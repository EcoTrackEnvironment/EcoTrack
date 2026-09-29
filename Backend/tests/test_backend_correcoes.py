"""Regressoes para correcoes operacionais do backend."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest
from fastapi import HTTPException

from src import api, clients, db, mapa, predict
from src.clients import ClimateAPIError, ClimateReading
from src.forecast import PrevisaoIndisponivelError


def _corte(data: dt.date, identificador: int = 1) -> dict:
    return {
        "id": identificador,
        "escopo": "global",
        "latitude": None,
        "longitude": None,
        "raio_influencia_m": None,
        "data_corte": data.isoformat(),
        "altura_corte_cm": 2.0,
        "observacao": None,
        "criado_em": "2026-01-01T00:00:00",
    }


def test_mapa_resolve_cortes_na_data_alvo(monkeypatch):
    alvo = dt.date(2026, 8, 10)
    referencias = []

    monkeypatch.setattr(mapa, "RODOVIA_ROTA", [(-23.4, -46.7), (-23.4, -46.699)])
    monkeypatch.setattr(mapa, "grupo_climatico", lambda *_: (-23.4, -46.7))

    def resolver(coords, referencia):
        referencias.append(referencia)
        return [_corte(alvo) for _ in coords]

    monkeypatch.setattr(mapa, "resolver_cortes", resolver)

    resultado = mapa.gerar_mapa_rodovia(espacamento_km=0.2, dia=alvo)

    assert referencias == [alvo]
    assert resultado["data"] == alvo.isoformat()


@pytest.mark.parametrize(
    ("dias", "inicio_esperado"),
    [(0, dt.date(2020, 1, 3)), (1, dt.date(2020, 1, 3)), (3, dt.date(2020, 1, 1))],
)
def test_prever_altura_usa_exatamente_os_dias_de_crescimento(
    monkeypatch, dias, inicio_esperado
):
    fim = dt.date(2020, 1, 3)
    chamadas = []

    def janela(_lat, _lon, inicio, fim_recebido, _clima):
        chamadas.append((inicio, fim_recebido))
        n_dias = (fim_recebido - inicio).days + 1
        return {
            "valores": np.zeros((n_dias, 5)),
            "std": np.zeros((n_dias, 5)),
            "fontes": {"modelo-clima": 0},
        }

    monkeypatch.setattr(predict, "montar_clima_janela", janela)
    monkeypatch.setattr(
        predict,
        "prever_crescimento_janela",
        lambda *_args, **_kwargs: {
            "altura_cm": 99.0,
            "confianca": 0.8,
            "std_cm": 0.0,
            "fatores_medios": {},
        },
    )
    monkeypatch.setattr(
        predict,
        "resumo_clima_janela",
        lambda *_args: ClimateReading(fim, 0, 0, 0, 0, 0, 0, 0, "teste", {}),
    )
    monkeypatch.setattr(
        predict,
        "simular_crescimento",
        lambda _especie, clima, altura_inicial_cm=0.0: {
            "altura_cm": altura_inicial_cm if len(clima) == 0 else 99.0
        },
    )

    resultado = predict.prever_altura(
        0,
        0,
        "Brachiaria (Urochloa)",
        dias,
        fim,
        clima_hoje=object(),
        altura_inicial_cm=4.0,
    )

    assert chamadas == [(inicio_esperado, fim)]
    assert resultado["altura_cm"] == (4.0 if dias == 0 else 99.0)
    if dias == 0:
        assert resultado["confianca"] == 1.0
        assert resultado["std_cm"] == 0.0
        assert resultado["fatores_medios"] == {}


def test_health_exige_artefato_joblib_e_preserva_campos(monkeypatch, tmp_path):
    modelo = tmp_path / "climate_model.joblib"
    metadata = tmp_path / "model_metadata.json"
    metadata.write_text("{}")
    monkeypatch.setattr(api, "MODEL_PATH", modelo)
    monkeypatch.setattr(api, "MODEL_META_PATH", metadata)

    assert api.health() == {
        "status": "modelo_ausente",
        "modelo_treinado": False,
        "metadata_disponivel": True,
    }

    modelo.write_bytes(b"artefato")
    assert api.health()["status"] == "ok"
    assert api.health()["modelo_treinado"] is True


def test_crescimento_serie_converte_previsao_indisponivel_em_422(monkeypatch):
    hoje = dt.date.today()
    monkeypatch.setattr(api, "corte_vigente", lambda *_args: _corte(hoje - dt.timedelta(days=1)))

    def sem_clima(*_args):
        raise PrevisaoIndisponivelError("sem cobertura")

    monkeypatch.setattr(api, "obter_clima", sem_clima)

    with pytest.raises(HTTPException) as excinfo:
        api.crescimento_serie(
            inicio=None,
            fim=hoje.isoformat(),
            latitude=None,
            longitude=None,
        )

    assert excinfo.value.status_code == 422
    assert excinfo.value.detail == "sem cobertura"


def test_desempate_de_corte_usa_id_mesmo_com_relogio_regressivo():
    antigo = _corte(dt.date(2026, 8, 10), identificador=10)
    antigo["criado_em"] = "2030-01-01T00:00:00"
    recente = _corte(dt.date(2026, 8, 10), identificador=11)
    recente["criado_em"] = "2000-01-01T00:00:00"

    assert max([antigo, recente], key=db._ordenacao)["id"] == 11


def test_remover_corte_mantem_protecao_do_ultimo_global(tmp_path, monkeypatch):
    caminho = tmp_path / "cortes.db"
    monkeypatch.setattr(db, "DB_PATH", caminho)
    db.inicializar()
    (unico_global,) = db.listar_cortes()

    with pytest.raises(db.CorteNaoEncontradoError):
        db.remover_corte(unico_global["id"])

    outro = db.registrar_corte(data_corte=dt.date.today(), altura_corte_cm=3.0)
    removido = db.remover_corte(unico_global["id"])

    assert removido["id"] == unico_global["id"]
    assert db.obter_corte(outro["id"])["id"] == outro["id"]


@pytest.mark.parametrize(
    "daily",
    [
        {"temperature_2m_mean": [None]},
        {"temperature_2m_mean": [float("nan")]},
        {"temperature_2m_mean": "nao-e-lista"},
    ],
)
def test_open_meteo_normaliza_resposta_invalida(monkeypatch, daily):
    monkeypatch.setattr(clients, "_get_json", lambda *_args: {"daily": daily})

    with pytest.raises(ClimateAPIError):
        clients.fetch_open_meteo(-23.5, -46.6, dt.date(2026, 1, 1))


def test_nasa_normaliza_numero_nao_finito(monkeypatch):
    monkeypatch.setattr(
        clients,
        "_get_json",
        lambda *_args: {
            "properties": {"parameter": {"ALLSKY_SFC_SW_DWN": {"20260101": "nan"}}}
        },
    )

    with pytest.raises(ClimateAPIError):
        clients.fetch_nasa_power(-23.5, -46.6, dt.date(2026, 1, 1))
