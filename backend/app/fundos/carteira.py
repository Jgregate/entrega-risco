"""Composicao da carteira dos fundos - CDA (Composicao e Diversificacao de
Aplicacoes) dos dados abertos da CVM.

A CVM publica um ZIP por mes com a carteira aberta de TODOS os fundos,
quebrada em blocos por tipo de ativo (`cda_fi_BLC_1` a `BLC_8`), mais um
arquivo do exterior (`cda_fie`) e um com o PL de referencia (`cda_fi_PL`).

Estrategia de ingestao - vale explicar porque nao e a obvia: os blocos somam
uns 300 MB de CSV por mes. Filtrar por um CNPJ ainda custa ler o arquivo
inteiro, entao fazer isso "sob demanda, por fundo" pagaria o preco todo de
novo a cada fundo aberto. Aqui o mes e processado UMA vez, para todos os
fundos de uma vez, e o que fica no banco e o agregado - classe de ativo por
fundo e as maiores posicoes por fundo. Depois disso, abrir a carteira de
qualquer fundo daquele mes e uma consulta de milissegundos.

Só o mes mais recente e mantido: carteira e uma foto, nao uma serie, e manter
o historico multiplicaria o banco sem responder nenhuma pergunta da tela.
"""

from __future__ import annotations

import io
import sqlite3
import time
import zipfile

import pandas as pd
import requests

from .._certs import sessao_requests

CDA_URL = "https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/cda_fi_{yyyymm}.zip"
REQUEST_TIMEOUT = 300

# Quantas posicoes individuais guardar por fundo. A tela mostra as maiores; o
# resto vira "demais posicoes" a partir do total da classe, sem perder soma.
TOP_POSICOES = 20

# Cada bloco do CDA tem colunas proprias, mas todos respondem as mesmas tres
# perguntas: o que e, de quem e, e quanto vale. Este mapa e a traducao de cada
# bloco para esse formato comum.
BLOCOS = {
    1: {"descricao": ("TP_TITPUB", "TP_ATIVO"), "emissor": None},
    2: {"descricao": ("NM_FUNDO_CLASSE_SUBCLASSE_COTA",), "emissor": None},
    3: {"descricao": ("TP_APLIC",), "emissor": None},
    4: {"descricao": ("DS_ATIVO", "CD_ATIVO"), "emissor": None},
    5: {"descricao": ("TP_ATIVO",), "emissor": "EMISSOR"},
    6: {"descricao": ("DS_ATIVO", "TP_ATIVO"), "emissor": "EMISSOR"},
    7: {"descricao": ("DS_ATIVO", "TP_ATIVO"), "emissor": "EMISSOR"},
    8: {"descricao": ("DS_ATIVO", "TP_ATIVO"), "emissor": "EMISSOR"},
}

# TP_APLIC da CVM -> classe macro que a tela mostra. O vocabulario da CVM e
# granular demais para um grafico (22 rotulos so no BLC_8); o que o analista
# quer ver e onde o risco esta, nao o nome regulatorio da rubrica.
CLASSES = {
    "Títulos Públicos": "Renda Fixa",
    "Operações Compromissadas": "Caixa e compromissadas",
    "Disponibilidades": "Caixa e compromissadas",
    "Cotas de Fundos": "Fundos",
    "Investimento no Exterior": "Exterior",
    "Ações": "Ações",
    "Ações e outros TVM cedidos em empréstimo": "Ações",
    "Obrigações por ações e outros TVM recebidos em empréstimo": "Ações",
    "Brazilian Depository Receipt - BDR": "Ações",
    "Certificado ou recibo de depósito de valores mobiliários": "Ações",
    "Debêntures": "Crédito privado",
    "Títulos de Crédito Privado": "Crédito privado",
    "Títulos ligados ao agronegócio": "Crédito privado",
    "Depósitos a prazo e outros títulos de IF": "Crédito privado",
    "Mercado Futuro - Posições compradas": "Derivativos",
    "Mercado Futuro - Posições vendidas": "Derivativos",
    "Opções - Posições lançadas": "Derivativos",
    "Opções - Posições titulares": "Derivativos",
    "Compras a termo a receber": "Derivativos",
    "Vendas a termo a receber": "Derivativos",
    "Obrigações por compra a termo a pagar": "Derivativos",
    "Obrigações por venda a termo a entregar": "Derivativos",
    "DIFERENCIAL DE SWAP A PAGAR": "Derivativos",
    "DIFERENCIAL DE SWAP A RECEBER": "Derivativos",
}

