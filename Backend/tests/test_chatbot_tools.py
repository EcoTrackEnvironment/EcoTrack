from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.chatbot import tools as tools_module
from src.chatbot.tools import ToolRegistry
from src.forecast import PrevisaoIndisponivelError
from src.predict import ModeloIndisponivelError


async def inline_runner(function, arguments):
    return function(arguments)


def registry() -> ToolRegistry:
    return ToolRegistry(runner=inline_runner)


def fake_prediction(**_: object):
    return {
        "altura_cm": 18.4,
        "confianca": 0.82,
        "clima": SimpleNamespace(
            fonte="historico-real(20d)+modelo-clima(11d)",
            temperatura_c=24.111,
            precipitacao_mm=2.222,
            umidade_pct=70.25,
            radiacao_mj_m2=18.333,
            vento_kmh=9.44,
            fontes={"temperatura_c": "media-da-janela"},
        ),
    }


@pytest.mark.asyncio
async def test_tool_declarations_are_allowlisted_and_strict():
    declarations = registry().declarations

    assert len(declarations) == 7
    assert {item["name"] for item in declarations} == {
        "listar_pontos_monitorados",
        "listar_especies_suportadas",
        "consultar_previsao_por_ponto",
        "consultar_previsao_por_coordenadas",
        "consultar_status_previsao_climatica",
        "consultar_status_modelo",
        "consultar_status_apis_climaticas",
    }
    assert all(item["parameters"]["additionalProperties"] is False for item in declarations)
    assert not any("atualizar" in item["name"] or "gerar" in item["name"] for item in declarations)
    prediction = next(
        item for item in declarations if item["name"] == "consultar_previsao_por_ponto"
    )
    assert "Brachiaria (Urochloa)" in prediction["parameters"]["properties"]["especie"]["enum"]
    assert "RA-S01" in prediction["parameters"]["properties"]["ponto_id"]["enum"]
    assert prediction["parameters"]["properties"]["data"]["type"] == "string"


@pytest.mark.asyncio
async def test_valid_point_uses_domain_prediction(monkeypatch):
    captured = {}

    def predict(**kwargs):
        captured.update(kwargs)
        return fake_prediction()

    monkeypatch.setattr(tools_module, "prever_altura", predict)
    result = await registry().execute(
        "consultar_previsao_por_ponto",
        {
            "ponto_id": "RA-S01",
            "especie": "Brachiaria (Urochloa)",
            "dias_desde_corte": 30,
            "data": "2026-07-17",
        },
    )

    assert result["ok"] is True
    assert result["data"]["ponto"]["id"] == "RA-S01"
    assert result["data"]["previsao"] == {
        "altura_cm": 18.4,
        "confianca": 0.82,
    }
    assert captured["dias_desde_corte"] == 30
    assert captured["dia"].isoformat() == "2026-07-17"


@pytest.mark.asyncio
async def test_invalid_point_species_and_bounds_are_friendly():
    tools = registry()
    invalid_point = await tools.execute(
        "consultar_previsao_por_ponto",
        {
            "ponto_id": "NAO-EXISTE",
            "especie": "Brachiaria (Urochloa)",
            "dias_desde_corte": 10,
        },
    )
    invalid_species = await tools.execute(
        "consultar_previsao_por_ponto",
        {"ponto_id": "RA-S01", "especie": "inventada", "dias_desde_corte": 10},
    )
    invalid_coordinates = await tools.execute(
        "consultar_previsao_por_coordenadas",
        {
            "latitude": 91,
            "longitude": -181,
            "raio_metros": 0,
            "especie": "Brachiaria (Urochloa)",
            "dias_desde_corte": 366,
            "data": "17/07/2026",
            "extra": "nao permitido",
        },
    )

    assert invalid_point["error"]["code"] == "DOMAIN_VALIDATION"
    assert invalid_species["error"]["code"] == "INVALID_TOOL_ARGUMENTS"
    assert invalid_coordinates["error"]["code"] == "INVALID_TOOL_ARGUMENTS"
    fields = {item["field"] for item in invalid_coordinates["error"]["details"]}
    assert {
        "latitude",
        "longitude",
        "raio_metros",
        "dias_desde_corte",
        "data",
        "extra",
    } <= fields


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ModeloIndisponivelError("internal path"), "MODEL_UNAVAILABLE"),
        (PrevisaoIndisponivelError("internal path"), "FORECAST_UNAVAILABLE"),
    ],
)
async def test_domain_unavailability_is_sanitized(monkeypatch, error, code):
    def fail(**_: object):
        raise error

    monkeypatch.setattr(tools_module, "prever_altura", fail)
    result = await registry().execute(
        "consultar_previsao_por_ponto",
        {
            "ponto_id": "RA-S01",
            "especie": "Brachiaria (Urochloa)",
            "dias_desde_corte": 10,
        },
    )

    assert result["error"]["code"] == code
    assert "internal path" not in result["error"]["message"]


@pytest.mark.asyncio
async def test_unknown_tool_and_invalid_arguments_do_not_execute():
    tools = registry()
    unknown = await tools.execute("abrir_arquivo", {"path": "/etc/passwd"})
    extra = await tools.execute("listar_pontos_monitorados", {"unexpected": True})

    assert unknown["error"]["code"] == "TOOL_NOT_ALLOWED"
    assert extra["error"]["code"] == "INVALID_TOOL_ARGUMENTS"
