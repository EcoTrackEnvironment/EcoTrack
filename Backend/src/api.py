"""API HTTP do EcoTrack (FastAPI).

Expoe as "Variaveis X" (altura estimada da grama + confianca) por ponto da
rodovia. Endpoint principal:

  GET /variaveis-x

retornando o JSON no formato especificado:

  {
    "localizacao": {"latitude": ..., "longitude": ..., "raio_metros": ...},
    "previsao": {"altura": ..., "probabilidade": ...}
  }

Rode o servidor com:
  uvicorn src.api:app --reload
"""

from __future__ import annotations

import datetime as dt
import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .clients import checar_apis_externas
from .forecast import PrevisaoIndisponivelError, gerar_previsao, status_previsao
from .historico import coletar_historico
from .mapa import gerar_mapa_rodovia
from .config import (
    ALTURA_CORTE_RECOMENDADO_CM,
    FORECAST_DIAS,
    MODEL_META_PATH,
    MONITORING_POINTS,
    REGION_CENTER,
    REGION_NAME,
    SPECIES_LIST,
)
from .predict import ModeloIndisponivelError, prever_altura
from .train import treinar

app = FastAPI(
    title="EcoTrack API",
    version="1.0.0",
    description=(
        "Monitoramento preditivo de crescimento de grama para otimizar o corte "
        "nas margens do Rodoanel (CCR Motiva)."
    ),
)

# CORS liberado para uso local do FrontEnd (site estatico).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas de resposta
# ---------------------------------------------------------------------------
class Localizacao(BaseModel):
    latitude: float
    longitude: float
    raio_metros: float


class Previsao(BaseModel):
    altura: float
    probabilidade: float = Field(..., ge=0.0, le=1.0)


class Clima(BaseModel):
    temperatura_c: float
    precipitacao_mm: float
    umidade_pct: float
    radiacao_mj_m2: float
    vento_kmh: float
    # Origem de cada variavel: "open-meteo" | "nasa-power" | "modelo-clima" | "historico-real".
    fontes: dict[str, str]


class RespostaVariaveisX(BaseModel):
    localizacao: Localizacao
    previsao: Previsao
    # Campos auxiliares (uteis para operacao; nao fazem parte do contrato minimo)
    especie: str
    dias_desde_corte: int
    data: str
    fonte_clima: str
    corte_recomendado: bool
    clima: Clima


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validar_especie(especie: str) -> None:
    if especie not in SPECIES_LIST:
        raise HTTPException(
            status_code=422,
            detail={
                "erro": "especie desconhecida",
                "especies_validas": SPECIES_LIST,
            },
        )


def _parse_data(data: str | None) -> dt.date | None:
    if data is None:
        return None
    try:
        return dt.date.fromisoformat(data)
    except ValueError:
        raise HTTPException(status_code=422, detail="data invalida (use AAAA-MM-DD)")


def _predizer(latitude, longitude, raio_metros, especie, dias_desde_corte, dia):
    try:
        res = prever_altura(latitude, longitude, especie, dias_desde_corte, dia)
    except ModeloIndisponivelError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PrevisaoIndisponivelError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    clima = res["clima"]
    return RespostaVariaveisX(
        localizacao=Localizacao(
            latitude=latitude, longitude=longitude, raio_metros=raio_metros
        ),
        previsao=Previsao(
            altura=res["altura_cm"],
            probabilidade=res["confianca"],
        ),
        especie=especie,
        dias_desde_corte=dias_desde_corte,
        data=(dia or dt.date.today()).isoformat(),
        fonte_clima=clima.fonte,
        corte_recomendado=res["altura_cm"] >= ALTURA_CORTE_RECOMENDADO_CM,
        clima=Clima(
            temperatura_c=round(clima.temperatura_c, 2),
            precipitacao_mm=round(clima.precipitacao_mm, 2),
            umidade_pct=round(clima.umidade_pct, 1),
            radiacao_mj_m2=round(clima.radiacao_mj_m2, 2),
            vento_kmh=round(clima.vento_kmh, 1),
            fontes=clima.fontes,
        ),
    )


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@app.get("/")
def raiz():
    return {
        "servico": "EcoTrack API",
        "regiao": REGION_NAME,
        "endpoints": [
            "/variaveis-x",
            "/mapa/rodovia",
            "/historico/atualizar (POST)",
            "/previsao/gerar (POST)",
            "/previsao/status",
            "/pontos",
            "/especies",
            "/health",
            "/status/apis",
        ],
    }


@app.get("/health")
def health():
    modelo_ok = MODEL_META_PATH.exists()
    return {"status": "ok" if modelo_ok else "modelo_ausente", "modelo_treinado": modelo_ok}


