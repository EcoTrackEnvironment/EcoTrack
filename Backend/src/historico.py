"""Coleta e consulta do HISTORICO CLIMATICO real da rodovia.

A API puxa ate 1 ano de dados diarios das APIs externas gratuitas (Open-Meteo
arquivo/ERA5 e NASA POWER) para todas as coordenadas onde ha celulas do mapa,
e guarda tudo em data/climate_history.csv. Esse CSV e o dataset de treino do
modelo de previsao climatica (src/train.py) e tambem a fonte de clima REAL
para dias passados nas projecoes de crescimento.

Como a resolucao espacial das APIs de clima e de ~11 km (muito maior que os
200 m entre celulas do mapa), as coordenadas das celulas sao agrupadas em
CELULAS CLIMATICAS numa grade de RESOLUCAO_CLIMA_GRAUS (~0.1 grau): todas as
celulas do mapa ficam cobertas, sem baixar o mesmo dado centenas de vezes.

Dias/variaveis que as APIs nao entregarem sao preenchidos por INTERPOLACAO
dos dias reais vizinhos (sem climatologia sintetica), mantendo o CSV completo
para o treino. A coluna `variaveis_reais` conta quantas das 5 variaveis do dia
vieram direto das APIs (antes da interpolacao).
"""

from __future__ import annotations

import datetime as dt
import functools
import logging

import pandas as pd

from .clients import (
    ClimateAPIError,
    fetch_nasa_power_historico,
    fetch_open_meteo_historico,
)
from .config import (
    CLIMATE_TARGETS,
    HIST_DEFASAGEM_DIAS,
    HIST_DIAS,
    HISTORY_CSV,
    RESOLUCAO_CLIMA_GRAUS,
    RODOVIA_ROTA,
)

logger = logging.getLogger("ecotrack.historico")


class ColetaIndisponivelError(RuntimeError):
    """As APIs externas nao devolveram dados suficientes para a coleta."""

_VARS_OPEN_METEO = ("temperatura_c", "precipitacao_mm", "umidade_pct", "vento_kmh")
_VARS_NASA = ("radiacao_mj_m2",)


def grupo_climatico(latitude: float, longitude: float) -> tuple[float, float]:
    """Coordenada da celula CLIMATICA (grade de ~11 km) que cobre o ponto."""
    passo = RESOLUCAO_CLIMA_GRAUS
    return (round(round(latitude / passo) * passo, 4), round(round(longitude / passo) * passo, 4))


def celulas_climaticas() -> list[tuple[float, float]]:
    """Celulas climaticas unicas que cobrem toda a rota da rodovia."""
    return sorted({grupo_climatico(lat, lon) for lat, lon in RODOVIA_ROTA})


def periodo_historico(dias: int = HIST_DIAS) -> tuple[dt.date, dt.date]:
    """Janela [inicio, fim] coberta pela coleta (fim defasado da publicacao)."""
    fim = dt.date.today() - dt.timedelta(days=HIST_DEFASAGEM_DIAS)
    return fim - dt.timedelta(days=dias - 1), fim


def coletar_historico(dias: int = HIST_DIAS, caminho=HISTORY_CSV) -> pd.DataFrame:
    """Baixa o historico diario de todas as celulas climaticas e salva em CSV.

    Uma chamada por API por celula (as duas APIs aceitam intervalos). Dias ou
    variaveis que faltarem sao interpolados dos dias reais vizinhos da propria
    celula; se uma variavel nao vier de jeito nenhum para uma celula, a coleta
    falha (ColetaIndisponivelError) em vez de inventar dados.
    """
    inicio, fim = periodo_historico(dias)
    grupos = celulas_climaticas()
    logger.info(
        "Coletando %s dias (%s..%s) para %s celulas climaticas...",
        dias, inicio, fim, len(grupos),
    )

    todas_datas = [inicio + dt.timedelta(days=i) for i in range((fim - inicio).days + 1)]
    frames = []
    for lat, lon in grupos:
        try:
            om = fetch_open_meteo_historico(lat, lon, inicio, fim)
        except ClimateAPIError as exc:
            logger.warning("Open-Meteo falhou em (%s, %s): %s", lat, lon, exc)
            om = {}
        try:
            nasa = fetch_nasa_power_historico(lat, lon, inicio, fim)
        except ClimateAPIError as exc:
            logger.warning("NASA POWER falhou em (%s, %s): %s", lat, lon, exc)
            nasa = {}

        grade = pd.DataFrame(index=pd.Index(todas_datas, name="data"), columns=CLIMATE_TARGETS, dtype=float)
        for d, vals in om.items():
            for var in _VARS_OPEN_METEO:
                grade.loc[d, var] = vals[var]
        for d, vals in nasa.items():
            for var in _VARS_NASA:
                grade.loc[d, var] = vals[var]

        sem_dado = [v for v in CLIMATE_TARGETS if grade[v].isna().all()]
        if sem_dado:
            raise ColetaIndisponivelError(
                f"As APIs nao devolveram nenhum dado de {', '.join(sem_dado)} "
                f"para a celula ({lat}, {lon}). Verifique a conexao/status das "
                "APIs (GET /status/apis) e tente novamente."
            )

        reais = grade.notna().sum(axis=1)
        # Lacunas pontuais: interpolacao linear entre dias reais vizinhos
        # (e ffill/bfill nas bordas do periodo).
        grade = grade.interpolate(limit_direction="both")

        grade = grade.round(3)
        grade["variaveis_reais"] = reais
        grade["latitude"] = lat
        grade["longitude"] = lon
        frames.append(grade.reset_index())

    df = pd.concat(frames, ignore_index=True)
    df["data"] = [d.isoformat() for d in df["data"]]
    df = df[["data", "latitude", "longitude", *CLIMATE_TARGETS, "variaveis_reais"]]
    df.to_csv(caminho, index=False)
    _carregar_historico.cache_clear()
    logger.info("Historico salvo: %s linhas em %s", len(df), caminho)
    return df


@functools.lru_cache(maxsize=1)
def _carregar_historico() -> pd.DataFrame | None:
    if not HISTORY_CSV.exists():
        return None
    df = pd.read_csv(HISTORY_CSV, parse_dates=["data"])
    df["data"] = df["data"].dt.date
    return df


def serie_historica(
    latitude: float, longitude: float, datas: list[dt.date]
) -> dict[dt.date, dict]:
    """Valores REAIS do historico para as datas pedidas (celula mais proxima).

    Retorna {data: {variavel: valor}} apenas para as datas presentes no CSV.
    """
    df = _carregar_historico()
    if df is None or df.empty:
        return {}
    lat_g, lon_g = grupo_climatico(latitude, longitude)
    grupo = df[(df["latitude"] == lat_g) & (df["longitude"] == lon_g)]
    if grupo.empty:
        # Celula fora da grade coletada: usa a mais proxima.
        dist2 = (df["latitude"] - latitude) ** 2 + (df["longitude"] - longitude) ** 2
        mais_proxima = df.loc[dist2.idxmin(), ["latitude", "longitude"]]
        grupo = df[
            (df["latitude"] == mais_proxima["latitude"])
            & (df["longitude"] == mais_proxima["longitude"])
        ]
    alvo = set(datas)
    out: dict[dt.date, dict] = {}
    for _, linha in grupo[grupo["data"].isin(alvo)].iterrows():
        out[linha["data"]] = {v: float(linha[v]) for v in CLIMATE_TARGETS}
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = coletar_historico()
    print(f"{len(df)} linhas, {df[['latitude', 'longitude']].drop_duplicates().shape[0]} celulas climaticas")
