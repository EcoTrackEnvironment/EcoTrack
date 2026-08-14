"""Modelo agronomico de crescimento de grama, POR ESPECIE.

Observacao de campo que motiva este modulo: no Rodoanel as especies crescem
TODAS JUNTAS no mesmo trecho. Nao faz sentido "sortear" uma especie por
segmento -- o que muda de uma para a outra e o quanto cada uma cresce sob o
mesmo clima. Por isso cada especie tem aqui o seu proprio calculo, e nao apenas
uma taxa base diferente multiplicando as mesmas curvas.

O que mudou em relacao ao modelo anterior
-----------------------------------------
1. **Estado, nao media.** Antes cada dia era independente: a taxa do dia saia
   da chuva DAQUELE dia. Agronomicamente isso e errado -- a planta cresce da
   agua ARMAZENADA no solo, nao da chuva que caiu hoje. Agora a simulacao
   carrega dois estados dia a dia: a agua no solo e a altura do dossel.

2. **Demanda hidrica fisica (FAO-56).** A perda de agua nao e mais um palpite:
   e a evapotranspiracao de referencia ET0 por Penman-Monteith, calculada com
   as cinco variaveis climaticas (temperatura, umidade, radiacao, vento) e a
   altitude da RMSP. Cada especie consome `kc * ET0` e resiste ate esgotar a
   fracao `fracao_esgotamento` do seu reservatorio -- que depende da
   profundidade de raiz DELA. E dai que sai a diferenca real entre a
   grama-batatais (aguenta veranico) e o capim-elefante (sofre primeiro).

3. **Curva termica beta por especie.** No lugar do triangulo unico, a beta
   normalizada de Yan & Hunt: pico exatamente em `temp_otima_c`, zero nos
   cardeais, e largura controlada por `curva_termica_a`. Especie rustica tem
   curva larga; especie tropical exigente tem pico estreito.

4. **Luz interceptada pelo dossel.** Radiacao entra duas vezes, por mecanismos
   diferentes: a resposta fotossintetica saturante (meia-saturacao propria de
   cada especie -- tolerancia a sombra) e a FRACAO de luz que o dossel captura
   (Beer-Lambert sobre o IAF, que cresce com a altura). E isso que produz a
   rebrota lenta logo apos o corte e explica por que o gramado prostrado
   (folha horizontal, k_extincao alto) arranca mais rapido que a touceira
   ereta.

5. **Vento = acamamento, nao secagem.** O efeito evaporativo do vento ja esta
   dentro do ET0; contar de novo seria dupla contagem. O que sobra e o efeito
   mecanico: capim alto tomba, gramado rasteiro nao. Por isso a penalidade
   agora depende da altura ATUAL.

Todas as constantes continuam sendo estimativas de engenharia calibradas para
alturas realistas em margem de rodovia na RMSP; a estrutura e que passou a ser
a de um modelo agronomico de verdade. Nao substituem medicao de campo.
"""

from __future__ import annotations

import math

from .config import (
    AGUA_DISPONIVEL_MM_POR_M,
    AGUA_INICIAL_FRACAO,
    GRASS_SPECIES,
    REGION_ALTITUDE_M,
)

# Constante de Stefan-Boltzmann para fluxo diario (MJ K^-4 m^-2 d^-1).
_SIGMA = 4.903e-9
# Albedo da referencia de grama do FAO-56.
_ALBEDO = 0.23
# Razao Rs/Rso assumida (ceu medio). O FAO-56 calcularia Rso a partir da
# radiacao extraterrestre (dia do ano + latitude); como o modelo climatico
# entrega apenas Rs, fixa-se a razao tipica de dia parcialmente claro.
_RAZAO_CEU_CLARO = 0.75


def _limitar(valor: float, minimo: float, maximo: float) -> float:
    """Equivalente escalar de np.clip (bem mais barato no laco diario)."""
    return float(min(max(valor, minimo), maximo))


def _pressao_atmosferica(altitude_m: float) -> float:
    """Pressao atmosferica (kPa) pela atmosfera padrao (FAO-56 eq. 7)."""
    return 101.3 * ((293.0 - 0.0065 * altitude_m) / 293.0) ** 5.26


# Constante psicrometrica (kPa/C) da regiao — nao depende do clima do dia.
_GAMMA = 0.000665 * _pressao_atmosferica(REGION_ALTITUDE_M)


