"""Formula agronomica de crescimento de grama.

Como nao existem dados historicos reais de crescimento de grama para o
Rodoanel, este modulo implementa uma relacao *plausivel* entre variaveis
climaticas e a taxa de crescimento diario da grama. E ELA que calcula a altura
servida pela API: a taxa diaria e acumulada ao longo da janela desde o corte,
alimentada com clima real (historico/ao vivo) e com o clima futuro previsto
pelo modelo de machine learning (src/train.py).

Premissas (documentadas no README):

1. Gramineas de margem de rodovia em SP sao majoritariamente C4 tropicais,
   com otimo termico alto (25-35 C). Usa-se uma resposta termica triangular:
   crescimento zero abaixo de temp_min e acima de temp_max, maximo em
   temp_otima.

2. Agua: crescimento cresce com a umidade do solo (aproximada por precipitacao
   recente + umidade do ar), saturando em excesso e caindo sob deficit hidrico.

3. Radiacao (PAR): a fotossintese responde de forma saturante a radiacao solar
   global; usa-se uma curva de Michaelis-Menten (meia-saturacao ~12 MJ/m2/dia).

4. Vento: ventos fortes aumentam a evapotranspiracao e reduzem levemente o
   crescimento efetivo.

5. A altura sem corte segue um acumulo logistico limitado por altura_max da
   especie (a grama nao cresce indefinidamente).

Todas as constantes sao estimativas de engenharia, calibradas para produzir
alturas realistas (0 a ~altura_max cm) e nao pretendem substituir medicoes de
campo.
"""

from __future__ import annotations

import numpy as np

from .config import GRASS_SPECIES


def fator_temperatura(temp_c: float, especie: dict) -> float:
    """Resposta termica triangular normalizada em [0, 1]."""
    t_min = especie["temp_min_c"]
    t_max = especie["temp_max_c"]
    t_opt = especie["temp_otima_c"]
    if temp_c <= t_min or temp_c >= t_max:
        return 0.0
    if temp_c <= t_opt:
        return (temp_c - t_min) / (t_opt - t_min)
    return (t_max - temp_c) / (t_max - t_opt)


def fator_agua(precipitacao_mm: float, umidade_pct: float) -> float:
    """Disponibilidade hidrica normalizada em [0, 1].

    Combina precipitacao recente (proxy de umidade do solo) com a umidade
    relativa do ar. Satura em ~20 mm/dia e penaliza umidade do ar muito baixa
    (deficit hidrico atmosferico).
    """
    # Componente de precipitacao: saturante.
    f_precip = precipitacao_mm / (precipitacao_mm + 8.0)  # ~0.71 em 20 mm
    # Componente de umidade do ar: cresce a partir de ~30%.
    f_umid = np.clip((umidade_pct - 30.0) / 50.0, 0.0, 1.0)
    # Media ponderada (solo pesa mais que ar).
    return float(np.clip(0.65 * f_precip + 0.35 * f_umid, 0.0, 1.0))


def fator_radiacao(radiacao_mj_m2: float) -> float:
    """Resposta saturante (Michaelis-Menten) a radiacao solar global.

    Meia-saturacao em ~12 MJ/m2/dia. PAR ~ 45% da radiacao global.
    """
    k = 12.0
    return float(radiacao_mj_m2 / (radiacao_mj_m2 + k))


def fator_vento(vento_kmh: float) -> float:
    """Penalizacao leve por vento forte (maior evapotranspiracao)."""
    return float(np.clip(1.0 - 0.006 * max(vento_kmh - 10.0, 0.0), 0.7, 1.0))


def taxa_crescimento_diaria(
    especie_nome: str,
    temperatura_c: float,
    precipitacao_mm: float,
    umidade_pct: float,
    radiacao_mj_m2: float,
    vento_kmh: float,
) -> float:
    """Taxa de crescimento em cm/dia para um dia com as condicoes dadas."""
    especie = GRASS_SPECIES[especie_nome]
    taxa = (
        especie["taxa_base_cm_dia"]
        * fator_temperatura(temperatura_c, especie)
        * fator_agua(precipitacao_mm, umidade_pct)
        * fator_radiacao(radiacao_mj_m2)
        * fator_vento(vento_kmh)
    )
    return float(max(taxa, 0.0))


def altura_acumulada(especie_nome: str, taxas_diarias: list[float]) -> float:
    """Altura (cm) acumulando taxas diarias REAIS (uma por dia desde o corte).

    Mesmo acumulo logistico de `altura_estimada`, mas integrando dia a dia com
    o clima de cada dia (historico real ou previsto pelo modelo climatico), em
    vez de assumir um unico clima constante no periodo.
    """
    especie = GRASS_SPECIES[especie_nome]
    h_max = especie["altura_max_cm"]
    soma = float(sum(max(t, 0.0) for t in taxas_diarias))
    if soma <= 0:
        return 0.0
    altura = h_max * (1.0 - np.exp(-soma / h_max))
    return float(np.clip(altura, 0.0, h_max))


def altura_estimada(
    especie_nome: str,
    dias_desde_corte: float,
    temperatura_c: float,
    precipitacao_mm: float,
    umidade_pct: float,
    radiacao_mj_m2: float,
    vento_kmh: float,
) -> float:
    """Altura (cm) acumulada desde o ultimo corte.

    Modela o crescimento como acumulo logistico: a taxa diaria estimada e
    aplicada ao longo de `dias_desde_corte`, mas saturando na altura maxima da
    especie (crescimento desacelera perto do limite).
    """
    especie = GRASS_SPECIES[especie_nome]
    taxa = taxa_crescimento_diaria(
        especie_nome,
        temperatura_c,
        precipitacao_mm,
        umidade_pct,
        radiacao_mj_m2,
        vento_kmh,
    )
    h_max = especie["altura_max_cm"]
    if taxa <= 0:
        return 0.0
    # Aproximacao logistica: altura tende a h_max com meia-vida ~ h_max/taxa.
    altura = h_max * (1.0 - np.exp(-taxa * dias_desde_corte / h_max))
    return float(np.clip(altura, 0.0, h_max))
