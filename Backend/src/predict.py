"""Inferencia: clima por dia da janela + altura pela formula agronomica.

Papeis (arquitetura atual):
  * Modelo ML autorregressivo (climate_model.joblib): preve o clima do dia
    seguinte a partir dos dias passados; a previsao recursiva de 365 dias para
    todas as celulas fica materializada em data/climate_forecast.csv
    (src/forecast.py, gerado pelo botao do painel).
  * Modelo agronomico (src/growth.py): simula a altura da grama dia a dia sob
    o clima de cada dia da janela [corte, data-alvo], com balanco de agua no
    solo e dossel proprios de CADA especie. Duas especies no mesmo ponto e na
    mesma janela chegam a alturas diferentes — e essa diferenca e o que o mapa
    mostra quando se troca a especie selecionada.

Origem do clima de cada dia da janela (SOMENTE dados reais ou do modelo — a
climatologia generica NAO entra no calculo de altura):
  * hoje               -> leitura ao vivo das APIs (obter_clima), se fornecida;
  * dia passado        -> historico REAL coletado das APIs (CSV);
  * dia futuro         -> previsao recursiva do modelo (climate_forecast.csv);
  * sem dado disponivel-> erro (PrevisaoIndisponivelError): gere/atualize a
                          previsao pelo botao do painel.

Confianca:
  O CSV de previsao guarda, por dia/variavel, o desvio-padrao entre as arvores
  do ensemble. Essa incerteza e propagada re-simulando o crescimento com o
  clima nas bordas (+/- std); a meia-faixa resultante, reduzida a hipotese de
  erros diarios independentes, vira confianca = 1 / (1 + std/escala). Janelas
  so com dados reais tem confianca proxima de 1.
"""

from __future__ import annotations

import datetime as dt

import numpy as np

from .config import CLIMATE_TARGETS, MODEL_PATH, SPECIES_LIST
from .forecast import PrevisaoIndisponivelError, serie_prevista
from .growth import simular_crescimento
from .historico import serie_historica

# Escala de calibracao da confianca (cm de desvio-padrao propagado).
_ESCALA_CONFIANCA_CM = 8.0


class ModeloIndisponivelError(RuntimeError):
    """Modelo ainda nao treinado / arquivo ausente."""


def _exigir_modelo() -> None:
    if not MODEL_PATH.exists():
        raise ModeloIndisponivelError(
            f"Modelo nao encontrado em {MODEL_PATH}. Rode: python -m scripts.build_pipeline"
        )


def _confianca_from_std(std_cm: float) -> float:
    return float(1.0 / (1.0 + (std_cm / _ESCALA_CONFIANCA_CM)))


def montar_clima_janelas(
    pontos: list[tuple[float, float]],
    inicio: dt.date,
    fim: dt.date,
    clima_hoje=None,
) -> dict[tuple[float, float], dict]:
    """Monta o clima diario da janela [inicio, fim] para varios pontos.

    Retorna, por ponto, um dicionario com:
      valores : ndarray (n_dias, n_vars) — clima central de cada dia
      std     : ndarray (n_dias, n_vars) — incerteza (so dias previstos)
      fontes  : contagem de dias por origem (historico-real, ao-vivo,
                modelo-clima)

    So dados reais (historico/ao vivo) e previsoes do modelo entram no
    calculo; um dia sem cobertura gera PrevisaoIndisponivelError.
    """
    _exigir_modelo()
    hoje = dt.date.today()
    datas = [inicio + dt.timedelta(days=i) for i in range((fim - inicio).days + 1)]
    n_vars = len(CLIMATE_TARGETS)

    janelas = {}
    for lat, lon in pontos:
        valores = np.zeros((len(datas), n_vars))
        std = np.zeros((len(datas), n_vars))
        fontes = {"historico-real": 0, "ao-vivo": 0, "modelo-clima": 0}

        hist = serie_historica(lat, lon, datas)
        prev = serie_prevista(lat, lon, [d for d in datas if d not in hist])
        for i, d in enumerate(datas):
            if clima_hoje is not None and d == hoje:
                valores[i] = [getattr(clima_hoje, v) for v in CLIMATE_TARGETS]
                fontes["ao-vivo"] += 1
            elif d in hist:
                valores[i] = [hist[d][v] for v in CLIMATE_TARGETS]
                fontes["historico-real"] += 1
            elif d in prev:
                valores[i] = [prev[d][v] for v in CLIMATE_TARGETS]
                std[i] = [prev[d][f"std_{v}"] for v in CLIMATE_TARGETS]
                fontes["modelo-clima"] += 1
            else:
                raise PrevisaoIndisponivelError(
                    f"Sem clima real nem previsto para {d.isoformat()}: a "
                    "previsao do modelo nao cobre esta data. Gere/atualize a "
                    "previsao (botao 'Gerar previsao climatica' do painel ou "
                    "POST /previsao/gerar) ou escolha uma data dentro do "
                    "periodo coberto (GET /previsao/status)."
                )

        janelas[(lat, lon)] = {
            "valores": valores,
            "std": std,
            "fontes": fontes,
            "datas": datas,
        }
    return janelas


def montar_clima_janela(
    latitude: float,
    longitude: float,
    inicio: dt.date,
    fim: dt.date,
    clima_hoje=None,
) -> dict:
    """Janela climatica de um unico ponto (atalho de montar_clima_janelas)."""
    return montar_clima_janelas([(latitude, longitude)], inicio, fim, clima_hoje)[
        (latitude, longitude)
    ]