def pressao_vapor_saturacao(temp_c: float) -> float:
    """Pressao de vapor de saturacao es (kPa) — FAO-56 eq. 11."""
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def evapotranspiracao_referencia(
    temperatura_c: float,
    umidade_pct: float,
    radiacao_mj_m2: float,
    vento_kmh: float,
) -> float:
    """ET0 diaria (mm/dia) por Penman-Monteith FAO-56.

    Usa as quatro variaveis climaticas que afetam a demanda atmosferica. Duas
    simplificacoes documentadas, impostas pelo que o modelo climatico entrega:
      * sem Tmax/Tmin, o balanco de onda longa usa a temperatura media;
      * sem radiacao extraterrestre, assume-se Rs/Rso = 0.75 (ceu medio).
    """
    t = float(temperatura_c)
    es = pressao_vapor_saturacao(t)
    ea = es * _limitar(umidade_pct, 0.0, 100.0) / 100.0
    dpv = max(es - ea, 0.0)  # deficit de pressao de vapor (kPa)

    # Declividade da curva de pressao de vapor (kPa/C) — FAO-56 eq. 13.
    delta = 4098.0 * es / (t + 237.3) ** 2

    rs = max(float(radiacao_mj_m2), 0.0)
    # Saldo de radiacao: onda curta absorvida menos onda longa emitida.
    rns = (1.0 - _ALBEDO) * rs
    rnl = (
        _SIGMA
        * (t + 273.16) ** 4
        * max(0.34 - 0.14 * math.sqrt(ea), 0.05)
        * (1.35 * _RAZAO_CEU_CLARO - 0.35)
    )
    rn = max(rns - rnl, 0.0)

    u2 = max(float(vento_kmh), 0.0) / 3.6  # km/h -> m/s a 2 m

    termo_radiativo = 0.408 * delta * rn
    termo_aerodinamico = _GAMMA * (900.0 / (t + 273.0)) * u2 * dpv
    denominador = delta + _GAMMA * (1.0 + 0.34 * u2)
    return float(max((termo_radiativo + termo_aerodinamico) / denominador, 0.0))


def fator_temperatura(temp_c: float, especie: dict) -> float:
    """Resposta termica beta normalizada em [0, 1].

    Beta de Yan & Hunt: vale exatamente 1 em `temp_otima_c`, zero em
    `temp_min_c` e `temp_max_c`. O expoente `curva_termica_a` controla a
    largura -- especie rustica (a baixo) mantem crescimento longe do otimo;
    especie exigente (a alto) despenca rapido.
    """
    t_min = especie["temp_min_c"]
    t_max = especie["temp_max_c"]
    t_opt = especie["temp_otima_c"]
    if temp_c <= t_min or temp_c >= t_max:
        return 0.0

    a = especie.get("curva_termica_a", 1.5)
    # Expoente do ramo descendente que coloca o maximo exatamente em t_opt.
    b = a * (t_max - t_opt) / (t_opt - t_min)
    subida = (temp_c - t_min) / (t_opt - t_min)
    descida = (t_max - temp_c) / (t_max - t_opt)
    return _limitar(subida**a * descida**b, 0.0, 1.0)


def capacidade_hidrica_mm(especie: dict) -> float:
    """Agua disponivel (mm) no volume de solo alcancado pela raiz da especie."""
    return (especie["prof_raiz_mm"] / 1000.0) * AGUA_DISPONIVEL_MM_POR_M


def fator_agua(agua_solo_mm: float, especie: dict) -> float:
    """Coeficiente de estresse hidrico Ks (FAO-56), em [0, 1].

    Enquanto a especie nao esgota a fracao `fracao_esgotamento` do
    reservatorio, cresce sem estresse (Ks = 1). Passado esse ponto, Ks cai
    linearmente ate zero no ponto de murcha. Raiz mais profunda e fracao de
    esgotamento maior = mais dias de veranico sem sofrer.
    """
    capacidade = capacidade_hidrica_mm(especie)
    if capacidade <= 0:
        return 0.0
    agua = _limitar(agua_solo_mm, 0.0, capacidade)
    prontamente_disponivel = especie["fracao_esgotamento"] * capacidade
    reserva_sob_estresse = capacidade - prontamente_disponivel
    if agua >= reserva_sob_estresse:
        return 1.0
    if reserva_sob_estresse <= 0:
        return 1.0
    return _limitar(agua / reserva_sob_estresse, 0.0, 1.0)


