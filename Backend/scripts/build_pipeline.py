"""Executa o pipeline offline completo do EcoTrack:

  1. Coleta ate 1 ano de dados climaticos REAIS das APIs gratuitas (Open-Meteo
     arquivo + NASA POWER) para todas as celulas climaticas da rodovia
     -> data/climate_history.csv.
  2. Treina o modelo de PREVISAO CLIMATICA autorregressivo (preve o dia
     seguinte a partir dos dias passados) e salva modelo + metricas.
  3. Gera a previsao recursiva de 365 dias (dia 1 -> dia 2 -> ...) para todas
     as celulas -> data/climate_forecast.csv.

Uso:
  python -m scripts.build_pipeline
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import FORECAST_CSV, HISTORY_CSV, MODEL_PATH  # noqa: E402
from src.forecast import gerar_previsao  # noqa: E402
from src.historico import coletar_historico  # noqa: E402
from src.train import treinar  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    print("[1/3] Coletando historico climatico real (ate 1 ano, todas as celulas)...")
    df_hist = coletar_historico()
    n_celulas = df_hist[["latitude", "longitude"]].drop_duplicates().shape[0]
    print(f"      -> {len(df_hist)} linhas ({n_celulas} celulas climaticas) em {HISTORY_CSV}")

    print("[2/3] Treinando modelo de previsao climatica (autorregressivo)...")
    meta = treinar()
    print(f"      -> modelo em {MODEL_PATH}")
    print("      MAE por variavel:", meta["metricas"]["mae_por_variavel"])

    print("[3/3] Gerando previsao recursiva de 365 dias (todas as celulas)...")
    df_prev = gerar_previsao()
    print(f"      -> {len(df_prev)} linhas em {FORECAST_CSV}")
    print("\nPipeline concluido com sucesso.")


if __name__ == "__main__":
    main()
