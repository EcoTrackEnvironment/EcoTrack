"""Varredura operacional da rodovia em celulas de ~200 m.

Gera pontos espacados ao longo do laco do Rodoanel (config.RODOVIA_ROTA, linha
central real do SP-021 extraida do OpenStreetMap), a cada ~200 m (para que os
raios de 100 m cubram a via de forma contigua), e estima a altura da grama em
cada um, classificando-o por cor:

  verde   -> 1 a 15 cm
  amarelo -> 16 a 25 cm
  vermelho -> > 25 cm

TODAS as especies convivem em TODO trecho
-----------------------------------------
A versao anterior sorteava uma especie por celula (pseudo-aleatorio porem
deterministico). Isso nao corresponde ao campo: na margem do Rodoanel as
especies crescem juntas, misturadas, no mesmo ponto. Agora cada celula e
avaliada para as CINCO especies, e o consumidor escolhe o que quer ver:

  * `especie=<nome>`  -> o mapa mostra como aquela especie especifica esta
                         naquele trecho (e o que alimenta o dropdown do
                         painel);
  * sem `especie`     -> modo "pior caso": cada celula recebe a MAIOR altura
                         entre as especies presentes, que e o criterio
                         operacional real -- a roçada e disparada pela grama
                         mais alta do trecho, nao pela media.

Em ambos os modos cada celula carrega `alturas_por_especie` com as cinco
alturas, entao o painel consegue mostrar o trecho inteiro sem nova requisicao.

A altura de cada celula vem do modelo agronomico (growth.py), simulando dia a
dia sob o clima da janela [hoje, data-alvo]: dias passados usam o historico
REAL coletado das APIs, hoje usa a leitura ao vivo e dias futuros usam o clima
PREVISTO pelo modelo climatico treinado. As celulas do mapa sao agrupadas nas
celulas CLIMATICAS (~11 km) coletadas no historico, entao ha variacao espacial
de clima ao longo do anel.
"""

from __future__ import annotations

import datetime as dt
import math

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
    especie: str | None = None,
) -> dict:
    """Varre a rodovia e retorna rota + celulas classificadas por cor.

    A data e tratada como HORIZONTE DE PROJECAO: o "dias desde o ultimo corte" e
    o tempo decorrido entre hoje e a data escolhida (assumindo o ultimo corte
    hoje), aplicado igualmente a TODAS as celulas. Assim, escolher uma data 1 ano
    a frente testa toda a rodovia como se nao houvesse corte por 1 ano. A
    altura e simulada dia a dia (modelo agronomico): passado com historico real,
    futuro com o clima previsto pelo modelo — e por construcao nunca diminui ao
    alargar o horizonte (o incremento diario e nao-negativo).

    `especie` seleciona qual especie o mapa representa. Sem ela, cada celula
    fica com a especie mais alta daquele trecho (criterio operacional de corte).
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

    # Uma janela climatica por celula CLIMATICA (~11 km); dentro dela, um
    # resultado por especie — reutilizado por todas as celulas do mapa daquele
    # grupo. Todas as especies sao simuladas sempre: e barato (a janela ja esta
    # montada) e permite mostrar o trecho inteiro no popup.
    grupos_por_celula = [grupo_climatico(lat, lon) for lat, lon in coords]
    janelas = montar_clima_janelas(
        sorted(set(grupos_por_celula)), inicio_janela, fim_janela, clima_hoje
    )
    cache_pred: dict[tuple, dict] = {}
    for grupo, janela in janelas.items():
        for nome in SPECIES_LIST:
            cache_pred[(grupo, nome)] = prever_crescimento_janela(janela, nome)

    exemplo = next(iter(janelas.values()))
    fonte_clima = "+".join(
        f"{nome}({n}d)" for nome, n in exemplo["fontes"].items() if n > 0
    )

    resumo = {"verde": 0, "amarelo": 0, "vermelho": 0}
    acum_por_especie = {
        nome: {"soma_altura": 0.0, "altura_max": 0.0, "verde": 0, "amarelo": 0, "vermelho": 0}
        for nome in SPECIES_LIST
    }
    celulas = []
    for (lat, lon), grupo in zip(coords, grupos_por_celula):
        preds = {nome: cache_pred[(grupo, nome)] for nome in SPECIES_LIST}
        alturas = {nome: preds[nome]["altura_cm"] for nome in SPECIES_LIST}

        # Especie exibida: a escolhida ou, no modo pior caso, a mais alta.
        exibida = especie or max(alturas, key=alturas.get)
        pred = preds[exibida]
        cor = classificar_cor(pred["altura_cm"])
        resumo[cor] += 1

        for nome, altura in alturas.items():
            acumulado = acum_por_especie[nome]
            acumulado["soma_altura"] += altura
            acumulado["altura_max"] = max(acumulado["altura_max"], altura)
            acumulado[classificar_cor(altura)] += 1

        celulas.append(
            {
                "latitude": round(lat, 5),
                "longitude": round(lon, 5),
                "raio_metros": RAIO_CELULA_M,
                "altura_cm": pred["altura_cm"],
                "confianca": pred["confianca"],
                "especie": exibida,
                "dias_desde_corte": dias_desde_corte,
                "cor": cor,
                "alturas_por_especie": alturas,
            }
        )

    confianca_media = (
        sum(c["confianca"] for c in celulas) / len(celulas) if celulas else 0.0
    )
    n = len(celulas) or 1
    resumo_por_especie = {
        nome: {
            "altura_media_cm": round(dados["soma_altura"] / n, 1),
            "altura_max_cm": round(dados["altura_max"], 1),
            "verde": dados["verde"],
            "amarelo": dados["amarelo"],
            "vermelho": dados["vermelho"],
        }
        for nome, dados in acum_por_especie.items()
    }

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
        "especie_selecionada": especie,
        "modo": "especie" if especie else "pior-caso",
        "especies_disponiveis": SPECIES_LIST,
        "resumo_por_especie": resumo_por_especie,
    }
