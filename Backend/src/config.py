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
# Banco operacional (SQLite): registros de corte informados pela equipe.
DB_PATH = Path(os.getenv("ECOTRACK_DB_PATH", DATA_DIR / "ecotrack.db"))

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
# TODAS as especies convivem no MESMO trecho (observacao de campo: elas crescem
# juntas, misturadas). Por isso cada celula do mapa e avaliada para as cinco, e
# cada especie tem seu PROPRIO conjunto de parametros -- nao apenas uma taxa
# base diferente. As formas funcionais que consomem estes parametros estao em
# src/growth.py.
#
# Parametros termicos:
#   temp_min_c / temp_otima_c / temp_max_c : cardeais da curva beta termica.
#   curva_termica_a : forma da curva beta (maior = pico mais estreito, especie
#                     mais exigente termicamente).
#
# Parametros hidricos (balanco de agua no solo, FAO-56):
#   kc                  : coeficiente de cultura (demanda hidrica relativa ao
#                         ET0 de referencia). Elefante/coloniao gastam mais.
#   prof_raiz_mm        : profundidade efetiva de raiz -> tamanho do reservatorio
#                         de agua que a especie alcanca.
#   fracao_esgotamento  : fracao da agua disponivel que a especie consome SEM
#                         sofrer estresse (p do FAO-56). Maior = mais resistente
#                         a seca.
#
# Parametros de luz / dossel:
#   k_radiacao_mj    : meia-saturacao da resposta fotossintetica a radiacao.
#                      Menor = tolera sombra; maior = exige sol pleno.
#   k_extincao       : coeficiente de extincao de Beer-Lambert do dossel.
#                      Alto = folhas horizontais (gramados prostrados, capta
#                      muito com pouca altura); baixo = folhas eretas.
#   lai_por_cm       : indice de area foliar acumulado por cm de altura.
#   lai_residual     : area foliar remanescente logo apos o corte (rebrota).
#                      Estolonifera/rizomatosa rebrota mais rapido.
#
# Parametros mecanicos / de porte:
#   altura_max_cm     : altura assintotica sem corte.
#   vento_sensibilidade / vento_expoente : acamamento por vento, que so pesa
#                      quando a planta ja esta alta (capim alto tomba, gramado
#                      rasteiro nao).
#   richards_nu       : forma da desaceleracao perto da altura maxima.
#
#   taxa_base_cm_dia  : crescimento potencial diario (cm) com todos os fatores
#                      em 1, ja calibrado para as demais funcoes.
#
# Fonte conceitual: gramineas C4 tropicais (Urochloa/Brachiaria, Cynodon,
# Megathyrsus/colonial, Pennisetum, Paspalum) tem otimo termico alto (25-35 C)
# e crescimento fortemente dependente de radiacao (PAR) e agua. As diferencas
# entre elas (tolerancia a seca, exigencia de luz, porte, rebrota) sao as que
# aparecem nos parametros acima.
# ---------------------------------------------------------------------------
GRASS_SPECIES = {
    # Decumbente, touceira aberta, raiz profunda, tolera solo acido e seca
    # moderada. O "meio-termo" entre gramado e capim alto.
    "Brachiaria (Urochloa)": {
        "taxa_base_cm_dia": 4.2,
        "temp_otima_c": 30.0,
        "temp_min_c": 12.0,
        "temp_max_c": 42.0,
        "curva_termica_a": 1.7,
        "altura_max_cm": 90.0,
        "kc": 0.95,
        "prof_raiz_mm": 900.0,
        "fracao_esgotamento": 0.55,
        "k_radiacao_mj": 11.0,
        "k_extincao": 0.55,
        "lai_por_cm": 0.061,
        "lai_residual": 0.45,
        "vento_sensibilidade": 0.004,
        "vento_expoente": 2.0,
        "richards_nu": 1.6,
    },
    # Estolonifera e prostrada (grama de campo de futebol). Raiz muito profunda
    # -> campea em seca; em compensacao exige sol pleno e nao tolera sombra.
    "Cynodon (grama-seda)": {
        "taxa_base_cm_dia": 1.5,
        "temp_otima_c": 28.0,
        "temp_min_c": 10.0,
        "temp_max_c": 41.0,
        "curva_termica_a": 1.4,
        "altura_max_cm": 45.0,
        "kc": 0.85,
        "prof_raiz_mm": 1300.0,
        "fracao_esgotamento": 0.65,
        "k_radiacao_mj": 14.0,
        "k_extincao": 0.85,
        "lai_por_cm": 0.111,
        "lai_residual": 0.80,
        "vento_sensibilidade": 0.001,
        "vento_expoente": 3.0,
        "richards_nu": 2.5,
    },
    # Touceira alta e ereta, tolerante a sombra (satura cedo na luz), mas
    # exigente em agua. Cresce rapido e tomba com vento quando alta.
    "Megathyrsus (capim-coloniao)": {
        "taxa_base_cm_dia": 9.5,
        "temp_otima_c": 31.0,
        "temp_min_c": 13.0,
        "temp_max_c": 43.0,
        "curva_termica_a": 2.1,
        "altura_max_cm": 180.0,
        "kc": 1.15,
        "prof_raiz_mm": 1100.0,
        "fracao_esgotamento": 0.45,
        "k_radiacao_mj": 8.0,
        "k_extincao": 0.45,
        "lai_por_cm": 0.033,
        "lai_residual": 0.35,
        "vento_sensibilidade": 0.006,
        "vento_expoente": 1.6,
        "richards_nu": 1.2,
    },
    # O maior porte da lista e o mais sedento: sofre primeiro em veranico e
    # acama com vento. Otimo termico mais alto (mais tropical).
    "Pennisetum (capim-elefante)": {
        "taxa_base_cm_dia": 14.5,
        "temp_otima_c": 32.0,
        "temp_min_c": 14.0,
        "temp_max_c": 43.0,
        "curva_termica_a": 2.3,
        "altura_max_cm": 250.0,
        "kc": 1.25,
        "prof_raiz_mm": 1000.0,
        "fracao_esgotamento": 0.40,
        "k_radiacao_mj": 9.0,
        "k_extincao": 0.40,
        "lai_por_cm": 0.024,
        "lai_residual": 0.30,
        "vento_sensibilidade": 0.008,
        "vento_expoente": 1.4,
        "richards_nu": 1.1,
    },
    # Rizomatosa, baixa e lenta, mas a mais rustica: menor demanda hidrica e
    # maior tolerancia a esgotamento do solo. Curva termica larga.
    "Paspalum (grama-batatais)": {
        "taxa_base_cm_dia": 1.1,
        "temp_otima_c": 27.0,
        "temp_min_c": 11.0,
        "temp_max_c": 40.0,
        "curva_termica_a": 1.2,
        "altura_max_cm": 40.0,
        "kc": 0.75,
        "prof_raiz_mm": 1500.0,
        "fracao_esgotamento": 0.70,
        "k_radiacao_mj": 10.0,
        "k_extincao": 0.70,
        "lai_por_cm": 0.113,
        "lai_residual": 0.70,
        "vento_sensibilidade": 0.0015,
        "vento_expoente": 3.0,
        "richards_nu": 2.2,
    },
}