def fator_radiacao(radiacao_mj_m2: float, especie: dict) -> float:
    """Resposta fotossintetica saturante a radiacao (Michaelis-Menten).

    A meia-saturacao e propria da especie: valor baixo = satura com pouca luz
    (tolerante a sombra, caso do coloniao); valor alto = so rende sob sol pleno
    (caso do Cynodon).
    """
    k = especie["k_radiacao_mj"]
    r = max(float(radiacao_mj_m2), 0.0)
    return float(r / (r + k))


def indice_area_foliar(altura_cm: float, especie: dict) -> float:
    """IAF do dossel a partir da altura, com a area foliar residual do corte."""
    return float(
        especie["lai_residual"] + especie["lai_por_cm"] * max(altura_cm, 0.0)
    )


def fator_dossel(altura_cm: float, especie: dict) -> float:
    """Fracao da luz interceptada pelo dossel (Beer-Lambert).

    Logo apos o corte so o resto de folha intercepta luz, e a rebrota e lenta;
    conforme o dossel fecha, a interceptacao satura. `k_extincao` distingue a
    folha horizontal do gramado prostrado (intercepta muito com pouca altura)
    da folha ereta da touceira.
    """
    iaf = indice_area_foliar(altura_cm, especie)
    return 1.0 - math.exp(-especie["k_extincao"] * iaf)


def fator_vento(vento_kmh: float, altura_cm: float, especie: dict) -> float:
    """Penalidade MECANICA de acamamento (tombamento) por vento forte.

    O efeito do vento sobre a perda de agua ja esta no ET0 -- aqui so entra o
    dano fisico, que depende da altura atual: capim alto tomba, gramado
    rasteiro nao sente. Sem efeito ate 10 km/h.
    """
    excesso = max(float(vento_kmh) - 10.0, 0.0)
    if excesso <= 0:
        return 1.0
    altura_rel = _limitar(altura_cm / especie["altura_max_cm"], 0.0, 1.0)
    penalidade = (
        especie["vento_sensibilidade"] * excesso * altura_rel ** especie["vento_expoente"]
    )
    return _limitar(1.0 - penalidade, 0.5, 1.0)


def fator_autolimitacao(altura_cm: float, especie: dict) -> float:
    """Desaceleracao perto da altura maxima (forma de Richards).

    `richards_nu` define o feitio: valor alto (gramado) cresce quase linear e
    trava de vez perto do teto; valor baixo (capim alto) desacelera cedo e de
    forma suave.
    """
    h_max = especie["altura_max_cm"]
    altura_rel = _limitar(altura_cm / h_max, 0.0, 1.0)
    return _limitar(1.0 - altura_rel ** especie["richards_nu"], 0.0, 1.0)


def taxa_crescimento_diaria(
    especie_nome: str,
    temperatura_c: float,
    precipitacao_mm: float,
    umidade_pct: float,
    radiacao_mj_m2: float,
    vento_kmh: float,
    altura_cm: float = 0.0,
    agua_solo_mm: float | None = None,
) -> float:
    """Crescimento (cm) de UM dia sob as condicoes dadas.

    Ponto de entrada de diagnostico: calcula a taxa de um dia isolado. Sem
    `agua_solo_mm` o solo e assumido na condicao inicial padrao, entao a chuva
    do proprio dia praticamente nao aparece -- e o comportamento correto, e por
    isso que a altura servida pela API vem de `simular_crescimento`, que carrega
    a agua do solo de um dia para o outro.
    """
    especie = GRASS_SPECIES[especie_nome]
    if agua_solo_mm is None:
        agua_solo_mm = AGUA_INICIAL_FRACAO * capacidade_hidrica_mm(especie)
    agua = min(agua_solo_mm + max(precipitacao_mm, 0.0), capacidade_hidrica_mm(especie))

    incremento = (
        especie["taxa_base_cm_dia"]
        * fator_temperatura(temperatura_c, especie)
        * fator_agua(agua, especie)
        * fator_radiacao(radiacao_mj_m2, especie)
        * fator_dossel(altura_cm, especie)
        * fator_vento(vento_kmh, altura_cm, especie)
        * fator_autolimitacao(altura_cm, especie)
    )
    return float(max(incremento, 0.0))