def prever_crescimento_janela(
    janela: dict, especie: str, altura_inicial_cm: float = 0.0
) -> dict:
    """Altura + confianca de uma especie para uma janela ja montada.

    `altura_inicial_cm` e a altura em que a grama ficou no corte que abre a
    janela -- vem do registro de corte da equipe (src/db.py). O default zero
    mantem o comportamento de quem chama sem informar (corte rente ao solo).

    Altura: simulacao agronomica dia a dia (src/growth.py) sob o clima central
    da janela, carregando agua no solo e altura do dossel de um dia para o
    outro.

    Confianca: a incerteza do clima previsto (std por dia/variavel) e propagada
    RODANDO A SIMULACAO nas bordas — uma vez com clima+std e outra com
    clima-std. Isso captura a nao-linearidade do modelo (saturacao do dossel,
    esgotamento do solo) sem precisar derivar a formula. Como esse envelope
    supoe que todos os dias erram para o mesmo lado, ele e a cota superior; a
    meia-faixa e convertida para a hipotese de erros diarios INDEPENDENTES
    (a mesma do modelo anterior) dividindo por sqrt(dias previstos) — a razao
    entre somar n desvios linearmente e soma-los em quadratura.
    """
    valores = janela["valores"]
    std = janela["std"]
    dias_previstos = janela["fontes"]["modelo-clima"]

    sim = simular_crescimento(especie, valores, altura_inicial_cm=altura_inicial_cm)
    altura = sim["altura_cm"]

    if dias_previstos > 0 and np.any(std > 0):
        idx_nao_neg = [i for i, v in enumerate(CLIMATE_TARGETS) if v != "temperatura_c"]
        alto = valores + std
        baixo = valores - std
        baixo[:, idx_nao_neg] = np.clip(baixo[:, idx_nao_neg], 0.0, None)
        altura_alta = simular_crescimento(
            especie, alto, altura_inicial_cm=altura_inicial_cm
        )["altura_cm"]
        altura_baixa = simular_crescimento(
            especie, baixo, altura_inicial_cm=altura_inicial_cm
        )["altura_cm"]
        meia_faixa = abs(altura_alta - altura_baixa) / 2.0
        std_cm = float(meia_faixa / np.sqrt(dias_previstos))
    else:
        std_cm = 0.0

    return {
        "altura_cm": round(float(altura), 1),
        "confianca": round(_confianca_from_std(std_cm), 3),
        "std_cm": round(std_cm, 2),
        "fatores_medios": sim["fatores_medios"],
    }


def series_crescimento(
    latitude: float,
    longitude: float,
    inicio: dt.date,
    fim: dt.date,
    clima_hoje=None,
    altura_inicial_cm: float = 0.0,
) -> dict:
    """Altura dia a dia de TODAS as especies num ponto, para a janela dada.

    Alimenta o grafico de tendencia do painel: uma linha por especie sobre o
    mesmo eixo de tempo e o mesmo clima, que e a comparacao honesta entre elas
    (todas convivem no mesmo trecho). A janela e montada uma unica vez e
    reaproveitada pelas cinco simulacoes.

    `altura_inicial_cm` e a altura deixada pelo corte que abre a janela: as
    cinco linhas partem dela, nao de zero.
    """
    janela = montar_clima_janela(latitude, longitude, inicio, fim, clima_hoje)
    datas = janela["datas"]
    series = {
        nome: [
            round(altura, 2)
            for altura in simular_crescimento(
                nome, janela["valores"], altura_inicial_cm=altura_inicial_cm
            )["serie_altura_cm"]
        ]
        for nome in SPECIES_LIST
    }
    partes = [f"{nome}({n}d)" for nome, n in janela["fontes"].items() if n > 0]
    return {
        "datas": [d.isoformat() for d in datas],
        "series": series,
        "fonte_clima": "+".join(partes) if partes else "vazio",
        "dias": len(datas),
    }


def prever_altura(
    latitude: float,
    longitude: float,
    especie: str,
    dias_desde_corte: int,
    dia: dt.date | None = None,
    clima_hoje=None,
    altura_inicial_cm: float = 0.0,
) -> dict:
    """Preve a altura da grama e a confianca para um ponto/condicao.

    A janela de crescimento e [dia - dias_desde_corte, dia]: dias passados
    usam o historico real, dias futuros usam a previsao recursiva do modelo.

    Consulta HIPOTETICA: o periodo vem do parametro, nao do banco de cortes.
    Serve para responder "e se fizesse N dias desde o corte?". O retrato real
    da via (que le os cortes registrados) e o de /mapa/rodovia.
    """
    from .ingest import obter_clima

    fim = dia or dt.date.today()
    inicio = fim - dt.timedelta(days=dias_desde_corte)
    hoje = dt.date.today()
    if clima_hoje is None and inicio <= hoje <= fim:
        clima_hoje = obter_clima(latitude, longitude, hoje)

    janela = montar_clima_janela(latitude, longitude, inicio, fim, clima_hoje)
    res = prever_crescimento_janela(janela, especie, altura_inicial_cm=altura_inicial_cm)
    res["clima"] = resumo_clima_janela(janela, latitude, longitude, fim)
    return res


def resumo_clima_janela(janela: dict, latitude: float, longitude: float, fim: dt.date):
    """Leitura media da janela, com resumo legivel das fontes usadas."""
    from .clients import ClimateReading

    medias = janela["valores"].mean(axis=0)
    partes = [f"{nome}({n}d)" for nome, n in janela["fontes"].items() if n > 0]
    return ClimateReading(
        data=fim,
        latitude=latitude,
        longitude=longitude,
        fonte="+".join(partes) if partes else "vazio",
        fontes={v: "media-da-janela" for v in CLIMATE_TARGETS},
        **{v: float(m) for v, m in zip(CLIMATE_TARGETS, medias)},
    )
