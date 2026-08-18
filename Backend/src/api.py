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
from .chatbot import create_chat_router
from .db import (
    CorteInvalidoError,
    CorteNaoEncontradoError,
    corte_vigente,
    inicializar as inicializar_banco,
    listar_cortes,
    registrar_corte,
    remover_corte,
)
from .forecast import PrevisaoIndisponivelError, gerar_previsao, status_previsao
from .historico import coletar_historico
from .ingest import obter_clima
from .mapa import gerar_mapa_rodovia
from .config import (
    ALTURA_CORTE_MAX_CM,
    ALTURA_CORTE_RECOMENDADO_CM,
    ECOTRACK_CORS_ORIGINS,
    FORECAST_DIAS,
    MAX_DIAS_DESDE_CORTE,
    MODEL_META_PATH,
    MONITORING_POINTS,
    RAIO_CORTE_MAX_M,
    RAIO_CORTE_PADRAO_M,
    REGION_CENTER,
    REGION_NAME,
    SPECIES_LIST,
    classificar_cor,
)
from .predict import ModeloIndisponivelError, prever_altura, series_crescimento
from .train import treinar

app = FastAPI(
    title="EcoTrack API",
    version="1.0.0",
    description=(
        "Monitoramento preditivo de crescimento de grama para otimizar o corte "
        "nas margens do Rodoanel (CCR Motiva)."
    ),
)

# CORS preserva o uso local atual; restrinja ECOTRACK_CORS_ORIGINS em producao.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ECOTRACK_CORS_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(create_chat_router())

# Cria a tabela de cortes e semeia o corte geral de referencia (07/08/2026 a
# 2 cm) na primeira subida. Em base ja populada, e um no-op.
inicializar_banco()


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
    # Novos campos (retrocompativeis: sempre presentes, mas so mudam o
    # comportamento de quem os le explicitamente).
    cor: str = Field(..., description="Classificacao operacional: verde | amarelo | vermelho")
    # So preenchido no modo "pior caso" (especie omitida na chamada): as 5
    # alturas do ponto, igual ao que /mapa/rodovia ja traz por celula.
    alturas_por_especie: dict[str, float] | None = None


class NovoCorte(BaseModel):
    """Registro de corte informado pela equipe de campo.

    Sem `latitude`/`longitude` o corte e GERAL (vale para toda a rodovia); com
    coordenada, vale so dentro de `raio_influencia_m` daquele ponto.
    """

    data_corte: dt.date = Field(..., description="Dia da roçada (AAAA-MM-DD)")
    altura_corte_cm: float = Field(
        ..., ge=0.0, le=ALTURA_CORTE_MAX_CM, description="Altura em que a grama ficou"
    )
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    raio_influencia_m: float | None = Field(
        None,
        gt=0,
        le=RAIO_CORTE_MAX_M,
        description=f"Alcance do corte por ponto (padrao {RAIO_CORTE_PADRAO_M:.0f} m)",
    )
    observacao: str | None = Field(None, max_length=500)


class Corte(BaseModel):
    id: int | None
    escopo: str
    latitude: float | None
    longitude: float | None
    raio_influencia_m: float | None
    data_corte: str
    altura_corte_cm: float
    observacao: str | None
    criado_em: str | None


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


def _predizer(
    latitude,
    longitude,
    raio_metros,
    especie,
    dias_desde_corte,
    dia,
    altura_inicial_cm: float = 0.0,
    alinhar_com_mapa: bool = False,
    clima_hoje=None,
):
    # /mapa/rodovia e /crescimento/serie janelam a partir do dia SEGUINTE ao
    # corte (a janela tem `dias_desde_corte` dias). Este endpoint sempre
    # janelou a partir do PROPRIO dia do corte (`dias_desde_corte + 1` dias)
    # -- um dia a mais de crescimento simulado. Isso nunca importou enquanto
    # a consulta era so hipotetica, mas passa a importar quando se quer
    # reproduzir o numero exato de um ponto real do mapa: dai o parametro
    # `alinhar_com_mapa`, que troca so a janela interna, sem mudar o
    # `dias_desde_corte` mostrado na resposta nem o comportamento de quem
    # nao pedir o alinhamento.
    dias_para_janela = max(dias_desde_corte - 1, 0) if alinhar_com_mapa else dias_desde_corte
    try:
        res = prever_altura(
            latitude,
            longitude,
            especie,
            dias_para_janela,
            dia,
            clima_hoje=clima_hoje,
            altura_inicial_cm=altura_inicial_cm,
        )
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
        cor=classificar_cor(res["altura_cm"]),
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
            "/crescimento/serie",
            "/historico/atualizar (POST)",
            "/previsao/gerar (POST)",
            "/previsao/status",
            "/pontos",
            "/especies",
            "/health",
            "/status/apis",
            "/chat (POST)",
            "/chat/stream (POST)",
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
    especie: str | None = Query(
        None,
        description=(
            "Especie exibida no mapa. Omitida = pior caso (a especie mais alta "
            "de cada trecho, criterio de disparo da rocada)."
        ),
    ),
):
    """Varre toda a rodovia em celulas de ~200 m e classifica cada uma por cor.

    verde = 1-15 cm · amarelo = 16-25 cm · vermelho = > 25 cm.

    As cinco especies convivem em todo trecho: cada celula traz
    `alturas_por_especie` com as cinco alturas, e `especie` escolhe qual delas
    colore o mapa.
    """
    dia = _parse_data(data)
    if especie is not None:
        _validar_especie(especie)
    try:
        return gerar_mapa_rodovia(espacamento_km=espacamento_km, dia=dia, especie=especie)
    except ModeloIndisponivelError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PrevisaoIndisponivelError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ---------------------------------------------------------------------------
