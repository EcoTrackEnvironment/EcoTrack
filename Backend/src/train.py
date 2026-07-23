"""Treino offline do modelo de PREVISAO CLIMATICA (autorregressivo).

Papel do modelo: descobrir o clima do DIA SEGUINTE analisando os climas ja
passados. Para prever um dia distante (ex.: daqui 10 dias), ele prepara todos
os dias antes: preve o dia 1, usa essa previsao como "passado" para prever o
dia 2, e assim por diante (previsao recursiva, feita em src/forecast.py).

Dataset de treino: data/climate_history.csv — ate 1 ano de dados diarios REAIS
das APIs gratuitas (Open-Meteo arquivo + NASA POWER) em todas as celulas
climaticas da rodovia (src/historico.py).

Features (por celula, para prever o dia D):
  * por variavel: valor do dia D-1 (lag1) e medias dos ultimos 7 e 30 dias;
  * sazonalidade do dia do ano (seno/cosseno, continua na virada do ano);
  * latitude/longitude da celula.
Alvos: as 5 variaveis climaticas do dia D.

Metodo: Random Forest Regressor multi-saida (scikit-learn). O ensemble da,
"de graca", uma medida de incerteza: a dispersao entre as arvores e gravada no
CSV de previsao e propagada ate a CONFIANCA exposta pela API.

Avaliacao com split TEMPORAL (ultimos 20% dos dias como teste): MAE de prever
o dia seguinte a partir de dados reais.
"""

from __future__ import annotations

import datetime as dt
import json
import math

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

import joblib

from .config import (
    CLIMATE_CONTEXTO_DIAS,
    CLIMATE_FEATURES,
    CLIMATE_LAG_JANELAS,
    CLIMATE_TARGETS,
    HISTORY_CSV,
    MODEL_META_PATH,
    MODEL_PATH,
)

N_ESTIMATORS = 200


def features_de_contexto(
    contexto: np.ndarray, data: dt.date, latitude: float, longitude: float
) -> dict:
    """Features para prever o dia `data` a partir do CONTEXTO passado.

    `contexto` e uma matriz (>= CLIMATE_CONTEXTO_DIAS, n_vars) com os dias
    anteriores em ordem cronologica (mais recente na ultima linha) — valores
    reais ou ja previstos, no caso da previsao recursiva.
    """
    f = {}
    for i, var in enumerate(CLIMATE_TARGETS):
        for j in CLIMATE_LAG_JANELAS:
            nome = f"{var}_media{j}" if j > 1 else f"{var}_lag1"
            f[nome] = float(contexto[-j:, i].mean())
    ang = 2.0 * math.pi * (data.timetuple().tm_yday - 1) / 365.25
    f["dia_ano_sin"] = math.sin(ang)
    f["dia_ano_cos"] = math.cos(ang)
    f["latitude"] = latitude
    f["longitude"] = longitude
    return f


def montar_dataset_supervisionado(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma o historico em pares (features dos dias passados -> dia D)."""
    linhas = []
    for (lat, lon), grupo in df.groupby(["latitude", "longitude"]):
        grupo = grupo.sort_values("data")
        valores = grupo[CLIMATE_TARGETS].to_numpy(dtype=float)
        datas = list(grupo["data"])
        for t in range(CLIMATE_CONTEXTO_DIAS, len(grupo)):
            f = features_de_contexto(
                valores[t - CLIMATE_CONTEXTO_DIAS : t], datas[t], lat, lon
            )
            f["data"] = datas[t]
            for i, var in enumerate(CLIMATE_TARGETS):
                f[f"alvo_{var}"] = valores[t, i]
            linhas.append(f)
    return pd.DataFrame(linhas)


def treinar(caminho_historico=HISTORY_CSV) -> dict:
    """Treina o modelo climatico autorregressivo e persiste modelo + metadados."""
    if not caminho_historico.exists():
        from .historico import coletar_historico

        coletar_historico()
    df = pd.read_csv(caminho_historico, parse_dates=["data"])
    df["data"] = df["data"].dt.date

    sup = montar_dataset_supervisionado(df)
    X = sup[CLIMATE_FEATURES]
    y = sup[[f"alvo_{v}" for v in CLIMATE_TARGETS]]

    # Split temporal: ultimos 20% dos dias como teste (treina no passado,
    # preve o dia seguinte — o cenario real de uso).
    datas_ordenadas = sorted(sup["data"].unique())
    corte = datas_ordenadas[int(len(datas_ordenadas) * 0.8)]
    treino = sup["data"] < corte
    X_train, y_train = X[treino], y[treino]
    X_test, y_test = X[~treino], y[~treino]

    modelo = RandomForestRegressor(
        n_estimators=N_ESTIMATORS,
        min_samples_leaf=4,
        n_jobs=-1,
        random_state=42,
    )
    modelo.fit(X_train, y_train)

    pred = modelo.predict(X_test)
    mae_por_var = {
        var: round(float(mean_absolute_error(y_test[f"alvo_{var}"], pred[:, i])), 3)
        for i, var in enumerate(CLIMATE_TARGETS)
    }

    joblib.dump(modelo, MODEL_PATH)

    meta = {
        "modelo": "RandomForestRegressor (multi-saida, autorregressivo)",
        "papel": "prever o clima do dia seguinte a partir dos dias ja passados",
        "n_estimators": N_ESTIMATORS,
        "treinado_em": dt.datetime.now().isoformat(timespec="seconds"),
        "historico": {
            "arquivo": HISTORY_CSV.name,
            "n_amostras": int(len(sup)),
            "n_celulas_climaticas": int(df[["latitude", "longitude"]].drop_duplicates().shape[0]),
            "periodo": [
                min(df["data"]).isoformat(),
                max(df["data"]).isoformat(),
            ],
            "pct_dados_reais": round(
                float(df["variaveis_reais"].mean() / len(CLIMATE_TARGETS) * 100), 1
            ) if "variaveis_reais" in df else None,
        },
        "features": CLIMATE_FEATURES,
        "targets": CLIMATE_TARGETS,
        "split": "temporal (ultimos 20% dos dias como teste)",
        "metricas": {"mae_por_variavel": mae_por_var},
    }
    MODEL_META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


if __name__ == "__main__":
    m = treinar()
    print("Modelo climatico treinado.")
    print(json.dumps(m["metricas"], indent=2))
