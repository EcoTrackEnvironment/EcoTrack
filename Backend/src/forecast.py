"""Geracao da PREVISAO CLIMATICA recursiva (dia a dia) em CSV.

O modelo autorregressivo (src/train.py) so sabe prever o DIA SEGUINTE a partir
dos dias ja passados. Para prever um dia distante, TODOS os dias anteriores
precisam estar prontos: este modulo preve o dia 1 a partir do historico real,
usa essa previsao como "passado" para prever o dia 2, e assim por diante ate
FORECAST_DIAS (365). O resultado — todas as celulas climaticas da rodovia —
vai para data/climate_forecast.csv, com a incerteza (desvio-padrao entre as
arvores) por variavel/dia.

Esse CSV e o que a API consulta para dias futuros nas projecoes de
crescimento; gere-o pelo botao do painel (POST /previsao/gerar) ou pelo
pipeline offline.
"""

from __future__ import annotations

import datetime as dt
import functools
import logging

import numpy as np
import pandas as pd

import joblib

from .config import (
    CLIMATE_CONTEXTO_DIAS,
    CLIMATE_FEATURES,
    CLIMATE_TARGETS,
    FORECAST_CSV,
    FORECAST_DIAS,
    HISTORY_CSV,
    MODEL_PATH,
)
from .train import features_de_contexto

logger = logging.getLogger("ecotrack.forecast")

# Indices das variaveis que nao podem ser negativas (todas menos temperatura).
_NAO_NEG = [i for i, v in enumerate(CLIMATE_TARGETS) if v != "temperatura_c"]


class PrevisaoIndisponivelError(RuntimeError):
    """Historico ou modelo ausentes para gerar a previsao."""


def gerar_previsao(dias: int = FORECAST_DIAS, caminho=FORECAST_CSV) -> pd.DataFrame:
    """Gera o CSV com `dias` de previsao para TODAS as celulas climaticas.

    Recursivo: o dia N e previsto com o contexto [reais... previsoes 1..N-1].
    Grava, por dia/celula, as 5 variaveis previstas e o desvio-padrao entre as
    arvores de cada uma (usado na confianca).
    """
    if not MODEL_PATH.exists():
        raise PrevisaoIndisponivelError(
            f"Modelo nao encontrado em {MODEL_PATH}. Rode: python -m scripts.build_pipeline"
        )
    if not HISTORY_CSV.exists():
        raise PrevisaoIndisponivelError(
            f"Historico nao encontrado em {HISTORY_CSV}. Atualize o historico primeiro."
        )
    modelo = joblib.load(MODEL_PATH)
    hist = pd.read_csv(HISTORY_CSV, parse_dates=["data"])
    hist["data"] = hist["data"].dt.date

    # Contexto inicial por celula: ultimos CLIMATE_CONTEXTO_DIAS dias reais.
    celulas: list[tuple[float, float]] = []
    contextos: dict[tuple[float, float], np.ndarray] = {}
    for (lat, lon), grupo in hist.groupby(["latitude", "longitude"]):
        grupo = grupo.sort_values("data")
        celulas.append((lat, lon))
        contextos[(lat, lon)] = grupo[CLIMATE_TARGETS].to_numpy(dtype=float)[
            -CLIMATE_CONTEXTO_DIAS:
        ]
    ultimo_dia_real = max(hist["data"])
    logger.info(
        "Gerando %s dias de previsao para %s celulas (apos %s)...",
        dias, len(celulas), ultimo_dia_real,
    )

    linhas = []
    for passo in range(1, dias + 1):
        data_alvo = ultimo_dia_real + dt.timedelta(days=passo)
        X = pd.DataFrame(
            [
                features_de_contexto(contextos[c], data_alvo, c[0], c[1])
                for c in celulas
            ]
        )[CLIMATE_FEATURES]

        media = modelo.predict(X)  # (n_celulas, n_vars)
        arvores = np.stack(
            [est.predict(X.to_numpy()) for est in modelo.estimators_]
        )  # (n_arvores, n_celulas, n_vars)
        media[:, _NAO_NEG] = np.clip(media[:, _NAO_NEG], 0.0, None)
        arvores[:, :, _NAO_NEG] = np.clip(arvores[:, :, _NAO_NEG], 0.0, None)
        std = arvores.std(axis=0)  # (n_celulas, n_vars)

        for k, (lat, lon) in enumerate(celulas):
            linhas.append(
                {
                    "data": data_alvo.isoformat(),
                    "latitude": lat,
                    "longitude": lon,
                    **{v: round(float(media[k, i]), 3) for i, v in enumerate(CLIMATE_TARGETS)},
                    **{f"std_{v}": round(float(std[k, i]), 3) for i, v in enumerate(CLIMATE_TARGETS)},
                }
            )
            # A previsao deste dia vira "passado" do proximo passo.
            contextos[(lat, lon)] = np.vstack([contextos[(lat, lon)][1:], media[k]])

    df = pd.DataFrame(linhas)
    df.to_csv(caminho, index=False)
    _carregar_previsao.cache_clear()
    logger.info("Previsao salva: %s linhas em %s", len(df), caminho)
    return df


@functools.lru_cache(maxsize=1)
def _carregar_previsao() -> pd.DataFrame | None:
    if not FORECAST_CSV.exists():
        return None
    df = pd.read_csv(FORECAST_CSV, parse_dates=["data"])
    df["data"] = df["data"].dt.date
    return df


def status_previsao() -> dict:
    """Resumo do CSV de previsao (para o painel)."""
    df = _carregar_previsao()
    if df is None or df.empty:
        return {"gerada": False}
    return {
        "gerada": True,
        "linhas": int(len(df)),
        "celulas": int(df[["latitude", "longitude"]].drop_duplicates().shape[0]),
        "periodo": [min(df["data"]).isoformat(), max(df["data"]).isoformat()],
    }


def serie_prevista(
    latitude: float, longitude: float, datas: list[dt.date]
) -> dict[dt.date, dict]:
    """Previsoes {data: {variavel: valor, std_variavel: std}} das datas pedidas.

    Usa a celula climatica mais proxima presente no CSV. Datas fora do periodo
    gerado ficam ausentes do retorno.
    """
    df = _carregar_previsao()
    if df is None or df.empty:
        return {}
    dist2 = (df["latitude"] - latitude) ** 2 + (df["longitude"] - longitude) ** 2
    mais_proxima = df.loc[dist2.idxmin(), ["latitude", "longitude"]]
    grupo = df[
        (df["latitude"] == mais_proxima["latitude"])
        & (df["longitude"] == mais_proxima["longitude"])
    ]
    out: dict[dt.date, dict] = {}
    for _, linha in grupo[grupo["data"].isin(set(datas))].iterrows():
        out[linha["data"]] = {
            **{v: float(linha[v]) for v in CLIMATE_TARGETS},
            **{f"std_{v}": float(linha[f"std_{v}"]) for v in CLIMATE_TARGETS},
        }
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = gerar_previsao()
    print(f"{len(df)} linhas de previsao geradas")
