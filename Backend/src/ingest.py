"""Ingestao da leitura climatica AO VIVO do dia, por variavel.

Estrategia: partir da PREVISAO do proprio modelo para o dia (ou do historico
real, se o dia ja estiver coletado) e sobrescrever, variavel a variavel, com
os valores reais que cada API gratuita conseguir entregar:

  * Open-Meteo -> temperatura, precipitacao, umidade, vento
  * NASA POWER -> radiacao solar

Assim, a base so e usada nas variaveis que a respectiva API nao forneceu
(ex.: a NASA POWER publica radiacao com alguns dias de defasagem, entao a
radiacao de "hoje" costuma vir da previsao do modelo, enquanto as demais
variaveis vem reais do Open-Meteo). Nao ha climatologia generica: se nem as
APIs nem o historico nem a previsao cobrirem alguma variavel do dia, a
leitura falha pedindo para gerar a previsao.

Cada leitura carrega, em `fontes`, a origem de cada variavel, e em `fonte` um
resumo legivel.
"""

from __future__ import annotations

import datetime as dt
import logging

from .clients import (
    VARS_NASA_POWER,
    VARS_OPEN_METEO,
    ClimateAPIError,
    ClimateReading,
    fetch_nasa_power,
    fetch_open_meteo,
)
from .config import CLIMATE_TARGETS

logger = logging.getLogger("ecotrack.ingest")


def _resumir_fontes(fontes: dict) -> str:
    """Monta um resumo legivel a partir da origem de cada variavel."""
    ao_vivo = sorted({v for v in fontes.values() if v in ("open-meteo", "nasa-power")})
    vars_modelo = sorted(k for k, v in fontes.items() if v == "modelo-clima")
    if not ao_vivo:
        return "modelo-clima"
    resumo = "+".join(ao_vivo)
    if vars_modelo:
        resumo += "+modelo-clima(" + ",".join(vars_modelo) + ")"
    return resumo


def obter_clima(
    latitude: float,
    longitude: float,
    dia: dt.date | None = None,
) -> ClimateReading:
    """Retorna o clima diario de um ponto: APIs ao vivo + base do modelo."""
    from .forecast import PrevisaoIndisponivelError, serie_prevista
    from .historico import serie_historica

    if dia is None:
        dia = dt.date.today()

    # Base: historico real (se o dia ja foi coletado) ou previsao do modelo.
    valores: dict[str, float] = {}
    fontes: dict[str, str] = {}
    hist = serie_historica(latitude, longitude, [dia])
    if dia in hist:
        for var in CLIMATE_TARGETS:
            valores[var] = hist[dia][var]
            fontes[var] = "historico-real"
    else:
        prev = serie_prevista(latitude, longitude, [dia])
        if dia in prev:
            for var in CLIMATE_TARGETS:
                valores[var] = prev[dia][var]
                fontes[var] = "modelo-clima"

    # Open-Meteo: temperatura, precipitacao, umidade, vento.
    try:
        om = fetch_open_meteo(latitude, longitude, dia)
        for var in VARS_OPEN_METEO:
            valores[var] = float(om[var])
            fontes[var] = "open-meteo"
    except ClimateAPIError as exc:
        logger.warning(
            "Open-Meteo indisponivel (%s); usando a base do modelo para %s.",
            exc,
            ", ".join(VARS_OPEN_METEO),
        )

    # NASA POWER: radiacao solar.
    try:
        nasa = fetch_nasa_power(latitude, longitude, dia)
        for var in VARS_NASA_POWER:
            valores[var] = float(nasa[var])
            fontes[var] = "nasa-power"
    except ClimateAPIError as exc:
        logger.warning(
            "NASA POWER sem dado para %s (%s); usando a base do modelo para %s.",
            dia,
            exc,
            ", ".join(VARS_NASA_POWER),
        )

    faltando = [v for v in CLIMATE_TARGETS if v not in valores]
    if faltando:
        raise PrevisaoIndisponivelError(
            f"Sem dado ao vivo nem previsto para {dia.isoformat()} "
            f"(variaveis: {', '.join(faltando)}). Gere/atualize a previsao "
            "(botao 'Gerar previsao climatica' do painel ou POST /previsao/gerar)."
        )

    return ClimateReading(
        data=dia,
        latitude=latitude,
        longitude=longitude,
        fonte=_resumir_fontes(fontes),
        fontes=fontes,
        **valores,
    )
