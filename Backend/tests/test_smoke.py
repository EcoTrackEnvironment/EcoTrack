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
from src.growth import altura_acumulada, altura_estimada, fator_temperatura  # noqa: E402
from src.historico import celulas_climaticas, grupo_climatico  # noqa: E402
from src.train import features_de_contexto  # noqa: E402


def test_fator_temperatura_zera_nos_extremos():
    esp = GRASS_SPECIES["Brachiaria (Urochloa)"]
    assert fator_temperatura(0, esp) == 0.0
    assert fator_temperatura(50, esp) == 0.0
    assert fator_temperatura(esp["temp_otima_c"], esp) == 1.0


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
    taxas = [1.0] * 30
    h30 = altura_acumulada("Cynodon (grama-seda)", taxas)
    h60 = altura_acumulada("Cynodon (grama-seda)", taxas * 2)
    assert 0 < h30 <= h60 <= GRASS_SPECIES["Cynodon (grama-seda)"]["altura_max_cm"]


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
