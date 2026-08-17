"""Banco operacional do EcoTrack: os registros de CORTE informados pela equipe.

Por que este modulo existe
--------------------------
O modelo agronomico (src/growth.py) integra o crescimento a partir de um estado
inicial: a altura logo apos o corte e a data em que ele aconteceu. Ate aqui as
duas eram premissas fixas no codigo -- "cortada hoje, a zero cm" --, o que
tornava o mapa uma projecao hipotetica em vez de um retrato da via. Agora esse
estado inicial e um DADO, guardado aqui e atualizavel pela tela de registro de
cortes.

Modelo de dados
---------------
Uma unica tabela, `cortes`, com dois escopos:

  * `global` -- vale para a rodovia inteira. E o corte geral, o que a
    concessionaria faz quando roca todo o anel. O seed inicial e um destes:
    toda a via cortada a 2 cm em 07/08/2026.
  * `ponto`  -- vale so para o entorno de uma coordenada, dentro de
    `raio_influencia_m`. E o que o operador registra ao clicar numa celula do
    mapa e dizer "este trecho eu cortei ontem, a 5 cm".

Nada e sobrescrito nem apagado quando um corte novo entra: a tabela e um
HISTORICO append-only, e a resolucao escolhe qual registro vale em cada ponto.
Isso preserva a trilha do que foi informado e permite corrigir um registro
errado simplesmente apagando aquela linha -- o corte anterior volta a valer.

Regra de resolucao (`corte_vigente`)
------------------------------------
Entre os registros que se aplicam ao ponto e que ja aconteceram na data de
referencia, vence o de `data_corte` mais recente; empatando a data, vence o de
escopo `ponto` (mais especifico que o corte geral); persistindo o empate, o
registrado por ultimo. Se nenhum se aplicar, cai no padrao de config.py, entao
a resolucao NUNCA devolve vazio -- o modelo de crescimento sempre tem um estado
inicial definido.
"""

from __future__ import annotations

import datetime as dt
import math
import sqlite3
from contextlib import contextmanager