def simular_crescimento(
    especie_nome: str,
    clima_diario,
    altura_inicial_cm: float = 0.0,
    agua_inicial_mm: float | None = None,
) -> dict:
    """Integra o crescimento dia a dia a partir do corte.

    `clima_diario` e uma sequencia (n_dias, 5) na ordem de CLIMATE_TARGETS:
    temperatura_c, precipitacao_mm, umidade_pct, radiacao_mj_m2, vento_kmh.

    A cada dia, nesta ordem:
      1. a chuva entra no reservatorio de solo (o que passa da capacidade
         escorre -- margem de rodovia e drenada);
      2. calcula-se a demanda ET0 (Penman-Monteith) e o consumo real da especie
         `Ks * kc * ET0`, que sai do reservatorio;
      3. o incremento do dia sai do produto dos fatores limitantes, todos
         avaliados no estado ATUAL (altura e agua daquele dia);
      4. a altura sobe -- e nunca desce, entao alargar o horizonte de projecao
         nunca reduz a altura prevista.

    Retorna a altura final, a serie diaria e a media de cada fator limitante
    (util para explicar o que segurou o crescimento no periodo).
    """
    especie = GRASS_SPECIES[especie_nome]
    capacidade = capacidade_hidrica_mm(especie)
    altura_max = especie["altura_max_cm"]
    agua = (
        AGUA_INICIAL_FRACAO * capacidade if agua_inicial_mm is None else float(agua_inicial_mm)
    )
    agua = _limitar(agua, 0.0, capacidade)

    altura = _limitar(altura_inicial_cm, 0.0, especie["altura_max_cm"])
    serie_altura: list[float] = []
    acum = {"temperatura": 0.0, "agua": 0.0, "radiacao": 0.0, "dossel": 0.0, "vento": 0.0}
    n_dias = 0

    for linha in clima_diario:
        temperatura_c, precipitacao_mm, umidade_pct, radiacao_mj_m2, vento_kmh = (
            float(x) for x in linha
        )

        # 1. Entrada de agua (excedente escoa).
        agua = min(agua + max(precipitacao_mm, 0.0), capacidade)

        # 2. Fatores limitantes no estado atual.
        f_temp = fator_temperatura(temperatura_c, especie)
        f_agua = fator_agua(agua, especie)
        f_rad = fator_radiacao(radiacao_mj_m2, especie)
        f_dossel = fator_dossel(altura, especie)
        f_vento = fator_vento(vento_kmh, altura, especie)

        # 3. Consumo hidrico real do dia (FAO-56: Ks * Kc * ET0).
        et0 = evapotranspiracao_referencia(
            temperatura_c, umidade_pct, radiacao_mj_m2, vento_kmh
        )
        agua = max(agua - f_agua * especie["kc"] * et0, 0.0)

        # 4. Incremento e atualizacao da altura.
        incremento = (
            especie["taxa_base_cm_dia"]
            * f_temp
            * f_agua
            * f_rad
            * f_dossel
            * f_vento
            * fator_autolimitacao(altura, especie)
        )
        altura = _limitar(altura + max(incremento, 0.0), 0.0, altura_max)
        serie_altura.append(altura)

        acum["temperatura"] += f_temp
        acum["agua"] += f_agua
        acum["radiacao"] += f_rad
        acum["dossel"] += f_dossel
        acum["vento"] += f_vento
        n_dias += 1

    fatores_medios = (
        {k: round(v / n_dias, 3) for k, v in acum.items()} if n_dias else dict.fromkeys(acum, 0.0)
    )
    return {
        "altura_cm": altura,
        "serie_altura_cm": serie_altura,
        "agua_solo_mm": agua,
        "capacidade_hidrica_mm": capacidade,
        "fatores_medios": fatores_medios,
        "n_dias": n_dias,
    }


def altura_acumulada(especie_nome: str, clima_diario) -> float:
    """Altura (cm) apos a janela de clima diario informada (atalho)."""
    return float(simular_crescimento(especie_nome, clima_diario)["altura_cm"])


def altura_estimada(
    especie_nome: str,
    dias_desde_corte: float,
    temperatura_c: float,
    precipitacao_mm: float,
    umidade_pct: float,
    radiacao_mj_m2: float,
    vento_kmh: float,
) -> float:
    """Altura (cm) apos N dias sob um clima CONSTANTE.

    Atalho de cenario ("e se ficasse assim o mes inteiro?"). A altura servida
    pela API nao passa por aqui: ela usa o clima real/previsto de cada dia via
    `simular_crescimento`.
    """
    n = int(max(dias_desde_corte, 0))
    if n == 0:
        return 0.0
    dia = (temperatura_c, precipitacao_mm, umidade_pct, radiacao_mj_m2, vento_kmh)
    return altura_acumulada(especie_nome, [dia] * n)