# Registros de corte (banco operacional)
#
# E daqui que sai o ESTADO INICIAL do modelo de crescimento: quando cada trecho
# foi rocado e a que altura a grama ficou. Sem isso o mapa seria uma projecao
# hipotetica; com isso ele e o retrato da via.
# ---------------------------------------------------------------------------
@app.get("/cortes", response_model=list[Corte])
def cortes_listar():
    """Historico de cortes registrados, do mais recente para o mais antigo."""
    return listar_cortes()


@app.post("/cortes", response_model=Corte, status_code=201)
def cortes_registrar(corte: NovoCorte):
    """Registra um corte informado pela equipe.

    O registro nao sobrescreve nada: a tabela e um historico, e a resolucao
    escolhe qual corte vale em cada ponto (o mais recente; empatando a data,
    o mais especifico). Apagar um registro faz o anterior voltar a valer.
    """
    try:
        return registrar_corte(
            data_corte=corte.data_corte,
            altura_corte_cm=corte.altura_corte_cm,
            latitude=corte.latitude,
            longitude=corte.longitude,
            raio_influencia_m=corte.raio_influencia_m,
            observacao=corte.observacao,
        )
    except CorteInvalidoError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.delete("/cortes/{corte_id}", response_model=Corte)
def cortes_remover(corte_id: int):
    """Apaga um registro de corte (o anterior volta a valer naquele trecho)."""
    try:
        return remover_corte(corte_id)
    except CorteNaoEncontradoError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/cortes/vigente", response_model=Corte)
def cortes_vigente(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    data: str | None = Query(None, description="Data de referencia (padrao: hoje)"),
):
    """Qual corte o sistema esta usando como estado inicial neste ponto."""
    return corte_vigente(latitude, longitude, _parse_data(data))


