"""Inferencia: clima por dia da janela + altura pela formula agronomica.

Papeis (arquitetura atual):
  * Modelo ML autorregressivo (climate_model.joblib): preve o clima do dia
    seguinte a partir dos dias passados; a previsao recursiva de 365 dias para
    todas as celulas fica materializada em data/climate_forecast.csv
    (src/forecast.py, gerado pelo botao do painel).
  * Formula agronomica (src/growth.py): calcula a altura da grama acumulando,
    dia a dia, a taxa de crescimento sob o clima de cada dia da janela
    [corte, data-alvo].

Origem do clima de cada dia da janela (SOMENTE dados reais ou do modelo — a
climatologia generica NAO entra no calculo de altura):
  * hoje               -> leitura ao vivo das APIs (obter_clima), se fornecida;
  * dia passado        -> historico REAL coletado das APIs (CSV);
  * dia futuro         -> previsao recursiva do modelo (climate_forecast.csv);
  * sem dado disponivel-> erro (PrevisaoIndisponivelError): gere/atualize a
                          previsao pelo botao do painel.

Confianca:
  O CSV de previsao guarda, por dia/variavel, o desvio-padrao entre as arvores
  do ensemble. Essa incerteza e propagada pela formula: alturas calculadas com
  clima medio +/- std delimitam a faixa, e std_cm = (alta - baixa) / 2 vira
  confianca = 1 / (1 + std/escala). Janelas so com dados reais tem confianca
  proxima de 1.
"""

from __future__ import annotations

import datetime as dt

import numpy as np

from .config import CLIMATE_TARGETS, GRASS_SPECIES, MODEL_PATH
from .forecast import PrevisaoIndisponivelError, serie_prevista
from .growth import altura_acumulada, taxa_crescimento_diaria
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


def _taxas_de_valores(especie: str, valores: np.ndarray) -> list[float]:
    return [
        taxa_crescimento_diaria(especie, *(float(x) for x in linha))
        for linha in valores
    ]


def prever_crescimento_janela(janela: dict, especie: str) -> dict:
    """Altura + confianca de uma especie para uma janela ja montada.

    Altura: acumulo diario das taxas sob o clima central.
    Confianca: a incerteza do clima previsto (std por dia/variavel) e propagada
    pela formula — cada dia previsto contribui com meia-faixa de taxa
    (clima +/- std); os erros diarios sao tratados como independentes (soma em
    quadratura) e atenuados pela saturacao logistica.
    """
    valores = janela["valores"]
    std = janela["std"]
    taxas = _taxas_de_valores(especie, valores)
    altura = altura_acumulada(especie, taxas)

    if janela["fontes"]["modelo-clima"] > 0 and np.any(std > 0):
        idx_nao_neg = [i for i, v in enumerate(CLIMATE_TARGETS) if v != "temperatura_c"]
        alto = valores + std
        baixo = valores - std
        baixo[:, idx_nao_neg] = np.clip(baixo[:, idx_nao_neg], 0.0, None)
        taxas_alto = np.array(_taxas_de_valores(especie, alto))
        taxas_baixo = np.array(_taxas_de_valores(especie, baixo))
        deltas = np.abs(taxas_alto - taxas_baixo) / 2.0  # meia-faixa por dia
        std_soma = float(np.sqrt(np.sum(deltas**2)))
        # dh/dS da logistica h = h_max (1 - exp(-S/h_max)): perto da altura
        # maxima, variacoes na soma de taxas quase nao mudam a altura.
        h_max = GRASS_SPECIES[especie]["altura_max_cm"]
        soma = sum(max(t, 0.0) for t in taxas)
        std_cm = float(np.exp(-soma / h_max)) * std_soma
    else:
        std_cm = 0.0

    return {
        "altura_cm": round(float(altura), 1),
        "confianca": round(_confianca_from_std(std_cm), 3),
        "std_cm": round(std_cm, 2),
    }


def prever_altura(
    latitude: float,
    longitude: float,
    especie: str,
    dias_desde_corte: int,
    dia: dt.date | None = None,
    clima_hoje=None,
) -> dict:
    """Preve a altura da grama e a confianca para um ponto/condicao.

    A janela de crescimento e [dia - dias_desde_corte, dia]: dias passados
    usam o historico real, dias futuros usam a previsao recursiva do modelo.
    """
    from .ingest import obter_clima

    fim = dia or dt.date.today()
    inicio = fim - dt.timedelta(days=dias_desde_corte)
    hoje = dt.date.today()
    if clima_hoje is None and inicio <= hoje <= fim:
        clima_hoje = obter_clima(latitude, longitude, hoje)

    janela = montar_clima_janela(latitude, longitude, inicio, fim, clima_hoje)
    res = prever_crescimento_janela(janela, especie)
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
