"""Testes de fumaca do pipeline EcoTrack.

Rode com:  .venv/bin/python -m pytest -q
(ou simplesmente:  .venv/bin/python tests/test_smoke.py)
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import (  # noqa: E402
    CLIMATE_CONTEXTO_DIAS,
    CLIMATE_FEATURES,
    CLIMATE_TARGETS,
    GRASS_SPECIES,
    SPECIES_LIST,
)
from src.growth import (  # noqa: E402
    altura_acumulada,
    altura_estimada,
    evapotranspiracao_referencia,
    fator_agua,
    fator_temperatura,
    simular_crescimento,
)
from src.historico import celulas_climaticas, grupo_climatico  # noqa: E402
from src.train import features_de_contexto  # noqa: E402

# Um dia de verao umido na RMSP, na ordem de CLIMATE_TARGETS.
DIA_VERAO = (26.0, 6.0, 80.0, 22.0, 10.0)
# Veranico: quente, seco, com forte demanda evaporativa.
DIA_SECA = (28.0, 0.0, 50.0, 24.0, 14.0)


def test_fator_temperatura_zera_nos_extremos():
    esp = GRASS_SPECIES["Brachiaria (Urochloa)"]
    assert fator_temperatura(0, esp) == 0.0
    assert fator_temperatura(50, esp) == 0.0
    assert fator_temperatura(esp["temp_otima_c"], esp) == 1.0


def test_fator_temperatura_tem_maximo_no_otimo():
    # A beta normalizada nao pode passar de 1 em nenhum ponto da faixa.
    for esp in GRASS_SPECIES.values():
        for t in np.arange(esp["temp_min_c"], esp["temp_max_c"], 0.25):
            assert fator_temperatura(float(t), esp) <= 1.0 + 1e-9


def test_altura_cresce_com_dias():
    args = dict(
        especie_nome="Megathyrsus (capim-coloniao)",
        temperatura_c=30,
        precipitacao_mm=15,
        umidade_pct=80,
        radiacao_mj_m2=20,
        vento_kmh=10,
    )
    h10 = altura_estimada(dias_desde_corte=10, **args)
    h40 = altura_estimada(dias_desde_corte=40, **args)
    assert 0 < h10 < h40


def test_altura_acumulada_nao_decresce():
    h30 = altura_acumulada("Cynodon (grama-seda)", [DIA_VERAO] * 30)
    h60 = altura_acumulada("Cynodon (grama-seda)", [DIA_VERAO] * 60)
    assert 0 < h30 <= h60 <= GRASS_SPECIES["Cynodon (grama-seda)"]["altura_max_cm"]


def test_cada_especie_tem_seu_proprio_resultado():
    # Mesmo clima, mesma janela: as cinco especies precisam divergir.
    alturas = {
        nome: simular_crescimento(nome, [DIA_VERAO] * 45)["altura_cm"]
        for nome in SPECIES_LIST
    }
    assert len(set(round(h, 3) for h in alturas.values())) == len(SPECIES_LIST)
    # No verao umido o porte manda: elefante e coloniao passam dos gramados.
    assert alturas["Pennisetum (capim-elefante)"] > alturas["Paspalum (grama-batatais)"]
    assert alturas["Megathyrsus (capim-coloniao)"] > alturas["Cynodon (grama-seda)"]


def test_seca_inverte_a_ordem_das_especies():
    # Cynodon (raiz funda, tolera esgotar o solo) cresce menos que a Brachiaria
    # no verao umido, mas passa a frente dela num veranico prolongado.
    def altura(nome, dia):
        return simular_crescimento(nome, [dia] * 60)["altura_cm"]

    assert altura("Brachiaria (Urochloa)", DIA_VERAO) > altura("Cynodon (grama-seda)", DIA_VERAO)
    assert altura("Cynodon (grama-seda)", DIA_SECA) > altura("Brachiaria (Urochloa)", DIA_SECA)


def test_seca_pesa_mais_na_especie_sedenta():
    # Fracao do potencial que cada especie preserva sob veranico: a rustica
    # perde bem menos que a de alta demanda hidrica.
    def retencao(nome):
        seca = simular_crescimento(nome, [DIA_SECA] * 60)["altura_cm"]
        umido = simular_crescimento(nome, [DIA_VERAO] * 60)["altura_cm"]
        return seca / umido

    assert retencao("Paspalum (grama-batatais)") > 2 * retencao("Pennisetum (capim-elefante)")


def test_agua_do_solo_esgota_e_trava_o_crescimento():
    # Sem chuva, o reservatorio zera e o crescimento cessa: os ultimos dias de
    # uma janela longa nao podem adicionar quase nada.
    sim = simular_crescimento("Pennisetum (capim-elefante)", [DIA_SECA] * 120)
    serie = sim["serie_altura_cm"]
    assert sim["agua_solo_mm"] < 1.0
    assert serie[-1] - serie[-10] < 0.1


def test_fator_agua_respeita_a_tolerancia_da_especie():
    # Com o mesmo conteudo de agua no solo, a especie rustica sofre menos.
    rustica = GRASS_SPECIES["Paspalum (grama-batatais)"]
    sedenta = GRASS_SPECIES["Pennisetum (capim-elefante)"]
    assert fator_agua(25.0, rustica) > fator_agua(25.0, sedenta)


def test_et0_responde_as_variaveis_climaticas():
    base = evapotranspiracao_referencia(26.0, 70.0, 20.0, 10.0)
    assert 1.0 < base < 12.0  # faixa fisica de ET0 diaria
    assert evapotranspiracao_referencia(26.0, 30.0, 20.0, 10.0) > base  # ar seco
    assert evapotranspiracao_referencia(26.0, 70.0, 28.0, 10.0) > base  # mais sol
    assert evapotranspiracao_referencia(26.0, 70.0, 20.0, 25.0) > base  # mais vento


def test_features_de_contexto_cobre_todas_as_features():
    contexto = np.ones((CLIMATE_CONTEXTO_DIAS, len(CLIMATE_TARGETS)))
    f = features_de_contexto(contexto, dt.date(2026, 7, 17), -23.55, -46.63)
    assert set(CLIMATE_FEATURES) == set(f.keys())
    assert f["temperatura_c_lag1"] == 1.0


def test_celulas_climaticas_cobrem_a_rota():
    grupos = celulas_climaticas()
    assert len(grupos) >= 10
    lat_g, lon_g = grupo_climatico(-23.64, -46.58)
    assert (lat_g, lon_g) == (-23.6, -46.6)
    # O grupo fica a no maximo meia resolucao do ponto original.
    assert abs(lat_g - -23.64) <= 0.05 and abs(lon_g - -46.58) <= 0.05


def test_todas_especies_configuradas():
    assert len(SPECIES_LIST) == len(GRASS_SPECIES) >= 3


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"OK  {nome}")
    print("Todos os testes de fumaca passaram.")
