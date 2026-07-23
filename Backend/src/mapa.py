"""Varredura operacional da rodovia em celulas de ~200 m.

Gera pontos espacados ao longo do laco do Rodoanel (config.RODOVIA_ROTA, linha
central real do SP-021 extraida do OpenStreetMap), a cada ~200 m (para que os
raios de 100 m cubram a via de forma contigua), e estima a altura da grama em
cada um, classificando-o por cor:

  verde   -> 1 a 15 cm
  amarelo -> 16 a 25 cm
  vermelho -> > 25 cm

A altura de cada celula vem da FORMULA agronomica (growth.py), acumulando dia a
dia a taxa de crescimento sob o clima da janela [hoje, data-alvo]: dias
passados usam o historico REAL coletado das APIs, hoje usa a leitura ao vivo e
dias futuros usam o clima PREVISTO pelo modelo climatico treinado. As celulas
do mapa sao agrupadas nas celulas CLIMATICAS (~11 km) coletadas no historico,
entao ha variacao espacial de clima ao longo do anel. A variacao restante vem
da especie atribuida a cada trecho (pseudo-aleatoria porem deterministica,
pois nao ha historico real de corte por segmento).
"""

from __future__ import annotations

import datetime as dt
import math

import numpy as np

from .config import (
    MAX_DIAS_DESDE_CORTE,
    RAIO_CELULA_M,
    REGION_CENTER,
    RODOVIA_ROTA,
    SPECIES_LIST,
    classificar_cor,
)
from .historico import grupo_climatico
from .ingest import obter_clima
from .predict import montar_clima_janelas, prever_crescimento_janela

# Fator de conversao aproximado de graus para km na latitude da RMSP.
_KM_POR_GRAU_LAT = 111.0


def _km_por_grau_lon(lat: float) -> float:
    return 111.320 * math.cos(math.radians(lat))


def _dist_km(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    lat1, lon1 = p1
    lat2, lon2 = p2
    dlat = (lat2 - lat1) * _KM_POR_GRAU_LAT
    dlon = (lon2 - lon1) * _km_por_grau_lon((lat1 + lat2) / 2)
    return math.hypot(dlat, dlon)


def _pontos_ao_longo(rota: list[tuple[float, float]], espacamento_km: float):
    """Interpola pontos ao longo do laco fechado, a cada `espacamento_km`."""
    loop = list(rota) + [rota[0]]  # fecha o anel
    pontos: list[tuple[float, float]] = []
    resto = 0.0
    for a, b in zip(loop[:-1], loop[1:]):
        seg_km = _dist_km(a, b)
        if seg_km == 0:
            continue
        d = resto
        while d < seg_km:
            t = d / seg_km
            pontos.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            d += espacamento_km
        resto = d - seg_km
    return pontos


def gerar_mapa_rodovia(
    espacamento_km: float = 0.2,
    dia: dt.date | None = None,
    seed: int = 7,
) -> dict:
    """Varre a rodovia e retorna rota + celulas classificadas por cor.

    A data e tratada como HORIZONTE DE PROJECAO: o "dias desde o ultimo corte" e
    o tempo decorrido entre hoje e a data escolhida (assumindo o ultimo corte
    hoje), aplicado igualmente a TODAS as celulas. Assim, escolher uma data 1 ano
    a frente testa toda a rodovia como se nao houvesse corte por 1 ano. A
    altura acumula dia a dia (formula agronomica): passado com historico real,
    futuro com o clima previsto pelo modelo — e por construcao nunca diminui
    ao alargar o horizonte (taxas diarias sao nao-negativas).
    """
    hoje = dt.date.today()
    alvo = dia or hoje
    dias_desde_corte = max((alvo - hoje).days, 0)
    # Limita a janela de projecao para nao extrapolar indefinidamente.
    dias_desde_corte = min(dias_desde_corte, MAX_DIAS_DESDE_CORTE)

    # Janela de crescimento: do corte (assumido hoje) ate a data-alvo.
    # Para datas passadas, apenas o dia-alvo (historico real).
    inicio_janela = min(hoje, alvo)
    fim_janela = min(alvo, hoje + dt.timedelta(days=dias_desde_corte))
    clima_hoje = (
        obter_clima(REGION_CENTER["latitude"], REGION_CENTER["longitude"], hoje)
        if inicio_janela <= hoje <= fim_janela
        else None
    )
    coords = _pontos_ao_longo(RODOVIA_ROTA, espacamento_km)

    rng = np.random.default_rng(seed)
    # Especie varia por trecho (deterministico); dias-desde-corte e uniforme e
    # vem do horizonte de projecao (data escolhida).
    atribuicoes = [
        (SPECIES_LIST[int(rng.integers(len(SPECIES_LIST)))], dias_desde_corte)
        for _ in coords
    ]

    # Uma janela climatica por celula CLIMATICA (~11 km) e um resultado por
    # (celula climatica, especie) — reutilizado por todas as celulas do mapa
    # daquele grupo.
    grupos_por_celula = [grupo_climatico(lat, lon) for lat, lon in coords]
    janelas = montar_clima_janelas(
        sorted(set(grupos_por_celula)), inicio_janela, fim_janela, clima_hoje
    )
    cache_pred: dict[tuple, dict] = {}
    preds = []
    for grupo, (especie, _) in zip(grupos_por_celula, atribuicoes):
        chave = (grupo, especie)
        if chave not in cache_pred:
            cache_pred[chave] = prever_crescimento_janela(janelas[grupo], especie)
        preds.append(cache_pred[chave])

    exemplo = next(iter(janelas.values()))
    fonte_clima = "+".join(
        f"{nome}({n}d)" for nome, n in exemplo["fontes"].items() if n > 0
    )

    resumo = {"verde": 0, "amarelo": 0, "vermelho": 0}
    celulas = []
    for (lat, lon), (especie, dias), pred in zip(coords, atribuicoes, preds):
        cor = classificar_cor(pred["altura_cm"])
        resumo[cor] += 1
        celulas.append(
            {
                "latitude": round(lat, 5),
                "longitude": round(lon, 5),
                "raio_metros": RAIO_CELULA_M,
                "altura_cm": pred["altura_cm"],
                "confianca": pred["confianca"],
                "especie": especie,
                "dias_desde_corte": dias,
                "cor": cor,
            }
        )

    confianca_media = (
        sum(c["confianca"] for c in celulas) / len(celulas) if celulas else 0.0
    )

    return {
        "rota": [[lat, lon] for lat, lon in RODOVIA_ROTA],
        "celulas": celulas,
        "total_celulas": len(celulas),
        "raio_metros": RAIO_CELULA_M,
        "resumo": resumo,
        "confianca_media": round(confianca_media, 3),
        "fonte_clima": fonte_clima,
        "data": alvo.isoformat(),
        "dias_desde_corte": dias_desde_corte,
    }
