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

O ESTADO INICIAL VEM DO BANCO
-----------------------------
Antes o mapa assumia que a rodovia inteira tinha sido cortada HOJE, a zero cm,
e a data escolhida era so um horizonte hipotetico. Agora cada celula parte do
corte que a equipe registrou para ela (src/db.py): a data em que aquele trecho
foi rocado e a altura em que a grama ficou. Celulas com cortes diferentes tem
janelas de crescimento diferentes no mesmo mapa -- que e exatamente o retrato
operacional que se quer, com os trechos cortados ha mais tempo aparecendo mais
altos.

A altura de cada celula vem do modelo agronomico (growth.py), simulando dia a
dia sob o clima da janela [corte, data-alvo]: dias passados usam o historico
REAL coletado das APIs, hoje usa a leitura ao vivo e dias futuros usam o clima
PREVISTO pelo modelo climatico treinado. As celulas do mapa sao agrupadas nas
celulas CLIMATICAS (~11 km) coletadas no historico, entao ha variacao espacial
de clima ao longo do anel.
"""

from __future__ import annotations

import datetime as dt
import math

from .config import (
    RAIO_CELULA_M,
    REGION_CENTER,
    RODOVIA_ROTA,
    SPECIES_LIST,
    classificar_cor,
)
from .db import dias_desde_corte as _dias_desde_corte, resolver_cortes
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

    Cada celula parte do CORTE REGISTRADO para ela no banco (src/db.py): a
    janela de crescimento vai do dia seguinte ao corte ate a data-alvo, e a
    simulacao comeca na altura em que a grama ficou naquele corte. Celulas com
    cortes diferentes tem janelas diferentes na mesma varredura.

    A data-alvo (`dia`) e o horizonte: sem ela, o mapa mostra a via HOJE; com
    uma data futura, mostra como estaria naquele dia se nao houver novo corte.
    A altura e simulada dia a dia — passado com historico real, futuro com o
    clima previsto — e por construcao nunca diminui ao alargar o horizonte (o
    incremento diario e nao-negativo).

    `especie` seleciona qual especie o mapa representa. Sem ela, cada celula
    fica com a especie mais alta daquele trecho (criterio operacional de corte).
    """
    hoje = dt.date.today()
    alvo = dia or hoje
    coords = _pontos_ao_longo(RODOVIA_ROTA, espacamento_km)
    grupos_por_celula = [grupo_climatico(lat, lon) for lat, lon in coords]

    # Corte vigente em cada celula (uma leitura do banco para a varredura toda).
    cortes = resolver_cortes(coords, referencia=hoje)
    dias_por_celula = [_dias_desde_corte(corte, alvo) for corte in cortes]
    # Janela de cada celula: [corte + 1 dia, alvo]. Zero dia decorrido (a
    # data-alvo e a do proprio corte, ou anterior) dispensa simulacao — a grama
    # esta na altura em que ficou.
    inicios = [
        alvo - dt.timedelta(days=dias - 1) if dias > 0 else None
        for dias in dias_por_celula
    ]

    # Uma janela climatica por (data de corte, celula CLIMATICA de ~11 km);
    # dentro dela, um resultado por espécie — reutilizado por todas as celulas
    # do mapa naquela combinacao. Todas as especies sao simuladas sempre: e
    # barato (a janela ja esta montada) e permite mostrar o trecho inteiro no
    # popup sem nova requisicao.
    grupos_por_inicio: dict[dt.date, set] = {}
    for grupo, inicio in zip(grupos_por_celula, inicios):
        if inicio is not None:
            grupos_por_inicio.setdefault(inicio, set()).add(grupo)

    clima_hoje = (
        obter_clima(REGION_CENTER["latitude"], REGION_CENTER["longitude"], hoje)
        if any(inicio is not None and inicio <= hoje <= alvo for inicio in inicios)
        else None
    )
    janelas_por_inicio = {
        inicio: montar_clima_janelas(sorted(grupos), inicio, alvo, clima_hoje)
        for inicio, grupos in grupos_por_inicio.items()
    }

    cache_pred: dict[tuple, dict] = {}

    def _predizer(grupo, inicio, altura_corte_cm, nome) -> dict:
        if inicio is None:
            return {
                "altura_cm": round(float(altura_corte_cm), 1),
                "confianca": 1.0,
                "std_cm": 0.0,
                "fatores_medios": {},
            }
        chave = (grupo, inicio, altura_corte_cm, nome)
        if chave not in cache_pred:
            cache_pred[chave] = prever_crescimento_janela(
                janelas_por_inicio[inicio][grupo], nome, altura_inicial_cm=altura_corte_cm
            )
        return cache_pred[chave]

    if janelas_por_inicio:
        exemplo = next(iter(next(iter(janelas_por_inicio.values())).values()))
        fonte_clima = "+".join(
            f"{nome}({n}d)" for nome, n in exemplo["fontes"].items() if n > 0
        )
    else:
        fonte_clima = "sem-janela (corte na data-alvo)"

    resumo = {"verde": 0, "amarelo": 0, "vermelho": 0}
    acum_por_especie = {
        nome: {"soma_altura": 0.0, "altura_max": 0.0, "verde": 0, "amarelo": 0, "vermelho": 0}
        for nome in SPECIES_LIST
    }
    celulas = []
    for (lat, lon), grupo, corte, dias, inicio in zip(
        coords, grupos_por_celula, cortes, dias_por_celula, inicios
    ):
        altura_corte = corte["altura_corte_cm"]
        preds = {
            nome: _predizer(grupo, inicio, altura_corte, nome) for nome in SPECIES_LIST
        }
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
                "dias_desde_corte": dias,
                "cor": cor,
                "alturas_por_especie": alturas,
                # Estado inicial de onde esta celula partiu (registro do banco).
                "corte": {
                    "id": corte["id"],
                    "escopo": corte["escopo"],
                    "data_corte": corte["data_corte"],
                    "altura_corte_cm": corte["altura_corte_cm"],
                    "observacao": corte["observacao"],
                },
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

    # Os cortes distintos que aparecem na varredura, do mais recente ao mais
    # antigo — e o que o painel usa para dizer de onde veio o estado inicial.
    cortes_vigentes = {}
    for corte, dias in zip(cortes, dias_por_celula):
        chave = (corte["id"], corte["data_corte"], corte["altura_corte_cm"])
        registro = cortes_vigentes.setdefault(
            chave,
            {
                "id": corte["id"],
                "escopo": corte["escopo"],
                "data_corte": corte["data_corte"],
                "altura_corte_cm": corte["altura_corte_cm"],
                "observacao": corte["observacao"],
                "dias_desde_corte": dias,
                "celulas": 0,
            },
        )
        registro["celulas"] += 1

    return {
        "rota": [[lat, lon] for lat, lon in RODOVIA_ROTA],
        "celulas": celulas,
        "total_celulas": len(celulas),
        "raio_metros": RAIO_CELULA_M,
        "resumo": resumo,
        "confianca_media": round(confianca_media, 3),
        "fonte_clima": fonte_clima,
        "data": alvo.isoformat(),
        # Agora cada celula tem o seu; estes sao os extremos da varredura.
        "dias_desde_corte": max(dias_por_celula, default=0),
        "dias_desde_corte_min": min(dias_por_celula, default=0),
        "cortes_vigentes": sorted(
            cortes_vigentes.values(), key=lambda c: c["data_corte"], reverse=True
        ),
        "especie_selecionada": especie,
        "modo": "especie" if especie else "pior-caso",
        "especies_disponiveis": SPECIES_LIST,
        "resumo_por_especie": resumo_por_especie,
    }