@app.get("/crescimento/serie")
def crescimento_serie(
    inicio: str | None = Query(
        None,
        description=(
            "Data do corte AAAA-MM-DD. Omitida, usa o corte REGISTRADO para o "
            "ponto (GET /cortes/vigente)."
        ),
    ),
    fim: str | None = Query(None, description="Data final AAAA-MM-DD (padrao: +90 dias)"),
    latitude: float | None = Query(None, ge=-90, le=90),
    longitude: float | None = Query(None, ge=-180, le=180),
):
    """Altura dia a dia de cada especie, do corte ate a data final.

    Uma serie por especie sobre o mesmo eixo de tempo e o mesmo clima — e a
    comparacao direta entre elas, ja que todas convivem no mesmo trecho.

    O periodo e livre: `inicio` e a data do corte (pode estar no passado, e ai a
    janela usa o historico real) e `fim` o horizonte da projecao. Sem
    coordenada, usa o centro da regiao; com coordenada, e o ponto exato daquela
    celula do mapa.

    Omitindo `inicio`, o corte vem do banco: a data E a altura registradas para
    aquele ponto, as mesmas que o mapa usa. Informando `inicio`, a consulta e
    hipotetica e a altura inicial cai para a do corte registrado apenas se as
    datas coincidirem — caso contrario parte do solo (0 cm).
    """
    hoje = dt.date.today()
    lat = REGION_CENTER["latitude"] if latitude is None else latitude
    lon = REGION_CENTER["longitude"] if longitude is None else longitude

    corte = corte_vigente(lat, lon)
    data_corte_registrada = dt.date.fromisoformat(corte["data_corte"])
    data_inicio = _parse_data(inicio) or data_corte_registrada
    altura_inicial = (
        corte["altura_corte_cm"] if data_inicio == data_corte_registrada else 0.0
    )

    data_fim = _parse_data(fim) or data_inicio + dt.timedelta(days=90)
    if data_fim <= data_inicio:
        raise HTTPException(
            status_code=422, detail="a data final precisa ser posterior a data de corte"
        )
    # Limita a janela para nao extrapolar indefinidamente.
    data_fim = min(data_fim, data_inicio + dt.timedelta(days=MAX_DIAS_DESDE_CORTE))

    # A serie comeca no dia SEGUINTE ao corte (no dia do corte a grama esta na
    # altura em que ficou) — mesma convencao do mapa.
    inicio_janela = data_inicio + dt.timedelta(days=1)
    # A leitura ao vivo so entra se hoje estiver dentro da janela pedida.
    clima_hoje = (
        obter_clima(lat, lon, hoje) if inicio_janela <= hoje <= data_fim else None
    )

    try:
        resultado = series_crescimento(
            lat, lon, inicio_janela, data_fim, clima_hoje, altura_inicial_cm=altura_inicial
        )
    except ModeloIndisponivelError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PrevisaoIndisponivelError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    resultado["ponto"] = {"latitude": lat, "longitude": lon}
    resultado["inicio"] = data_inicio.isoformat()
    resultado["fim"] = data_fim.isoformat()
    resultado["especies"] = SPECIES_LIST
    resultado["altura_corte_recomendado_cm"] = ALTURA_CORTE_RECOMENDADO_CM
    resultado["altura_inicial_cm"] = altura_inicial
    resultado["corte"] = corte
    return resultado


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
    especie: str | None = Query(
        None,
        description=(
            "Especie de grama (ver /especies). Omitida, calcula as 5 e "
            "devolve a mais alta -- o mesmo criterio 'pior caso' do "
            "/mapa/rodovia -- com o detalhe das 5 em alturas_por_especie."
        ),
    ),
    dias_desde_corte: int = Query(30, ge=0, le=365),
    raio_metros: float = Query(500, gt=0),
    data: str | None = Query(None, description="Data AAAA-MM-DD (padrao: hoje)"),
    altura_inicial_cm: float = Query(
        0.0,
        ge=0.0,
        le=ALTURA_CORTE_MAX_CM,
        description=(
            "Altura em que a grama ficou no corte que abre a janela "
            "(padrao: 0 cm, corte hipotetico rente ao chao). Informe a "
            "altura de um corte real -- ver GET /cortes/vigente, ou o campo "
            "'corte' de uma celula de /mapa/rodovia -- para que o resultado "
            "reproduza exatamente o retrato do mapa naquele ponto."
        ),
    ),
    alinhar_com_mapa: bool = Query(
        False,
        description=(
            "Se True, a janela comeca no dia SEGUINTE ao corte -- mesma "
            "convencao de /mapa/rodovia e /crescimento/serie -- em vez do "
            "proprio dia do corte (comportamento padrao deste endpoint). "
            "Use junto com altura_inicial_cm vindo de uma celula real para "
            "o resultado bater exatamente com o mapa."
        ),
    ),
):
    """Retorna as Variaveis X (altura_cm + confianca) para um ponto arbitrario.

    Consulta HIPOTETICA por padrao (janela e altura inicial vem dos
    parametros, nao do banco de cortes) -- mesma logica de sempre. Passe
    `altura_inicial_cm` e `alinhar_com_mapa=true` para ancorar o resultado
    num corte real e reproduzir os numeros do mapa. Sem `especie`, avalia
    as 5 e devolve a mais alta.
    """
    dia = _parse_data(data)

    # /mapa/rodovia usa uma UNICA leitura ao vivo -- do CENTRO DA REGIAO,
    # nao do ponto clicado -- para "hoje" em toda a varredura (uma chamada
    # as APIs externas para centenas de celulas, nao uma por celula). Sem
    # repetir essa mesma escolha aqui, "hoje" desse endpoint usaria o clima
    # do proprio ponto consultado e o resultado nunca bateria exatamente
    # com o mapa quando a janela cobre o dia de hoje.
    clima_hoje = None
    if alinhar_com_mapa:
        hoje = dt.date.today()
        fim = dia or hoje
        dias_para_janela = max(dias_desde_corte - 1, 0)
        inicio = fim - dt.timedelta(days=dias_para_janela)
        if inicio <= hoje <= fim:
            try:
                clima_hoje = obter_clima(
                    REGION_CENTER["latitude"], REGION_CENTER["longitude"], hoje
                )
            except PrevisaoIndisponivelError as exc:
                raise HTTPException(status_code=422, detail=str(exc))

    if especie is not None:
        _validar_especie(especie)
        return _predizer(
            latitude,
            longitude,
            raio_metros,
            especie,
            dias_desde_corte,
            dia,
            altura_inicial_cm=altura_inicial_cm,
            alinhar_com_mapa=alinhar_com_mapa,
            clima_hoje=clima_hoje,
        )

    # Modo "pior caso": mesma regra do mapa -- avalia as 5 especies e
    # devolve a mais alta, com o detalhe de todas em alturas_por_especie.
    resultados = {
        nome: _predizer(
            latitude,
            longitude,
            raio_metros,
            nome,
            dias_desde_corte,
            dia,
            altura_inicial_cm=altura_inicial_cm,
            alinhar_com_mapa=alinhar_com_mapa,
            clima_hoje=clima_hoje,
        )
        for nome in SPECIES_LIST
    }
    vencedora = max(resultados, key=lambda nome: resultados[nome].previsao.altura)
    resposta = resultados[vencedora]
    resposta.alturas_por_especie = {
        nome: r.previsao.altura for nome, r in resultados.items()
    }
    return resposta


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