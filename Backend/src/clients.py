from __future__ import annotations

import datetime as dt
import math
import time
from dataclasses import dataclass, field

import requests

from .config import (
    HTTP_TIMEOUT_S,
    NASA_POWER_BASE,
    OPEN_METEO_ARCHIVE_BASE,
    OPEN_METEO_BASE,
    REGION_TIMEZONE,
)


class ClimateAPIError(RuntimeError):
    """Falha ao obter dados de uma API climatica externa."""


@dataclass
class ClimateReading:
    """Leitura climatica diaria consolidada para um ponto."""

    data: dt.date
    latitude: float
    longitude: float
    temperatura_c: float
    precipitacao_mm: float
    umidade_pct: float
    radiacao_mj_m2: float
    vento_kmh: float
    fonte: str  # resumo: ex. "open-meteo+nasa-power", "open-meteo+modelo-clima(radiacao_mj_m2)"
    # Fonte de CADA variavel: "open-meteo" | "nasa-power" | "modelo-clima" |
    # "historico-real".
    fontes: dict = field(default_factory=dict)


def _get_json(url: str, params: dict) -> dict:
    try:
        resp = requests.get(url, params=params, timeout=HTTP_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ClimateAPIError("Resposta da API climatica nao e um objeto JSON.")
        return data
    except (requests.RequestException, ValueError) as exc:  # rede ou JSON
        raise ClimateAPIError(str(exc)) from exc


def _numero(valor: object, campo: str) -> float:
    """Converte um valor de API em numero finito ou normaliza a falha."""
    if valor is None or isinstance(valor, bool):
        raise ClimateAPIError(f"Resposta climatica invalida para {campo}.")
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise ClimateAPIError(f"Resposta climatica invalida para {campo}.") from exc
    if not math.isfinite(numero):
        raise ClimateAPIError(f"Resposta climatica invalida para {campo}.")
    return numero


def _valor_diario(daily: dict, campo: str) -> float:
    valores = daily.get(campo)
    if not isinstance(valores, list) or not valores:
        raise ClimateAPIError(f"Resposta Open-Meteo incompleta: {campo}.")
    return _numero(valores[0], campo)


def _parametro_nasa(data: dict) -> dict:
    try:
        parametro = data["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
    except (KeyError, TypeError) as exc:
        raise ClimateAPIError(f"Resposta NASA POWER incompleta: {exc}") from exc
    if not isinstance(parametro, dict) or not parametro:
        raise ClimateAPIError("Resposta NASA POWER incompleta: radiacao ausente.")
    return parametro


def fetch_open_meteo(latitude: float, longitude: float, dia: dt.date) -> dict:
    """Temperatura, precipitacao, umidade e vento (medias diarias)."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": dia.isoformat(),
        "end_date": dia.isoformat(),
        "daily": ",".join(
            [
                "temperature_2m_mean",
                "precipitation_sum",
                "relative_humidity_2m_mean",
                "wind_speed_10m_max",
            ]
        ),
        "timezone": REGION_TIMEZONE,
    }
    data = _get_json(OPEN_METEO_BASE, params)
    daily = data.get("daily") or {}
    try:
        if not isinstance(daily, dict):
            raise ClimateAPIError("Resposta Open-Meteo incompleta: daily ausente.")
        return {
            "temperatura_c": _valor_diario(daily, "temperature_2m_mean"),
            "precipitacao_mm": _valor_diario(daily, "precipitation_sum"),
            "umidade_pct": _valor_diario(daily, "relative_humidity_2m_mean"),
            "vento_kmh": _valor_diario(daily, "wind_speed_10m_max"),
        }
    except (KeyError, IndexError, TypeError) as exc:
        raise ClimateAPIError(f"Resposta Open-Meteo incompleta: {exc}") from exc


def fetch_open_meteo_historico(
    latitude: float, longitude: float, inicio: dt.date, fim: dt.date
) -> dict[dt.date, dict]:
    """Serie DIARIA historica (temperatura, precipitacao, umidade, vento).

    Usa o endpoint de arquivo do Open-Meteo (reanalise ERA5), que aceita
    intervalos longos em uma unica chamada. Retorna {data: {variavel: valor}};
    dias sem dado ficam ausentes do dicionario.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": inicio.isoformat(),
        "end_date": fim.isoformat(),
        "daily": ",".join(
            [
                "temperature_2m_mean",
                "precipitation_sum",
                "relative_humidity_2m_mean",
                "wind_speed_10m_max",
            ]
        ),
        "timezone": REGION_TIMEZONE,
    }
    data = _get_json(OPEN_METEO_ARCHIVE_BASE, params)
    daily = data.get("daily") or {}
    try:
        datas = daily["time"]
        serie: dict[dt.date, dict] = {}
        for i, iso in enumerate(datas):
            valores = {
                "temperatura_c": daily["temperature_2m_mean"][i],
                "precipitacao_mm": daily["precipitation_sum"][i],
                "umidade_pct": daily["relative_humidity_2m_mean"][i],
                "vento_kmh": daily["wind_speed_10m_max"][i],
            }
            if any(v is None for v in valores.values()):
                continue
            serie[dt.date.fromisoformat(iso)] = {
                k: _numero(v, k) for k, v in valores.items()
            }
        return serie
    except (KeyError, IndexError, TypeError) as exc:
        raise ClimateAPIError(f"Resposta Open-Meteo (arquivo) incompleta: {exc}") from exc


def fetch_nasa_power_historico(
    latitude: float, longitude: float, inicio: dt.date, fim: dt.date
) -> dict[dt.date, dict]:
    """Serie DIARIA historica de radiacao solar (MJ/m2/dia) da NASA POWER.

    Uma unica chamada cobre o intervalo todo. Dias ausentes (-999) ficam fora
    do dicionario retornado.
    """
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN",
        "community": "AG",
        "longitude": longitude,
        "latitude": latitude,
        "start": inicio.strftime("%Y%m%d"),
        "end": fim.strftime("%Y%m%d"),
        "format": "JSON",
    }
    data = _get_json(NASA_POWER_BASE, params)
    try:
        param = _parametro_nasa(data)
        serie: dict[dt.date, dict] = {}
        for chave, valor in param.items():
            if valor is None:
                continue
            numero = _numero(valor, "ALLSKY_SFC_SW_DWN")
            if numero <= -900:
                continue
            serie[dt.datetime.strptime(chave, "%Y%m%d").date()] = {
                "radiacao_mj_m2": numero
            }
        return serie
    except (KeyError, TypeError, ValueError) as exc:
        raise ClimateAPIError(f"Resposta NASA POWER incompleta: {exc}") from exc


