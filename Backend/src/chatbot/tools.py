"""Allowlist de ferramentas que adaptam o dominio EcoTrack para a Gemini."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from ..clients import checar_apis_externas
from ..config import (
    ALTURA_CORTE_RECOMENDADO_CM,
    GRASS_SPECIES,
    MODEL_META_PATH,
    MONITORING_POINTS,
    REGION_CENTER,
    REGION_NAME,
    SPECIES_LIST,
)
from ..forecast import PrevisaoIndisponivelError, status_previsao
from ..predict import ModeloIndisponivelError, prever_altura

logger = logging.getLogger("ecotrack.chatbot.tools")


class StrictToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyArgs(StrictToolArgs):
    pass


class PredictionArgs(StrictToolArgs):
    especie: str
    dias_desde_corte: int = Field(ge=0, le=365)
    data: dt.date | None = None

    @field_validator("especie")
    @classmethod
    def validate_species(cls, value: str) -> str:
        if value not in SPECIES_LIST:
            raise ValueError(f"especie invalida; use uma de: {', '.join(SPECIES_LIST)}")
        return value


class PointPredictionArgs(PredictionArgs):
    ponto_id: str = Field(min_length=1, max_length=40)


class CoordinatePredictionArgs(PredictionArgs):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    raio_metros: float = Field(default=500, gt=0)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    args_model: type[StrictToolArgs]
    function: Callable[[StrictToolArgs], dict[str, Any]]

    def declaration(self) -> dict[str, Any]:
        schema = _clean_schema(self.args_model.model_json_schema())
        properties = schema.get("properties", {})
        if "especie" in properties:
            properties["especie"]["enum"] = SPECIES_LIST
        if "ponto_id" in properties:
            properties["ponto_id"]["enum"] = [
                point["id"] for point in MONITORING_POINTS
            ]
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": schema,
        }


def _clean_schema(value: Any) -> Any:
    """Converte o schema Pydantic para o subconjunto simples aceito por tools."""
    if isinstance(value, list):
        return [_clean_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    cleaned = {
        key: _clean_schema(item)
        for key, item in value.items()
        if key not in {"title", "default"}
    }
    choices = cleaned.get("anyOf")
    if isinstance(choices, list):
        non_null = [item for item in choices if item.get("type") != "null"]
        if len(non_null) == 1 and len(non_null) != len(choices):
            cleaned.pop("anyOf")
            cleaned.update(non_null[0])
    return cleaned


def _prediction_payload(
    latitude: float,
    longitude: float,
    raio_metros: float,
    especie: str,
    dias_desde_corte: int,
    data: dt.date | None,
    *,
    ponto: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = prever_altura(
        latitude=latitude,
        longitude=longitude,
        especie=especie,
        dias_desde_corte=dias_desde_corte,
        dia=data,
    )
    climate = result["clima"]
    payload: dict[str, Any] = {
        "localizacao": {
            "latitude": latitude,
            "longitude": longitude,
            "raio_metros": raio_metros,
        },
        "previsao": {
            "altura_cm": result["altura_cm"],
            "confianca": result["confianca"],
        },
        "especie": especie,
        "dias_desde_corte": dias_desde_corte,
        "data": (data or dt.date.today()).isoformat(),
        "fonte_clima": climate.fonte,
        "clima": {
            "temperatura_c": round(climate.temperatura_c, 2),
            "precipitacao_mm": round(climate.precipitacao_mm, 2),
            "umidade_pct": round(climate.umidade_pct, 1),
            "radiacao_mj_m2": round(climate.radiacao_mj_m2, 2),
            "vento_kmh": round(climate.vento_kmh, 1),
            "fontes": climate.fontes,
        },
        "corte_recomendado": result["altura_cm"] >= ALTURA_CORTE_RECOMENDADO_CM,
        "aviso": "Estimativa de apoio; considere inspecao em campo.",
    }
    if ponto:
        payload["ponto"] = {"id": ponto["id"], "trecho": ponto["trecho"]}
    return payload


def _list_points(_: EmptyArgs) -> dict[str, Any]:
    return {"regiao": REGION_NAME, "pontos": MONITORING_POINTS}


def _list_species(_: EmptyArgs) -> dict[str, Any]:
    return {
        "especies": [
            {"nome": name, **parameters} for name, parameters in GRASS_SPECIES.items()
        ]
    }


def _predict_point(args: PointPredictionArgs) -> dict[str, Any]:
    point = next((item for item in MONITORING_POINTS if item["id"] == args.ponto_id), None)
    if point is None:
        valid_ids = ", ".join(item["id"] for item in MONITORING_POINTS)
        raise ValueError(f"ponto_id invalido; use um de: {valid_ids}")
    return _prediction_payload(
        point["latitude"],
        point["longitude"],
        point["raio_metros"],
        args.especie,
        args.dias_desde_corte,
        args.data,
        ponto=point,
    )


def _predict_coordinates(args: CoordinatePredictionArgs) -> dict[str, Any]:
    return _prediction_payload(
        args.latitude,
        args.longitude,
        args.raio_metros,
        args.especie,
        args.dias_desde_corte,
        args.data,
    )


def _forecast_status(_: EmptyArgs) -> dict[str, Any]:
    return status_previsao()


def _model_status(_: EmptyArgs) -> dict[str, Any]:
    if not MODEL_META_PATH.exists():
        raise ModeloIndisponivelError(
            "Modelo climatico nao treinado. Execute o pipeline documentado."
        )
    metadata = json.loads(MODEL_META_PATH.read_text(encoding="utf-8"))
    history = metadata.get("historico") or {}
    return {
        "disponivel": True,
        "tipo": metadata.get("modelo"),
        "papel": metadata.get("papel"),
        "treinado_em": metadata.get("treinado_em"),
        "historico": {
            "periodo": history.get("periodo"),
            "n_amostras": history.get("n_amostras"),
            "n_celulas_climaticas": history.get("n_celulas_climaticas"),
            "pct_dados_reais": history.get("pct_dados_reais"),
        },
        "metricas": metadata.get("metricas"),
    }


def _api_status(_: EmptyArgs) -> dict[str, Any]:
    result = checar_apis_externas(
        REGION_CENTER["latitude"],
        REGION_CENTER["longitude"],
    )
    return {
        "apis": [
            {
                "nome": item.get("nome"),
                "status": item.get("status"),
                "latencia_ms": item.get("latencia_ms"),
                "detalhe": (
                    "resposta valida"
                    if item.get("status") == "up"
                    else "fonte temporariamente indisponivel"
                ),
            }
            for item in result.get("apis", [])
        ],
        "usando_modelo_como_base": result.get("usando_modelo_como_base"),
        "verificado_em": result.get("verificado_em"),
    }


TOOL_DEFINITIONS = (
    ToolDefinition(
        "listar_pontos_monitorados",
        "Lista os pontos monitorados, trechos, coordenadas e raios configurados.",
        EmptyArgs,
        _list_points,
    ),
    ToolDefinition(
        "listar_especies_suportadas",
        "Lista as especies aceitas e seus parametros agronomicos publicos.",
        EmptyArgs,
        _list_species,
    ),
    ToolDefinition(
        "consultar_previsao_por_ponto",
        "Consulta altura estimada, confianca, clima e corte para um ponto cadastrado.",
        PointPredictionArgs,
        _predict_point,
    ),
    ToolDefinition(
        "consultar_previsao_por_coordenadas",
        "Consulta altura estimada, confianca, clima e corte por latitude/longitude.",
        CoordinatePredictionArgs,
        _predict_coordinates,
    ),
    ToolDefinition(
        "consultar_status_previsao_climatica",
        "Informa se o CSV de previsao climatica existe e o periodo que cobre.",
        EmptyArgs,
        _forecast_status,
    ),
    ToolDefinition(
        "consultar_status_modelo",
        "Retorna apenas metadados seguros do modelo de previsao climatica.",
        EmptyArgs,
        _model_status,
    ),
    ToolDefinition(
        "consultar_status_apis_climaticas",
        "Consulta em rede a disponibilidade atual de Open-Meteo e NASA POWER.",
        EmptyArgs,
        _api_status,
    ),
)


class ToolRegistry:
    def __init__(
        self,
        definitions: tuple[ToolDefinition, ...] = TOOL_DEFINITIONS,
        runner: Callable[
            [Callable[[StrictToolArgs], dict[str, Any]], StrictToolArgs],
            Awaitable[dict[str, Any]],
        ]
        | None = None,
    ):
        self._definitions = {definition.name: definition for definition in definitions}
        self._runner = runner or self._run_in_thread

    @staticmethod
    async def _run_in_thread(
        function: Callable[[StrictToolArgs], dict[str, Any]],
        arguments: StrictToolArgs,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(function, arguments)

    @property
    def declarations(self) -> list[dict[str, Any]]:
        return [definition.declaration() for definition in self._definitions.values()]

    async def execute(self, name: str, arguments: Any) -> dict[str, Any]:
        definition = self._definitions.get(name)
        if definition is None:
            logger.warning("tool_not_allowed", extra={"tool": name})
            return {
                "ok": False,
                "error": {
                    "code": "TOOL_NOT_ALLOWED",
                    "message": "Ferramenta nao permitida.",
                },
            }
        try:
            validated = definition.args_model.model_validate(arguments or {})
        except ValidationError as exc:
            return {
                "ok": False,
                "error": {
                    "code": "INVALID_TOOL_ARGUMENTS",
                    "message": "Argumentos invalidos para a consulta.",
                    "details": [
                        {"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
                        for item in exc.errors(include_url=False, include_input=False)
                    ],
                },
            }
        try:
            result = await self._runner(definition.function, validated)
            return {"ok": True, "data": result}
        except ModeloIndisponivelError:
            return {
                "ok": False,
                "error": {
                    "code": "MODEL_UNAVAILABLE",
                    "message": "Modelo climatico indisponivel. Execute o pipeline documentado.",
                },
            }
        except PrevisaoIndisponivelError:
            return {
                "ok": False,
                "error": {
                    "code": "FORECAST_UNAVAILABLE",
                    "message": (
                        "Previsao sem cobertura para a data. Consulte o status "
                        "da previsao e gere-a pelo procedimento documentado."
                    ),
                },
            }
        except (ValueError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "error": {"code": "DOMAIN_VALIDATION", "message": str(exc)[:300]},
            }
        except Exception:
            logger.exception("tool_execution_failed", extra={"tool": name})
            return {
                "ok": False,
                "error": {
                    "code": "TOOL_FAILED",
                    "message": "Nao foi possivel consultar os dados do EcoTrack.",
                },
            }