from .config import (
    ALTURA_CORTE_MAX_CM,
    CORTE_PADRAO_ALTURA_CM,
    CORTE_PADRAO_DATA,
    DB_PATH,
    MAX_DIAS_DESDE_CORTE,
    RAIO_CORTE_MAX_M,
    RAIO_CORTE_PADRAO_M,
)

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS cortes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    escopo            TEXT    NOT NULL CHECK (escopo IN ('global', 'ponto')),
    latitude          REAL,
    longitude         REAL,
    raio_influencia_m REAL,
    data_corte        TEXT    NOT NULL,
    altura_corte_cm   REAL    NOT NULL,
    observacao        TEXT,
    criado_em         TEXT    NOT NULL,
    CHECK (
        (escopo = 'global' AND latitude IS NULL AND longitude IS NULL)
        OR (escopo = 'ponto' AND latitude IS NOT NULL AND longitude IS NOT NULL
            AND raio_influencia_m IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_cortes_data ON cortes (data_corte);
"""

# Fatores de conversao grau -> metro na latitude da RMSP (mesma aproximacao
# plana usada em mapa.py; nesta escala o erro e de centimetros).
_M_POR_GRAU_LAT = 111_000.0


class CorteInvalidoError(ValueError):
    """Dados de um registro de corte que nao passam na validacao."""


class CorteNaoEncontradoError(LookupError):
    """Registro de corte inexistente ou que nao pode ser removido."""


def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = (lat2 - lat1) * _M_POR_GRAU_LAT
    dlon = (lon2 - lon1) * 111_320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dlat, dlon)


@contextmanager
def conectar():
    """Conexao SQLite com linhas acessiveis por nome e commit automatico.

    Uma conexao por operacao: os endpoints sincronos do FastAPI rodam num pool
    de threads, e conexao SQLite nao atravessa thread com seguranca.
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def inicializar() -> None:
    """Cria a tabela (se preciso) e semeia o corte geral de referencia.

    O seed so entra numa base vazia -- reiniciar a API nao ressuscita um corte
    que a equipe apagou nem desfaz registros posteriores.
    """
    with conectar() as con:
        con.executescript(_ESQUEMA)
        (total,) = con.execute("SELECT COUNT(*) FROM cortes").fetchone()
        if total == 0:
            con.execute(
                """
                INSERT INTO cortes
                    (escopo, latitude, longitude, raio_influencia_m,
                     data_corte, altura_corte_cm, observacao, criado_em)
                VALUES ('global', NULL, NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    CORTE_PADRAO_DATA,
                    CORTE_PADRAO_ALTURA_CM,
                    "Roçada geral da rodovia (registro inicial do sistema)",
                    dt.datetime.now().isoformat(timespec="seconds"),
                ),
            )


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------
def _para_dict(linha: sqlite3.Row) -> dict:
    return {
        "id": linha["id"],
        "escopo": linha["escopo"],
        "latitude": linha["latitude"],
        "longitude": linha["longitude"],
        "raio_influencia_m": linha["raio_influencia_m"],
        "data_corte": linha["data_corte"],
        "altura_corte_cm": linha["altura_corte_cm"],
        "observacao": linha["observacao"],
        "criado_em": linha["criado_em"],
    }


def listar_cortes() -> list[dict]:
    """Todos os registros, do corte mais recente para o mais antigo."""
    with conectar() as con:
        linhas = con.execute(
            "SELECT * FROM cortes ORDER BY data_corte DESC, id DESC"
        ).fetchall()
    return [_para_dict(linha) for linha in linhas]


def obter_corte(corte_id: int) -> dict:
    with conectar() as con:
        linha = con.execute("SELECT * FROM cortes WHERE id = ?", (corte_id,)).fetchone()
    if linha is None:
        raise CorteNaoEncontradoError(f"corte {corte_id} nao encontrado")
    return _para_dict(linha)


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------
def _validar(
    data_corte: dt.date,
    altura_corte_cm: float,
    latitude: float | None,
    longitude: float | None,
    raio_influencia_m: float | None,
) -> None:
    hoje = dt.date.today()
    if data_corte > hoje:
        raise CorteInvalidoError(
            "a data do corte nao pode estar no futuro (informe quando a roçada "
            "REALMENTE aconteceu)"
        )
    limite = hoje - dt.timedelta(days=MAX_DIAS_DESDE_CORTE)
    if data_corte < limite:
        raise CorteInvalidoError(
            f"corte anterior a {limite.isoformat()}: fora da janela de "
            f"{MAX_DIAS_DESDE_CORTE} dias que o modelo consegue simular"
        )
    if not 0.0 <= altura_corte_cm <= ALTURA_CORTE_MAX_CM:
        raise CorteInvalidoError(
            f"altura de corte fora da faixa aceita (0 a {ALTURA_CORTE_MAX_CM:.0f} cm)"
        )
    if (latitude is None) != (longitude is None):
        raise CorteInvalidoError(
            "informe latitude E longitude, ou nenhuma das duas (corte geral)"
        )
    if latitude is not None:
        if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
            raise CorteInvalidoError("coordenada fora do intervalo valido")
        if raio_influencia_m is not None and not 0.0 < raio_influencia_m <= RAIO_CORTE_MAX_M:
            raise CorteInvalidoError(
                f"raio de influencia fora da faixa (0 a {RAIO_CORTE_MAX_M:.0f} m)"
            )


def registrar_corte(
    data_corte: dt.date,
    altura_corte_cm: float,
    latitude: float | None = None,
    longitude: float | None = None,
    raio_influencia_m: float | None = None,
    observacao: str | None = None,
) -> dict:
    """Grava um corte informado pela equipe e devolve o registro criado.

    Sem coordenada o registro e GLOBAL (vale para toda a rodovia); com
    coordenada vale so dentro de `raio_influencia_m` daquele ponto.
    """
    _validar(data_corte, altura_corte_cm, latitude, longitude, raio_influencia_m)
    escopo = "global" if latitude is None else "ponto"
    raio = None if escopo == "global" else float(raio_influencia_m or RAIO_CORTE_PADRAO_M)

    with conectar() as con:
        cursor = con.execute(
            """
            INSERT INTO cortes
                (escopo, latitude, longitude, raio_influencia_m,
                 data_corte, altura_corte_cm, observacao, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                escopo,
                latitude,
                longitude,
                raio,
                data_corte.isoformat(),
                float(altura_corte_cm),
                (observacao or "").strip() or None,
                dt.datetime.now().isoformat(timespec="seconds"),
            ),
        )
        novo_id = cursor.lastrowid
    return obter_corte(novo_id)


def remover_corte(corte_id: int) -> dict:
    """Apaga um registro; o corte anterior volta a valer naquele trecho.

    O ultimo registro global sobrevivente e protegido: sem ele a rodovia
    ficaria sem estado inicial definido fora dos raios dos cortes por ponto.
    """
    registro = obter_corte(corte_id)
    with conectar() as con:
        if registro["escopo"] == "global":
            (globais,) = con.execute(
                "SELECT COUNT(*) FROM cortes WHERE escopo = 'global'"
            ).fetchone()
            if globais <= 1:
                raise CorteNaoEncontradoError(
                    "este e o unico corte geral da base e nao pode ser removido: "
                    "registre outro corte geral antes de apagar este"
                )
        con.execute("DELETE FROM cortes WHERE id = ?", (corte_id,))
    return registro


# ---------------------------------------------------------------------------
# Resolucao: qual corte vale em cada ponto
# ---------------------------------------------------------------------------
def _corte_padrao() -> dict:
    """Estado inicial de ultimo recurso, quando nada na base se aplica."""
    return {
        "id": None,
        "escopo": "padrao",
        "latitude": None,
        "longitude": None,
        "raio_influencia_m": None,
        "data_corte": CORTE_PADRAO_DATA,
        "altura_corte_cm": CORTE_PADRAO_ALTURA_CM,
        "observacao": "padrao do sistema (nenhum registro aplicavel na base)",
        "criado_em": None,
    }


def _ordenacao(registro: dict) -> tuple:
    """Chave de desempate: data, depois especificidade, depois recencia."""
    return (
        registro["data_corte"],
        1 if registro["escopo"] == "ponto" else 0,
        registro["criado_em"] or "",
        registro["id"] or 0,
    )


def resolver_cortes(
    coordenadas: list[tuple[float, float]], referencia: dt.date | None = None
) -> list[dict]:
    """Corte vigente em cada coordenada, na mesma ordem da entrada.

    Le a tabela UMA vez e resolve todas as coordenadas em memoria -- o mapa
    resolve centenas de celulas por varredura, e uma consulta por celula seria
    desperdicio puro.
    """
    dia = (referencia or dt.date.today()).isoformat()
    registros = [r for r in listar_cortes() if r["data_corte"] <= dia]
    globais = [r for r in registros if r["escopo"] == "global"]
    pontuais = [r for r in registros if r["escopo"] == "ponto"]
    melhor_global = max(globais, key=_ordenacao) if globais else None

    resolvidos = []
    for lat, lon in coordenadas:
        candidatos = [
            r
            for r in pontuais
            if _dist_m(lat, lon, r["latitude"], r["longitude"]) <= r["raio_influencia_m"]
        ]
        if melhor_global is not None:
            candidatos.append(melhor_global)
        resolvidos.append(max(candidatos, key=_ordenacao) if candidatos else _corte_padrao())
    return resolvidos


def corte_vigente(
    latitude: float, longitude: float, referencia: dt.date | None = None
) -> dict:
    """Corte vigente num unico ponto (atalho de `resolver_cortes`)."""
    return resolver_cortes([(latitude, longitude)], referencia)[0]


def dias_desde_corte(corte: dict, alvo: dt.date) -> int:
    """Dias decorridos entre o corte e a data-alvo, limitados pelo modelo."""
    data_corte = dt.date.fromisoformat(corte["data_corte"])
    return min(max((alvo - data_corte).days, 0), MAX_DIAS_DESDE_CORTE)
