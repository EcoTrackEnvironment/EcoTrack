"""Configuracoes centrais do EcoTrack.

Define os pontos de monitoramento ao longo do Rodoanel Mario Covas (SP-021),
as especies de grama consideradas, as constantes agronomicas da formula de
crescimento e os parametros do modelo de previsao climatica.

As coordenadas sao aproximadas e representam celulas climaticas (trechos) do
anel viario metropolitano de Sao Paulo.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

DATA_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)

HISTORY_CSV = DATA_DIR / "climate_history.csv"
FORECAST_CSV = DATA_DIR / "climate_forecast.csv"
MODEL_PATH = MODELS_DIR / "climate_model.joblib"
MODEL_META_PATH = MODELS_DIR / "model_metadata.json"

# ---------------------------------------------------------------------------
# Regiao / clima de referencia (Regiao Metropolitana de Sao Paulo)
# Clima Cwa (subtropical umido) - inverno seco e ameno, verao quente e chuvoso.
# ---------------------------------------------------------------------------
REGION_NAME = "Rodoanel Mario Covas (SP-021) - RMSP"
REGION_TIMEZONE = "America/Sao_Paulo"
REGION_CENTER = {"latitude": -23.55, "longitude": -46.63}

# Pontos de monitoramento (trechos do Rodoanel).
# raio_metros representa a celula de influencia do ponto.
MONITORING_POINTS = [
    {"id": "RA-N01", "trecho": "Trecho Norte - Perus", "latitude": -23.400, "longitude": -46.740, "raio_metros": 500},
    {"id": "RA-N02", "trecho": "Trecho Norte - Cantareira", "latitude": -23.420, "longitude": -46.620, "raio_metros": 500},
    {"id": "RA-L01", "trecho": "Trecho Leste - Itaquaquecetuba", "latitude": -23.480, "longitude": -46.360, "raio_metros": 500},
    {"id": "RA-L02", "trecho": "Trecho Leste - Maua", "latitude": -23.640, "longitude": -46.430, "raio_metros": 500},
    {"id": "RA-S01", "trecho": "Trecho Sul - Sao Bernardo", "latitude": -23.720, "longitude": -46.560, "raio_metros": 500},
    {"id": "RA-O01", "trecho": "Trecho Oeste - Embu", "latitude": -23.650, "longitude": -46.850, "raio_metros": 500},
    {"id": "RA-O02", "trecho": "Trecho Oeste - Osasco", "latitude": -23.530, "longitude": -46.820, "raio_metros": 500},
]

# ---------------------------------------------------------------------------
# Especies de grama comuns em margens de rodovia no Rodoanel (SP).
#
# Parametros agronomicos (premissas documentadas no README):
#   taxa_base_cm_dia : crescimento potencial diario em cm sob condicoes otimas.
#   temp_otima_c     : temperatura do ar (C) de maior crescimento.
#   temp_min_c       : abaixo disso o crescimento cessa (~0).
#   temp_max_c       : acima disso o crescimento cessa (~0).
#   altura_max_cm    : altura assintotica tipica sem corte.
#
# Fonte conceitual: gramineas C4 tropicais (Urochloa/Brachiaria, Cynodon,
# Megathyrsus/colonial, Pennisetum, Paspalum) tem otimo termico alto (25-35 C)
# e crescimento fortemente dependente de radiacao (PAR) e agua.
# ---------------------------------------------------------------------------
GRASS_SPECIES = {
    "Brachiaria (Urochloa)": {
        "taxa_base_cm_dia": 1.8,
        "temp_otima_c": 30.0,
        "temp_min_c": 12.0,
        "temp_max_c": 42.0,
        "altura_max_cm": 90.0,
    },
    "Cynodon (grama-seda)": {
        "taxa_base_cm_dia": 1.1,
        "temp_otima_c": 28.0,
        "temp_min_c": 10.0,
        "temp_max_c": 41.0,
        "altura_max_cm": 45.0,
    },
    "Megathyrsus (capim-coloniao)": {
        "taxa_base_cm_dia": 2.6,
        "temp_otima_c": 31.0,
        "temp_min_c": 13.0,
        "temp_max_c": 43.0,
        "altura_max_cm": 180.0,
    },
    "Pennisetum (capim-elefante)": {
        "taxa_base_cm_dia": 3.0,
        "temp_otima_c": 32.0,
        "temp_min_c": 14.0,
        "temp_max_c": 43.0,
        "altura_max_cm": 250.0,
    },
    "Paspalum (grama-batatais)": {
        "taxa_base_cm_dia": 0.9,
        "temp_otima_c": 27.0,
        "temp_min_c": 11.0,
        "temp_max_c": 40.0,
        "altura_max_cm": 40.0,
    },
}

SPECIES_LIST = list(GRASS_SPECIES.keys())

# Altura operacional (cm) a partir da qual o corte e recomendado.
ALTURA_CORTE_RECOMENDADO_CM = 30.0

# Rota do anel viario (vertices lat/long, laco fechado).
# Linha central real do Rodoanel Mario Covas (SP-021) extraida do OpenStreetMap
# (ways com ref=SP-021, incluindo o Trecho Norte), com vertices a ~100 m.
# Arquivo: data/rodoanel_rota.json. Se ausente, cai no esboco de 7 vertices.
ROTA_JSON = DATA_DIR / "rodoanel_rota.json"

_ROTA_APROXIMADA = [
    (-23.400, -46.740),  # Norte - Perus
    (-23.420, -46.620),  # Norte - Cantareira
    (-23.480, -46.360),  # Leste - Itaquaquecetuba
    (-23.640, -46.430),  # Leste/Sul - Maua
    (-23.720, -46.560),  # Sul - Sao Bernardo
    (-23.650, -46.850),  # Oeste - Embu
    (-23.530, -46.820),  # Oeste - Osasco
]


def _carregar_rota() -> list[tuple[float, float]]:
    try:
        dados = json.loads(ROTA_JSON.read_text(encoding="utf-8"))
        vertices = [(float(lat), float(lon)) for lat, lon in dados["vertices"]]
        return vertices if len(vertices) >= 3 else _ROTA_APROXIMADA
    except (OSError, ValueError, KeyError):
        return _ROTA_APROXIMADA


RODOVIA_ROTA = _carregar_rota()

# Raio (m) de cada celula de monitoramento ao varrer a rodovia.
# Celulas a cada ~200 m com raio de 100 m cobrem a via de forma contigua.
RAIO_CELULA_M = 100

# Limiares de altura (cm) para a cor no mapa operacional:
#   verde:   1 a 15 cm   (sem necessidade de corte)
#   amarelo: 16 a 25 cm  (atencao)
#   vermelho: > 25 cm    (corte necessario)
FAIXA_VERDE_MAX_CM = 15.0
FAIXA_AMARELA_MAX_CM = 25.0


def classificar_cor(altura_cm: float) -> str:
    """Classifica a altura da grama na cor operacional do mapa."""
    if altura_cm > FAIXA_AMARELA_MAX_CM:
        return "vermelho"
    if altura_cm > FAIXA_VERDE_MAX_CM:
        return "amarelo"
    return "verde"

# Faixa maxima de "dias desde o ultimo corte" considerada no modelo.
# Cobre mais de um ano para permitir projecoes longas (ex.: "1 ano sem corte").
MAX_DIAS_DESDE_CORTE = 500

# ---------------------------------------------------------------------------
# APIs externas gratuitas (conforme PDF /ProvasPDFs - somente "Gratuitas").
# ---------------------------------------------------------------------------
OPEN_METEO_BASE = os.getenv(
    "OPEN_METEO_BASE", "https://api.open-meteo.com/v1/forecast"
)
OPEN_METEO_ARCHIVE_BASE = os.getenv(
    "OPEN_METEO_ARCHIVE_BASE", "https://archive-api.open-meteo.com/v1/archive"
)
NASA_POWER_BASE = os.getenv(
    "NASA_POWER_BASE",
    "https://power.larc.nasa.gov/api/temporal/daily/point",
)
HTTP_TIMEOUT_S = float(os.getenv("ECOTRACK_HTTP_TIMEOUT", "10"))

# ---------------------------------------------------------------------------
# Chatbot / Gemini (somente configuracao server-side).
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "45"))
CHAT_MAX_MESSAGE_CHARS = int(os.getenv("CHAT_MAX_MESSAGE_CHARS", "4000"))
CHAT_SESSION_TTL_SECONDS = int(os.getenv("CHAT_SESSION_TTL_SECONDS", "1800"))
CHAT_MAX_SESSIONS = int(os.getenv("CHAT_MAX_SESSIONS", "1000"))
CHAT_MAX_TOOL_ROUNDS = int(os.getenv("CHAT_MAX_TOOL_ROUNDS", "4"))
CHAT_RATE_LIMIT_PER_MINUTE = int(os.getenv("CHAT_RATE_LIMIT_PER_MINUTE", "20"))

# Mantem o comportamento CORS existente por padrao. Em producao, configure uma
# lista separada por virgulas com as origens exatas do frontend.
ECOTRACK_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ECOTRACK_CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

# ---------------------------------------------------------------------------
# Modelo de PREVISAO CLIMATICA.
#
# O modelo ML nao preve mais a altura da grama (isso e feito pela formula
# agronomica em growth.py); ele preve as variaveis climaticas de dias FUTUROS,
# treinado com ate 1 ano de dados reais das APIs (data/climate_history.csv)
# em todas as celulas climaticas da rodovia.
# ---------------------------------------------------------------------------
# Dias de historico real coletados das APIs externas.
HIST_DIAS = 365
# As APIs publicam dados com defasagem de alguns dias.
HIST_DEFASAGEM_DIAS = 6
# Resolucao (graus) das celulas CLIMATICAS: as coordenadas das celulas do mapa
# sao agrupadas nesta grade (~11 km, a resolucao do Open-Meteo) para a coleta.
RESOLUCAO_CLIMA_GRAUS = 0.1

# Variaveis-alvo previstas pelo modelo (ordem importa).
CLIMATE_TARGETS = [
    "temperatura_c",
    "precipitacao_mm",
    "umidade_pct",
    "radiacao_mj_m2",
    "vento_kmh",
]

# O modelo e AUTORREGRESSIVO: preve o dia seguinte olhando os dias ja
# passados. Para cada variavel usa o valor de ontem (lag1) e as medias dos
# ultimos 7 e 30 dias; a previsao de amanha entra como "ontem" do proximo
# passo, e assim por diante (dia 1, 2, 3... ate 365).
CLIMATE_LAG_JANELAS = (1, 7, 30)
# Dias de contexto passado necessarios para montar as features.
CLIMATE_CONTEXTO_DIAS = max(CLIMATE_LAG_JANELAS)

# Features do modelo climatico (ordem importa): lags + sazonalidade + coordenada.
CLIMATE_FEATURES = [
    f"{var}_media{j}" if j > 1 else f"{var}_lag1"
    for var in CLIMATE_TARGETS
    for j in CLIMATE_LAG_JANELAS
] + ["dia_ano_sin", "dia_ano_cos", "latitude", "longitude"]

# Dias de previsao gerados pelo botao "gerar previsao" (CSV climate_forecast).
FORECAST_DIAS = 365