def fetch_nasa_power(latitude: float, longitude: float, dia: dt.date) -> dict:
    """Radiacao solar global diaria (ALLSKY_SFC_SW_DWN) em MJ/m2/dia.

    A NASA POWER retorna kWh/m2/dia em ALLSKY_SFC_SW_DWN quando `units=...`;
    aqui usamos o parametro padrao (MJ/m2/dia).
    """
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN",
        "community": "AG",
        "longitude": longitude,
        "latitude": latitude,
        "start": dia.strftime("%Y%m%d"),
        "end": dia.strftime("%Y%m%d"),
        "format": "JSON",
    }
    data = _get_json(NASA_POWER_BASE, params)
    try:
        param = _parametro_nasa(data)
        valor = next(iter(param.values()))
        # NASA usa -999 para dados ausentes.
        if valor is None:
            raise ClimateAPIError("NASA POWER retornou valor ausente (-999).")
        numero = _numero(valor, "ALLSKY_SFC_SW_DWN")
        if numero <= -900:
            raise ClimateAPIError("NASA POWER retornou valor ausente (-999).")
        return {"radiacao_mj_m2": numero}
    except (KeyError, IndexError, TypeError) as exc:
        raise ClimateAPIError(f"Resposta NASA POWER incompleta: {exc}") from exc


def _checar_fonte(nome: str, url: str, fn, *args) -> dict:
    """Executa uma consulta minima a uma fonte e mede disponibilidade/latencia."""
    inicio = time.perf_counter()
    try:
        fn(*args)
        return {
            "nome": nome,
            "url": url,
            "status": "up",
            "latencia_ms": round((time.perf_counter() - inicio) * 1000, 1),
            "detalhe": "resposta valida",
        }
    except ClimateAPIError as exc:
        return {
            "nome": nome,
            "url": url,
            "status": "down",
            "latencia_ms": round((time.perf_counter() - inicio) * 1000, 1),
            "detalhe": str(exc)[:200],
        }


def checar_apis_externas(latitude: float, longitude: float) -> dict:
    """Verifica a disponibilidade das APIs externas gratuitas.

    Faz uma consulta real e minima a cada fonte. A NASA POWER publica dados com
    alguns dias de defasagem, entao usa-se uma data de ~7 dias atras; para a
    Open-Meteo, ontem.
    """
    hoje = dt.date.today()
    dia_om = hoje - dt.timedelta(days=1)
    dia_nasa = hoje - dt.timedelta(days=7)

    resultados = [
        _checar_fonte(
            "Open-Meteo",
            OPEN_METEO_BASE,
            fetch_open_meteo,
            latitude,
            longitude,
            dia_om,
        ),
        _checar_fonte(
            "NASA POWER",
            NASA_POWER_BASE,
            fetch_nasa_power,
            latitude,
            longitude,
            dia_nasa,
        ),
    ]
    alguma_fora = any(r["status"] == "down" for r in resultados)
    return {
        "apis": resultados,
        # Se qualquer fonte estiver fora, a leitura ao vivo usa a previsao do
        # proprio modelo como base nas variaveis que faltarem.
        "usando_modelo_como_base": alguma_fora,
        "verificado_em": dt.datetime.now().isoformat(timespec="seconds"),
    }


# Mapa de qual API fornece cada variavel climatica.
VARS_OPEN_METEO = ("temperatura_c", "precipitacao_mm", "umidade_pct", "vento_kmh")
VARS_NASA_POWER = ("radiacao_mj_m2",)