@app.get("/status/apis")
def status_apis():
    """Disponibilidade das APIs externas gratuitas (Open-Meteo, NASA POWER).

    Faz uma consulta real de checagem a cada fonte. Se alguma estiver fora, a
    leitura ao vivo usa a previsao do proprio modelo nas variaveis que faltarem.
    """
    return checar_apis_externas(REGION_CENTER["latitude"], REGION_CENTER["longitude"])


@app.get("/pontos")
def listar_pontos():
    return {"regiao": REGION_NAME, "pontos": MONITORING_POINTS}


@app.get("/mapa/rodovia")
def mapa_rodovia(
    espacamento_km: float = Query(0.2, ge=0.1, le=5.0),
    data: str | None = Query(None, description="Data AAAA-MM-DD (padrao: hoje)"),
):
    """Varre toda a rodovia em celulas de ~200 m e classifica cada uma por cor.

    verde = 1-15 cm · amarelo = 16-25 cm · vermelho = > 25 cm.
    """
    dia = _parse_data(data)
    try:
        return gerar_mapa_rodovia(espacamento_km=espacamento_km, dia=dia)
    except ModeloIndisponivelError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PrevisaoIndisponivelError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/historico/atualizar")
def atualizar_historico():
    """Botao "atualizar historico": repuxa ate 1 ano de dados reais das APIs
    para todas as celulas climaticas da rodovia e RETREINA o modelo com eles.
    """
    df = coletar_historico()
    meta = treinar()
    return {
        "historico": {
            "linhas": int(len(df)),
            "celulas_climaticas": int(df[["latitude", "longitude"]].drop_duplicates().shape[0]),
            "periodo": [df["data"].min(), df["data"].max()],
        },
        "modelo_retreinado": True,
        "metricas": meta["metricas"],
        "aviso": "A previsao existente ficou desatualizada: gere-a novamente em /previsao/gerar.",
    }


@app.post("/previsao/gerar")
def previsao_gerar():
    """Botao "gerar previsao": o modelo preve o clima dia a dia (recursivo,
    dia 1 -> dia 2 -> ...) por 365 dias, para TODAS as celulas climaticas da
    rodovia, e salva tudo em data/climate_forecast.csv.
    """
    try:
        df = gerar_previsao(FORECAST_DIAS)
    except PrevisaoIndisponivelError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {
        "linhas": int(len(df)),
        "celulas_climaticas": int(df[["latitude", "longitude"]].drop_duplicates().shape[0]),
        "dias": FORECAST_DIAS,
        "periodo": [df["data"].min(), df["data"].max()],
    }


@app.get("/previsao/status")
def previsao_status():
    """Situacao do CSV de previsao climatica (existe? qual periodo cobre?)."""
    return status_previsao()


@app.get("/especies")
def listar_especies():
    return {"especies": SPECIES_LIST}


@app.get("/modelo")
def info_modelo():
    if not MODEL_META_PATH.exists():
        raise HTTPException(status_code=503, detail="Modelo nao treinado.")
    return json.loads(MODEL_META_PATH.read_text())


@app.get("/variaveis-x", response_model=RespostaVariaveisX)
def variaveis_x(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    especie: str = Query(..., description="Especie de grama (ver /especies)"),
    dias_desde_corte: int = Query(30, ge=0, le=365),
    raio_metros: float = Query(500, gt=0),
    data: str | None = Query(None, description="Data AAAA-MM-DD (padrao: hoje)"),
):
    """Retorna as Variaveis X (altura_cm + confianca) para um ponto arbitrario."""
    _validar_especie(especie)
    dia = _parse_data(data)
    return _predizer(latitude, longitude, raio_metros, especie, dias_desde_corte, dia)


@app.get("/variaveis-x/ponto/{ponto_id}", response_model=RespostaVariaveisX)
def variaveis_x_por_ponto(
    ponto_id: str,
    especie: str = Query(..., description="Especie de grama (ver /especies)"),
    dias_desde_corte: int = Query(30, ge=0, le=365),
    data: str | None = Query(None, description="Data AAAA-MM-DD (padrao: hoje)"),
):
    """Como /variaveis-x, mas usando um ponto de monitoramento pre-cadastrado."""
    _validar_especie(especie)
    ponto = next((p for p in MONITORING_POINTS if p["id"] == ponto_id), None)
    if ponto is None:
        raise HTTPException(
            status_code=404,
            detail={"erro": "ponto nao encontrado", "ids": [p["id"] for p in MONITORING_POINTS]},
        )
    dia = _parse_data(data)
    return _predizer(
        ponto["latitude"],
        ponto["longitude"],
        ponto["raio_metros"],
        especie,
        dias_desde_corte,
        dia,
    )
