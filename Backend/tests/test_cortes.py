"""Testes do banco operacional de cortes (src/db.py).

Cada teste roda contra um SQLite temporario proprio: `src.db.DB_PATH` e trocado
em tempo de execucao, entao a base de verdade (data/ecotrack.db) nunca e tocada.

Rode com:  .venv/bin/python -m pytest -q
(ou simplesmente:  .venv/bin/python tests/test_cortes.py)
"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db  # noqa: E402
from src.config import CORTE_PADRAO_ALTURA_CM, CORTE_PADRAO_DATA  # noqa: E402

HOJE = dt.date.today()


@contextmanager
def base_temporaria():
    """Base recem-criada e semeada, descartada no fim do teste."""
    original = db.DB_PATH
    with tempfile.TemporaryDirectory() as pasta:
        db.DB_PATH = Path(pasta) / "teste.db"
        try:
            db.inicializar()
            yield
        finally:
            db.DB_PATH = original


def test_seed_cria_o_corte_geral_de_referencia():
    with base_temporaria():
        cortes = db.listar_cortes()
        assert len(cortes) == 1
        (corte,) = cortes
        assert corte["escopo"] == "global"
        assert corte["data_corte"] == CORTE_PADRAO_DATA
        assert corte["altura_corte_cm"] == CORTE_PADRAO_ALTURA_CM


def test_inicializar_e_idempotente():
    with base_temporaria():
        db.inicializar()
        db.inicializar()
        assert len(db.listar_cortes()) == 1


def test_seed_nao_ressuscita_apos_registro_novo():
    # Subir a API de novo nao pode reintroduzir o corte inicial nem duplicar nada.
    with base_temporaria():
        db.registrar_corte(data_corte=HOJE, altura_corte_cm=5.0)
        db.inicializar()
        assert len(db.listar_cortes()) == 2


def test_corte_por_ponto_vence_o_geral_dentro_do_raio():
    with base_temporaria():
        db.registrar_corte(
            data_corte=HOJE - dt.timedelta(days=1),
            altura_corte_cm=7.0,
            latitude=-23.40,
            longitude=-46.74,
            raio_influencia_m=500.0,
        )
        dentro = db.corte_vigente(-23.401, -46.740)
        fora = db.corte_vigente(-23.60, -46.50)
        assert dentro["escopo"] == "ponto" and dentro["altura_corte_cm"] == 7.0
        assert fora["escopo"] == "global"


def test_corte_mais_recente_vence_o_mais_antigo():
    with base_temporaria():
        antigo = db.registrar_corte(
            data_corte=HOJE - dt.timedelta(days=5),
            altura_corte_cm=3.0,
            latitude=-23.40,
            longitude=-46.74,
        )
        db.registrar_corte(
            data_corte=HOJE - dt.timedelta(days=2),
            altura_corte_cm=6.0,
            latitude=-23.40,
            longitude=-46.74,
        )
        assert db.corte_vigente(-23.40, -46.74)["altura_corte_cm"] == 6.0
        # E o antigo continua na base: a tabela e historico, nao estado.
        assert antigo["id"] in {c["id"] for c in db.listar_cortes()}


def test_remover_faz_o_corte_anterior_voltar_a_valer():
    with base_temporaria():
        db.registrar_corte(
            data_corte=HOJE - dt.timedelta(days=5),
            altura_corte_cm=3.0,
            latitude=-23.40,
            longitude=-46.74,
        )
        recente = db.registrar_corte(
            data_corte=HOJE - dt.timedelta(days=2),
            altura_corte_cm=6.0,
            latitude=-23.40,
            longitude=-46.74,
        )
        db.remover_corte(recente["id"])
        assert db.corte_vigente(-23.40, -46.74)["altura_corte_cm"] == 3.0


def test_ultimo_corte_global_e_protegido():
    with base_temporaria():
        (global_inicial,) = db.listar_cortes()
        try:
            db.remover_corte(global_inicial["id"])
            raise AssertionError("deveria ter recusado a remocao")
        except db.CorteNaoEncontradoError:
            pass
        # Com outro global na base, o antigo pode sair.
        db.registrar_corte(data_corte=HOJE, altura_corte_cm=4.0)
        db.remover_corte(global_inicial["id"])
        assert db.corte_vigente(-23.40, -46.74)["altura_corte_cm"] == 4.0


def test_corte_no_futuro_e_recusado():
    with base_temporaria():
        try:
            db.registrar_corte(data_corte=HOJE + dt.timedelta(days=1), altura_corte_cm=2.0)
            raise AssertionError("deveria ter recusado data futura")
        except db.CorteInvalidoError:
            pass


def test_altura_absurda_e_coordenada_incompleta_sao_recusadas():
    with base_temporaria():
        for kwargs in (
            {"data_corte": HOJE, "altura_corte_cm": 500.0},
            {"data_corte": HOJE, "altura_corte_cm": -1.0},
            {"data_corte": HOJE, "altura_corte_cm": 2.0, "latitude": -23.4},
        ):
            try:
                db.registrar_corte(**kwargs)
                raise AssertionError(f"deveria ter recusado {kwargs}")
            except db.CorteInvalidoError:
                pass


def test_resolucao_em_lote_bate_com_a_individual():
    with base_temporaria():
        db.registrar_corte(
            data_corte=HOJE - dt.timedelta(days=3),
            altura_corte_cm=8.0,
            latitude=-23.72,
            longitude=-46.56,
            raio_influencia_m=1000.0,
        )
        coords = [(-23.72, -46.56), (-23.40, -46.74), (-23.7205, -46.5605)]
        lote = db.resolver_cortes(coords)
        assert [c["id"] for c in lote] == [db.corte_vigente(*p)["id"] for p in coords]
        assert lote[0]["escopo"] == "ponto" and lote[1]["escopo"] == "global"


def test_dias_desde_corte_e_nao_negativo():
    with base_temporaria():
        corte = db.corte_vigente(-23.40, -46.74)
        data = dt.date.fromisoformat(corte["data_corte"])
        assert db.dias_desde_corte(corte, data + dt.timedelta(days=5)) == 5
        # Data-alvo anterior ao corte: zero dia decorrido, nao numero negativo.
        assert db.dias_desde_corte(corte, data - dt.timedelta(days=5)) == 0


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"OK  {nome}")
    print("Todos os testes de cortes passaram.")