# Solo das margens do Rodoanel: textura media, bem drenada.
# Agua disponivel (capacidade de campo - ponto de murcha) por metro de solo.
AGUA_DISPONIVEL_MM_POR_M = 120.0
# Fracao do reservatorio cheia no inicio de uma simulacao (condicao inicial do
# balanco hidrico quando nao ha historico de umidade do solo).
AGUA_INICIAL_FRACAO = 0.6
# Altitude media da RMSP (m) - entra na pressao atmosferica do ET0 (FAO-56).
REGION_ALTITUDE_M = 760.0

SPECIES_LIST = list(GRASS_SPECIES.keys())

# Altura operacional (cm) a partir da qual o corte e recomendado.
ALTURA_CORTE_RECOMENDADO_CM = 30.0

# ---------------------------------------------------------------------------
# Registros de CORTE (banco operacional).
#
# O modelo de crescimento sempre precisou de duas coisas que o sistema nao
# media: QUANDO foi o ultimo corte e a QUE ALTURA a grama ficou. Antes as duas
# eram premissas fixas no codigo (corte "hoje", altura zero). Agora vem do
# banco (src/db.py), alimentado pela equipe de campo.
#
# O seed representa a informacao de campo desta operacao: toda a rodovia foi
# rocada a 2 cm em 07/08/2026. Registros por ponto informados depois se
# sobrepoem a esse corte geral dentro do seu raio de influencia.
# ---------------------------------------------------------------------------
CORTE_PADRAO_DATA = "2026-08-07"
CORTE_PADRAO_ALTURA_CM = 2.0
# Raio (m) que um corte registrado por ponto cobre quando o operador nao informa
# outro. 300 m cobre a celula clicada e as vizinhas imediatas (celulas de 200 m).
RAIO_CORTE_PADRAO_M = 300.0
RAIO_CORTE_MAX_M = 20000.0
# Altura maxima aceita num registro de corte: acima disso nao e roçada, e erro
# de digitacao (a rocadeira opera entre ~2 e ~15 cm).
ALTURA_CORTE_MAX_CM = 50.0

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