CLASSE_PADRAO = "Outros"

# Ordem fixa nos graficos: do mais liquido/conservador ao mais discricionario,
# para a leitura nao mudar de fundo para fundo.
ORDEM_CLASSES = (
    "Renda Fixa",
    "Crédito privado",
    "Ações",
    "Fundos",
    "Exterior",
    "Derivativos",
    "Caixa e compromissadas",
    "Outros",
)


def cria_tabelas(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cda_classes (
            cnpj_fmt TEXT NOT NULL,
            ano      INTEGER NOT NULL,
            mes      INTEGER NOT NULL,
            classe   TEXT NOT NULL,
            valor    REAL NOT NULL,
            PRIMARY KEY (cnpj_fmt, ano, mes, classe)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cda_posicoes (
            cnpj_fmt  TEXT NOT NULL,
            ano       INTEGER NOT NULL,
            mes       INTEGER NOT NULL,
            ordem     INTEGER NOT NULL,
            classe    TEXT NOT NULL,
            tp_aplic  TEXT,
            descricao TEXT,
            emissor   TEXT,
            valor     REAL NOT NULL,
            PRIMARY KEY (cnpj_fmt, ano, mes, ordem)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cda_paises (
            cnpj_fmt TEXT NOT NULL,
            ano      INTEGER NOT NULL,
            mes      INTEGER NOT NULL,
            pais     TEXT NOT NULL,
            valor    REAL NOT NULL,
            PRIMARY KEY (cnpj_fmt, ano, mes, pais)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cda_meses (
            ano        INTEGER NOT NULL,
            mes        INTEGER NOT NULL,
            baixado_em REAL NOT NULL,
            PRIMARY KEY (ano, mes)
        )
        """
    )


def _texto(serie: pd.Series) -> pd.Series:
    return serie.astype("string").str.strip()


def _primeiro_preenchido(df: pd.DataFrame, colunas: tuple[str, ...]) -> pd.Series:
    """Primeira coluna com valor, olhando `colunas` na ordem dada - os blocos
    do CDA nem sempre preenchem o campo mais descritivo."""
    saida = pd.Series(pd.NA, index=df.index, dtype="string")
    for c in colunas:
        if c in df.columns:
            saida = saida.fillna(_texto(df[c]))
    return saida


def _le_bloco(z: zipfile.ZipFile, nome: str, spec: dict) -> pd.DataFrame | None:
    """Um bloco do CDA reduzido ao formato comum (cnpj, classe, descricao,
    emissor, valor)."""
    desejadas = {
        "CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO", "TP_APLIC", "VL_MERC_POS_FINAL",
        *spec["descricao"],
    }
    if spec["emissor"]:
        desejadas.add(spec["emissor"])

    try:
        with z.open(nome) as f:
            df = pd.read_csv(
                f, sep=";", encoding="latin1", low_memory=False,
                usecols=lambda c: c in desejadas,
            )
    except (KeyError, ValueError):
        return None

    if "CNPJ_FUNDO_CLASSE" not in df.columns:
        if "CNPJ_FUNDO" not in df.columns:
            return None
        df = df.rename(columns={"CNPJ_FUNDO": "CNPJ_FUNDO_CLASSE"})
    if "VL_MERC_POS_FINAL" not in df.columns:
        return None

    saida = pd.DataFrame({
        "cnpj_fmt": _texto(df["CNPJ_FUNDO_CLASSE"]),
        "tp_aplic": _texto(df["TP_APLIC"]) if "TP_APLIC" in df.columns else pd.NA,
        "descricao": _primeiro_preenchido(df, spec["descricao"]),
        "emissor": _texto(df[spec["emissor"]]) if spec["emissor"] in df.columns else pd.NA,
        "valor": pd.to_numeric(df["VL_MERC_POS_FINAL"], errors="coerce"),
    })
    return saida.dropna(subset=["cnpj_fmt", "valor"])


def _le_exterior(z: zipfile.ZipFile, nome: str) -> pd.DataFrame | None:
    """Exposicao por pais - so o `cda_fie` tem a coluna PAIS."""
    try:
        with z.open(nome) as f:
            df = pd.read_csv(
                f, sep=";", encoding="latin1", low_memory=False,
                usecols=lambda c: c in {"CNPJ_FUNDO_CLASSE", "PAIS", "VL_MERC_POS_FINAL"},
            )
    except (KeyError, ValueError):
        return None
    if not {"CNPJ_FUNDO_CLASSE", "PAIS", "VL_MERC_POS_FINAL"} <= set(df.columns):
        return None

    saida = pd.DataFrame({
        "cnpj_fmt": _texto(df["CNPJ_FUNDO_CLASSE"]),
        "pais": _texto(df["PAIS"]),
        "valor": pd.to_numeric(df["VL_MERC_POS_FINAL"], errors="coerce"),
    })
    return saida.dropna(subset=["cnpj_fmt", "pais", "valor"])


def _monta(conteudo: bytes, yyyymm: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(classes, posicoes, paises) de todos os fundos daquele mes."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    partes = []
    for n, spec in BLOCOS.items():
        bloco = _le_bloco(z, f"cda_fi_BLC_{n}_{yyyymm}.csv", spec)
        if bloco is not None and len(bloco):
            partes.append(bloco)

    if not partes:
        vazio = pd.DataFrame()
        return vazio, vazio, vazio

    tudo = pd.concat(partes, ignore_index=True)
    tudo["classe"] = (
        tudo["tp_aplic"].map(CLASSES).fillna(CLASSE_PADRAO).astype("string")
    )

    classes = (
        tudo.groupby(["cnpj_fmt", "classe"], observed=True)["valor"].sum().reset_index()
    )

    # posicoes individuais: as maiores em modulo, porque uma posicao vendida
    # grande importa tanto quanto uma comprada grande
    tudo["_abs"] = tudo["valor"].abs()
    posicoes = (
        tudo.sort_values("_abs", ascending=False)
        .groupby("cnpj_fmt", observed=True)
        .head(TOP_POSICOES)
        .drop(columns="_abs")
        .reset_index(drop=True)
    )
    posicoes["ordem"] = posicoes.groupby("cnpj_fmt", observed=True).cumcount()

    paises = _le_exterior(z, f"cda_fie_{yyyymm}.csv")
    if paises is None or paises.empty:
        paises = pd.DataFrame(columns=["cnpj_fmt", "pais", "valor"])
    else:
        paises = paises.groupby(["cnpj_fmt", "pais"], observed=True)["valor"].sum().reset_index()

    return classes, posicoes, paises


# --------------------------------------------------------------------------- #
# Ingestao
# --------------------------------------------------------------------------- #

def _grava(conn, ano, mes, classes, posicoes, paises) -> None:
    conn.execute("DELETE FROM cda_classes WHERE ano = ? AND mes = ?", (ano, mes))
    conn.execute("DELETE FROM cda_posicoes WHERE ano = ? AND mes = ?", (ano, mes))
    conn.execute("DELETE FROM cda_paises WHERE ano = ? AND mes = ?", (ano, mes))

    conn.executemany(
        "INSERT OR REPLACE INTO cda_classes (cnpj_fmt, ano, mes, classe, valor) "
        "VALUES (?, ?, ?, ?, ?)",
        [(r.cnpj_fmt, ano, mes, r.classe, float(r.valor)) for r in classes.itertuples()],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO cda_posicoes "
        "(cnpj_fmt, ano, mes, ordem, classe, tp_aplic, descricao, emissor, valor) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                r.cnpj_fmt, ano, mes, int(r.ordem), r.classe,
                None if pd.isna(r.tp_aplic) else str(r.tp_aplic),
                None if pd.isna(r.descricao) else str(r.descricao),
                None if pd.isna(r.emissor) else str(r.emissor),
                float(r.valor),
            )
            for r in posicoes.itertuples()
        ],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO cda_paises (cnpj_fmt, ano, mes, pais, valor) "
        "VALUES (?, ?, ?, ?, ?)",
        [(r.cnpj_fmt, ano, mes, r.pais, float(r.valor)) for r in paises.itertuples()],
    )
    # carteira e uma foto, nao uma serie: o mes novo substitui o anterior
    for tabela in ("cda_classes", "cda_posicoes", "cda_paises"):
        conn.execute(
            f"DELETE FROM {tabela} WHERE NOT (ano = ? AND mes = ?)", (ano, mes)
        )
    conn.execute("DELETE FROM cda_meses")
    conn.execute(
        "INSERT OR REPLACE INTO cda_meses (ano, mes, baixado_em) VALUES (?, ?, ?)",
        (ano, mes, time.time()),
    )
    conn.commit()


def mes_em_cache(conn: sqlite3.Connection) -> tuple[int, int] | None:
    row = conn.execute("SELECT ano, mes FROM cda_meses ORDER BY ano DESC, mes DESC").fetchone()
    return (row[0], row[1]) if row else None


def ingere(conn: sqlite3.Connection, candidatos: list[tuple[int, int]]) -> tuple[int, int] | None:
    """Baixa e processa o mes mais recente do CDA que existir entre os
    `candidatos` (do mais novo para o mais antigo).

    A CVM publica o CDA com defasagem maior que o informe diario, e a
    defasagem varia; por isso a busca tenta alguns meses para tras em vez de
    assumir um numero fixo.
    """
    for ano, mes in candidatos:
        yyyymm = f"{ano}{mes:02d}"
        try:
            resp = sessao_requests().get(CDA_URL.format(yyyymm=yyyymm), timeout=REQUEST_TIMEOUT)
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue

        try:
            classes, posicoes, paises = _monta(resp.content, yyyymm)
        except (zipfile.BadZipFile, ValueError):
            continue
        if classes.empty:
            continue

        _grava(conn, ano, mes, classes, posicoes, paises)
        return (ano, mes)
    return None


def invalida(conn: sqlite3.Connection) -> None:
    """Zera o carimbo para o proximo acesso reprocessar, mantendo os dados no
    ar enquanto isso."""
    conn.execute("UPDATE cda_meses SET baixado_em = 0")
    conn.commit()


def precisa_rebaixar(conn: sqlite3.Connection, horas: float) -> bool:
    row = conn.execute("SELECT MAX(baixado_em) FROM cda_meses").fetchone()
    if row is None or row[0] is None:
        return True
    return (time.time() - row[0]) >= horas * 3600


# --------------------------------------------------------------------------- #
# Leitura
# --------------------------------------------------------------------------- #

def composicao(conn: sqlite3.Connection, cnpj_fmt: str) -> dict | None:
    """Carteira de um fundo no mes em cache, ja em percentual do total."""
    ym = mes_em_cache(conn)
    if ym is None:
        return None
    ano, mes = ym

    classes = conn.execute(
        "SELECT classe, valor FROM cda_classes WHERE cnpj_fmt = ? AND ano = ? AND mes = ?",
        (cnpj_fmt, ano, mes),
    ).fetchall()
    if not classes:
        return None

    # o denominador e a soma dos valores POSITIVOS: posicoes passivas
    # (obrigacoes, vendas a termo) entram com sinal negativo no CDA e
    # encolheriam o total, distorcendo todos os percentuais para cima
    total = sum(v for _, v in classes if v > 0) or sum(abs(v) for _, v in classes)

    def pct(v):
        return round(v / total, 6) if total else None

    ordem = {c: i for i, c in enumerate(ORDEM_CLASSES)}
    por_classe = sorted(
        ({"classe": c, "valor": v, "percentual": pct(v)} for c, v in classes),
        key=lambda d: ordem.get(d["classe"], len(ORDEM_CLASSES)),
    )

    posicoes = conn.execute(
        "SELECT classe, tp_aplic, descricao, emissor, valor FROM cda_posicoes "
        "WHERE cnpj_fmt = ? AND ano = ? AND mes = ? ORDER BY ordem",
        (cnpj_fmt, ano, mes),
    ).fetchall()

    paises = conn.execute(
        "SELECT pais, valor FROM cda_paises WHERE cnpj_fmt = ? AND ano = ? AND mes = ? "
        "ORDER BY valor DESC",
        (cnpj_fmt, ano, mes),
    ).fetchall()

    emissores: dict[str, float] = {}
    for _, _, _, emissor, valor in posicoes:
        if emissor:
            emissores[emissor] = emissores.get(emissor, 0.0) + valor

    return {
        "referencia": f"{mes:02d}/{ano}",
        "total": total,
        "por_classe": por_classe,
        "posicoes": [
            {
                "classe": c, "tipo": tp, "descricao": d, "emissor": e,
                "valor": v, "percentual": pct(v),
            }
            for c, tp, d, e, v in posicoes
        ],
        "emissores": [
            {"emissor": e, "valor": v, "percentual": pct(v)}
            for e, v in sorted(emissores.items(), key=lambda kv: -abs(kv[1]))
        ],
        "paises": [
            {"pais": p, "valor": v, "percentual": pct(v)} for p, v in paises
        ],
    }
