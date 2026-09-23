"""Camada de dados publicos - CVM (fundos) e Banco Central (CDI).

Adaptado do sistema FUNDOS original (Streamlit). Duas mudancas de fundo em
relacao aquele:

1. Sem Streamlit: nada de `st.cache_data` nem sessao de usuario. Os TTLs de
   atualizacao (`ATUALIZACAO_HORAS`) sao os mesmos, so que aplicados a um
   cache proprio.
2. Cache escalavel: o gargalo do original era reparseir o CSV de dentro do
   ZIP mensal (varios MB) a cada cache-miss, num dict Python que nao
   sobrevive a restart nem e compartilhado entre processos. Aqui, o
   resultado JA PARSEADO de cada mes fica em SQLite (`backend/data/
   fundos_cache.db`) - meses fechados antigos nunca sao reparseados de novo,
   e qualquer worker Uvicorn le o mesmo banco.

Fontes: dados.cvm.gov.br/dados/FI (dados abertos CVM) e api.bcb.gov.br (SGS/BCB).
"""

from __future__ import annotations

import calendar
import io
import os
import re
import sqlite3
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .._certs import sessao_requests
from . import cadastro, carteira

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DATA_DIR / "fundos_cache.db"
INFORMES_DIR = DATA_DIR / "cvm_informes"

INFORME_URL = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{yyyymm}.zip"
BCB_CDI_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"

# Teto de historico que o sistema aceita voltar. "Desde o inicio do fundo"
# significa, na pratica, "desde o inicio dentro desta janela": cada mes a mais
# e um ZIP de ~11 MB baixado e parseado uma vez. 10 anos cobrem o historico
# relevante de praticamente qualquer classe ativa sem transformar a primeira
# consulta numa espera de minutos.
MAX_MESES_HISTORICO = 120

REQUEST_TIMEOUT = 30
# leitura de cada mes e I/O + parsing em C (libera o GIL boa parte do tempo),
# entao mais threads do que nucleos ainda ajuda; 16 e um bom equilibrio entre
# velocidade no primeiro carregamento e uso de memoria/CPU
MAX_WORKERS = 16

# Os dois ultimos meses fechados sao os unicos que a CVM ainda pode revisar
# (correcoes tardias de fundos/custodiantes). Por isso so eles sao
# rebaixados periodicamente; meses mais antigos ficam em cache para sempre
# (nunca mudam, tanto no banco quanto no ZIP baixado). O endpoint de
# atualizacao forca uma checagem na hora, ignorando essa janela.
MESES_RECENTES = 1

# Meses num ano - anualizacao das metricas mensais do ranking.
MESES_ANO = 12
ATUALIZACAO_HORAS = 6

# cache em memoria leve para chamadas de rede baratas de refazer (CDI,
# indices via Yahoo, ranking Top N) - mesmo padrao TTL simples de
# app/data.py; a parte cara (parse dos informes mensais) vive no SQLite,
# nao aqui.
_CACHE: dict[tuple, tuple[float, object]] = {}


def _cache_get(chave: tuple):
    item = _CACHE.get(chave)
    if item is None:
        return None
    carimbo, valor = item
    if time.time() - carimbo >= ATUALIZACAO_HORAS * 3600:
        return None
    return valor


def _cache_set(chave: tuple, valor: object) -> None:
    _CACHE[chave] = (time.time(), valor)


def _cnpj_fmt(digits):
    d = re.sub(r"\D", "", str(digits)).zfill(14)
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"


# --------------------------------------------------------------------------- #
# Banco SQLite (substitui o dict/dict-de-sessao do Streamlit)
# --------------------------------------------------------------------------- #

def _connect() -> sqlite3.Connection:
    """Cada chamada de rede que baixa/parseia um mes roda numa thread do
    ThreadPoolExecutor e abre sua propria conexao (sqlite3.Connection nao e
    thread-safe para reuso entre threads). Sem WAL, gravacoes concorrentes de
    varias threads batem de frente e o SQLite derruba a mais lenta com
    "database is locked" - WAL + timeout maior deixam o SQLite serializar as
    escritas em vez de desistir."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cotas_mensais (
            cnpj_fmt      TEXT NOT NULL,
            ano           INTEGER NOT NULL,
            mes           INTEGER NOT NULL,
            vl_quota      REAL NOT NULL,
            vl_patrim_liq REAL,
            nr_cotst      INTEGER,
            PRIMARY KEY (cnpj_fmt, ano, mes)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meses_baixados (
            ano        INTEGER NOT NULL,
            mes        INTEGER NOT NULL,
            baixado_em REAL NOT NULL,
            PRIMARY KEY (ano, mes)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cotas_diarias (
            cnpj_fmt      TEXT NOT NULL,
            data          TEXT NOT NULL,
            vl_quota      REAL NOT NULL,
            vl_patrim_liq REAL,
            vl_total      REAL,
            captc_dia     REAL,
            resg_dia      REAL,
            nr_cotst      INTEGER,
            PRIMARY KEY (cnpj_fmt, data)
        )
        """
    )
    # Marca quais (fundo, mes) ja tiveram a serie diaria extraida. Sem isso nao
    # da para distinguir "mes sem nenhuma cota reportada para esse fundo" de
    # "mes que ainda nao foi lido" - e o primeiro caso e comum (fundo novo,
    # fundo encerrado, fundo que nao reportou).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dias_lidos (
            cnpj_fmt TEXT NOT NULL,
            ano      INTEGER NOT NULL,
            mes      INTEGER NOT NULL,
            lido_em  REAL NOT NULL,
            PRIMARY KEY (cnpj_fmt, ano, mes)
        )
        """
    )
    cadastro.cria_tabelas(conn)
    carteira.cria_tabelas(conn)
    return conn


def _read_informe(path, extra_cols=()):
    """Le o informe diario de um mes, tolerando os dois formatos que a CVM
    ja usou: ate nov/2023 a coluna de CNPJ se chamava CNPJ_FUNDO; a partir
    de dez/2023 (Resolucao CVM 175, fundos organizados em "classes") passou
    a ser CNPJ_FUNDO_CLASSE. Sempre devolve a coluna como CNPJ_FUNDO_CLASSE,
    ou None se o arquivo nao existir/nao puder ser lido em nenhum formato.

    Linhas com VL_QUOTA <= 0 sao descartadas aqui, na fonte unica que todo o
    resto do modulo consome (cache mensal, serie diaria, book). Cota de fundo
    nunca e legitimamente zero ou negativa; quando a CVM publica isso, e
    artefato de migracao de classe (RCVM 175) ou erro de reporte do
    administrador - visto na pratica em pelo menos um CNPJ_FUNDO_CLASSE que
    reporta VL_QUOTA=0 por semanas antes de retomar o valor normal. Sem este
    filtro, esse zero e tratado como preco real: derruba a posicao a zero no
    valor consolidado do book e produz um salto de centenas de % quando o
    valor volta - silencioso em qualquer lugar que nao seja o grafico."""
    try:
        with zipfile.ZipFile(path) as z:
            name = z.namelist()[0]
            for cnpj_col in ("CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO"):
                try:
                    with z.open(name) as f:
                        df = pd.read_csv(
                            f, sep=";",
                            usecols=[cnpj_col, "DT_COMPTC", "VL_QUOTA", *extra_cols],
                            dtype={cnpj_col: str, "VL_QUOTA": float,
                                   **{c: float for c in extra_cols}},
                        )
                    if cnpj_col != "CNPJ_FUNDO_CLASSE":
                        df = df.rename(columns={cnpj_col: "CNPJ_FUNDO_CLASSE"})
                    return df[df["VL_QUOTA"] > 0].reset_index(drop=True)
                except ValueError:
                    continue
    except zipfile.BadZipFile:
        return None
    return None


def _month_range(n_months, ref=None):
    """Lista de (ano, mes) com n_months + 1 meses FECHADOS mais recentes,
    do mais antigo para o mais novo (o mes corrente nunca entra, so meses
    encerrados)."""
    ref = ref or date.today()
    y, m = ref.year, ref.month
    months = []
    for i in range(1, n_months + 2):
        mm = m - i
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        months.append((yy, mm))
    months.reverse()
    return months


def _mes_e_recente(year, month, ref=None):
    """True para o mes atual (aberto) e os MESES_RECENTES meses fechados
    mais novos - os unicos que a CVM ainda pode revisar."""
    ref = ref or date.today()
    diff = (ref.year - year) * 12 + (ref.month - month)
    return diff <= MESES_RECENTES


def _mes_n_atras(n, ref=None):
    """Mes fechado n meses antes do ultimo mes fechado (n=0 -> ultimo mes
    fechado, o mesmo usado como base em todo o resto do modulo)."""
    y, m = _month_range(0, ref=ref)[-1]
    m -= n
    while m <= 0:
        m += 12
        y -= 1
    return (y, m)


def _download_month(year, month):
    """Baixa (ou reaproveita do disco) o ZIP bruto de um mes. So chamado
    quando o banco ainda nao tem esse mes ou precisa rebaixar (mes recente,
    TTL vencido)."""
    INFORMES_DIR.mkdir(parents=True, exist_ok=True)
    yyyymm = f"{year}{month:02d}"
    path = INFORMES_DIR / f"inf_diario_fi_{yyyymm}.zip"

    url = INFORME_URL.format(yyyymm=yyyymm)
    try:
        resp = sessao_requests().get(url, timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        return path if path.exists() else None
    if resp.status_code != 200:
        return path if path.exists() else None
    path.write_bytes(resp.content)
    return path


def _precisa_rebaixar(conn, year, month) -> bool:
    if not _mes_e_recente(year, month):
        return False  # mes antigo e imutavel - nunca rebaixa
    row = conn.execute(
        "SELECT baixado_em FROM meses_baixados WHERE ano = ? AND mes = ?", (year, month)
    ).fetchone()
    if row is None:
        return True
    return (time.time() - row[0]) >= ATUALIZACAO_HORAS * 3600


def _mes_no_banco(conn, year, month):
    """Instantaneo (VL_QUOTA/VL_PATRIM_LIQ/NR_COTST por CNPJ) do banco, ou
    None se esse mes nunca foi baixado com sucesso."""
    row = conn.execute(
        "SELECT 1 FROM meses_baixados WHERE ano = ? AND mes = ?", (year, month)
    ).fetchone()
    if row is None:
        return None
    df = pd.read_sql(
        "SELECT cnpj_fmt, vl_quota, vl_patrim_liq, nr_cotst FROM cotas_mensais "
        "WHERE ano = ? AND mes = ?",
        conn, params=(year, month),
    )
    return df.set_index("cnpj_fmt").rename(
        columns={"vl_quota": "VL_QUOTA", "vl_patrim_liq": "VL_PATRIM_LIQ", "nr_cotst": "NR_COTST"}
    )


def _grava_mes(conn, year, month, df: pd.DataFrame) -> None:
    rows = [
        (
            r.CNPJ_FUNDO_CLASSE, year, month, float(r.VL_QUOTA),
            float(r.VL_PATRIM_LIQ) if pd.notna(getattr(r, "VL_PATRIM_LIQ", None)) else None,
            int(r.NR_COTST) if pd.notna(getattr(r, "NR_COTST", None)) else None,
        )
        for r in df.itertuples()
    ]
    conn.execute("DELETE FROM cotas_mensais WHERE ano = ? AND mes = ?", (year, month))
    conn.executemany(
        "INSERT INTO cotas_mensais (cnpj_fmt, ano, mes, vl_quota, vl_patrim_liq, nr_cotst) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.execute(
        "INSERT OR REPLACE INTO meses_baixados (ano, mes, baixado_em) VALUES (?, ?, ?)",
        (year, month, time.time()),
    )
    conn.commit()


def _snapshot_mes(year, month):
    """Ultima cota, patrimonio e num. de cotistas de TODOS os fundos no
    mes, vindos do SQLite sempre que possivel (um unico parse por mes, para
    sempre) - so cai pro ZIP quando o mes ainda nao esta no banco ou precisa
    ser rebaixado (mes recente dentro do TTL de revisao da CVM)."""
    conn = _connect()
    try:
        cache_atual = _mes_no_banco(conn, year, month)
        if cache_atual is not None and not _precisa_rebaixar(conn, year, month):
            return cache_atual

        path = _download_month(year, month)
        if path is None:
            return cache_atual  # rede falhou - fica com o que ja tinha (ou None)

        df = _read_informe(path, extra_cols=["VL_PATRIM_LIQ", "NR_COTST"])
        if df is None:
            return cache_atual

        df = df.sort_values("DT_COMPTC").drop_duplicates(subset="CNPJ_FUNDO_CLASSE", keep="last")
        _grava_mes(conn, year, month, df)
        return _mes_no_banco(conn, year, month)
    finally:
        conn.close()


def _unique_cnpjs_no_mes(year, month):
    """CNPJs (formatados) que aparecem no informe diario daquele mes, ou
    None se o arquivo nao pode ser obtido."""
    snap = _snapshot_mes(year, month)
    if snap is None:
        return None
    return set(snap.index)


def _cnpjs_com_dados_recentes():
    """CNPJs que reportaram cota nos dois ultimos meses fechados - usado
    para tirar da busca fundos sem historico recente suficiente para
    calcular metricas (novos demais, encerrados, sem cotas publicadas)."""
    ultimo = _mes_n_atras(0)
    anterior = _mes_n_atras(1)

    c1 = _unique_cnpjs_no_mes(*ultimo)
    c2 = _unique_cnpjs_no_mes(*anterior)
    if c1 is None:
        return c2
    if c2 is None:
        return c1
    return c1 & c2


# --------------------------------------------------------------------------- #
# Cadastro e busca de fundos
# --------------------------------------------------------------------------- #

def load_registry() -> pd.DataFrame:
    """Classes de fundos ATIVAS na CVM que de fato reportaram cota
    recentemente (ou seja: tem historico para analisar).

    Continua devolvendo `cnpj_fmt` + `Denominacao_Social` porque e o contrato
    que o ranking Top N consome; as colunas de classificacao vem junto para o
    filtro de categoria do ranking nao precisar de uma segunda consulta, e o
    cadastro completo continua saindo por `cadastro_fundo`.
    """
    conn = _connect()
    try:
        if cadastro.precisa_rebaixar(conn):
            cadastro.rebaixa(conn)
        df = pd.read_sql(
            "SELECT cnpj_fmt, nome AS Denominacao_Social, gestora, codigo_cvm, "
            "       tipo_fundo, classificacao_cvm, classificacao_anbima, previdenciario "
            "FROM cadastro WHERE situacao = ?",
            conn, params=(cadastro.SITUACAO_ATIVA,),
        )
    finally:
        conn.close()

    df = df.dropna(subset=["Denominacao_Social"])
    cnpjs_ativos = _cnpjs_com_dados_recentes()
    if cnpjs_ativos:
        df = df[df["cnpj_fmt"].isin(cnpjs_ativos)]
    return df.reset_index(drop=True)


def search_funds(query, registry, limit=40):
    """Filtra o registro por nome, CNPJ, codigo CVM ou gestora.

    Os quatro campos entram na mesma caixa de busca porque o usuario nao sabe
    de antemao qual deles tem em maos - e o formato do que ele digitou ja
    diz quase sempre o que ele quis dizer. So o nome e a gestora usam
    substring; CNPJ e codigo CVM comparam por digitos, para funcionar tanto
    com `12.345.678/0001-90` quanto com `12345678000190`.
    """
    q = str(query).strip()
    if not q:
        return registry.head(0)

    alvo = registry
    nome = alvo["Denominacao_Social"].str.upper()
    gestora = alvo["gestora"].fillna("").str.upper()
    mask = nome.str.contains(q.upper(), regex=False) | gestora.str.contains(
        q.upper(), regex=False
    )

    digitos = re.sub(r"\D", "", q)
    if digitos:
        cnpj_digitos = alvo["cnpj_fmt"].str.replace(r"\D", "", regex=True)
        mask = mask | cnpj_digitos.str.contains(digitos, regex=False)
        mask = mask | alvo["codigo_cvm"].fillna("").astype(str).str.strip().eq(
            digitos.lstrip("0")
        )

    # nome comecando com o termo vem antes de nome que so o contem
    achados = alvo[mask].copy()
    achados["_rank"] = (~nome[mask].str.startswith(q.upper())).astype(int)
    return achados.sort_values(["_rank", "Denominacao_Social"]).head(limit)


def fund_by_cnpj(cnpj_fmt: str, registry: pd.DataFrame) -> str | None:
    linha = registry[registry["cnpj_fmt"] == cnpj_fmt]
    return None if linha.empty else str(linha.iloc[0]["Denominacao_Social"])


def cadastro_fundo(cnpj_fmt: str) -> dict | None:
    """Linha completa do cadastro institucional de uma classe, ou None."""
    conn = _connect()
    try:
        if cadastro.precisa_rebaixar(conn):
            cadastro.rebaixa(conn)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM cadastro WHERE cnpj_fmt = ?", (cnpj_fmt,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    dados = {k: row[k] for k in row.keys() if k != "atualizado_em"}
    return dados


# --------------------------------------------------------------------------- #
# Ranking Top N
# --------------------------------------------------------------------------- #

def _metricas_mensais(quotas: pd.DataFrame, meses: int, cdi_acumulado: float | None):
    """Volatilidade, drawdown maximo e Sharpe da janela, a partir das cotas
    mensais - as mesmas colunas que ja sustentam o retorno do ranking.

    Tudo aqui e mensal por construcao: o ranking varre o mercado inteiro, e
    baixar a serie diaria de 25 mil fundos para refinar a terceira casa da
    volatilidade custaria minutos por consulta. Os numeros da tela do fundo
    (diarios) sao os finos; estes servem para comparar fundos entre si dentro
    da mesma janela.

    Sharpe so sai em janelas de pelo menos 12 meses, pela mesma razao que
    `analytics.anualizado` nao extrapola periodo curto: anualizar 1 mes de
    alta produz um numero que o usuario leria como projecao.
    """
    mensais = quotas.pct_change(axis=1)
    vol = mensais.std(axis=1, ddof=1) * np.sqrt(MESES_ANO)

    curva = quotas.div(quotas.iloc[:, 0], axis=0)
    drawdown = (curva / curva.cummax(axis=1) - 1.0).min(axis=1)

    retorno = quotas.iloc[:, -1] / quotas.iloc[:, 0] - 1.0
    if meses >= MESES_ANO and cdi_acumulado is not None:
        expoente = MESES_ANO / meses
        ann = (1.0 + retorno).clip(lower=0.0) ** expoente - 1.0
        cdi_ann = (1.0 + cdi_acumulado) ** expoente - 1.0
        sharpe = (ann - cdi_ann) / vol.replace(0.0, np.nan)
    else:
        sharpe = pd.Series(np.nan, index=quotas.index)

    return vol * 100, drawdown * 100, sharpe


def _ranking_a_partir_de(
    quotas: pd.DataFrame,
    snap_final: pd.DataFrame,
    registry: pd.DataFrame,
    min_cotistas: int,
    salto_mensal_max: float,
    top_n: int,
    cdi_acumulado: float | None = None,
) -> pd.DataFrame:
    """Nucleo puro do ranking (sem rede/banco) - isolado para ser testavel
    com DataFrames sinteticos.

    `registry` ja chega filtrado pela categoria escolhida: o merge no fim e
    `inner`, entao quem nao esta no registry simplesmente nao entra no ranking.
    """
    primeiro, ultimo = quotas.columns[0], quotas.columns[-1]
    base = quotas[[primeiro, ultimo]].dropna()
    # cota inicial zerada ou negativa produz retorno infinito e, sem este
    # filtro, esse fundo encabeca o ranking com um numero que nao existe
    base = base[(base[primeiro] > 0) & (base[ultimo] > 0)]
    if base.empty:
        return pd.DataFrame()
    retorno_total = (base[ultimo] / base[primeiro] - 1) * 100
    retorno_total = retorno_total[np.isfinite(retorno_total)]
    if retorno_total.empty:
        return pd.DataFrame()

    janela = quotas.loc[retorno_total.index]

    # saltos mensais acima do limite quase sempre sao desdobramento/
    # grupamento de cotas ou erro de reporte da CVM, nao desempenho real
    pico_mensal = janela.pct_change(axis=1).abs().max(axis=1) * 100
    sem_saltos = pico_mensal <= salto_mensal_max

    vol, drawdown, sharpe = _metricas_mensais(
        janela, len(quotas.columns) - 1, cdi_acumulado
    )

    resultado = pd.DataFrame({
        "cnpj_fmt": retorno_total.index,
        "retorno_%": retorno_total.values,
        "volatilidade_%": vol.values,
        "drawdown_%": drawdown.values,
        "sharpe": sharpe.values,
        "patrimonio_mi": (snap_final["VL_PATRIM_LIQ"].reindex(retorno_total.index) / 1e6).values,
        "cotistas": snap_final["NR_COTST"].reindex(retorno_total.index).values,
    })
    resultado = resultado[sem_saltos.values & (resultado["cotistas"] >= min_cotistas)]

    colunas = ["cnpj_fmt", "Denominacao_Social"]
    colunas += [c for c in ("gestora", "categoria") if c in registry.columns]
    resultado = resultado.merge(registry[colunas], on="cnpj_fmt", how="inner")
    return resultado.sort_values("retorno_%", ascending=False).head(top_n).reset_index(drop=True)


def _registry_da_categoria(chave: str | None) -> pd.DataFrame:
    """Registry com a coluna `categoria`, filtrado quando uma foi pedida."""
    registry = load_registry()
    if registry.empty:
        return registry
    registry = registry.assign(
        categoria=registry.apply(cadastro.categoria, axis=1)
    )
    if chave:
        registry = registry[registry["categoria"] == chave]
    return registry


def _cdi_acumulado(months) -> float | None:
    """CDI composto da janela (decimal), ou None se o BCB nao responder."""
    try:
        mensal = fetch_cdi_monthly(months[1:])
    except (requests.RequestException, ValueError, KeyError):
        # o CDI aqui so alimenta o Sharpe; sem ele o ranking ainda vale
        return None
    if not mensal:
        return None
    return float(np.prod([1.0 + m / 100.0 for m in mensal]) - 1.0)


def top_funds_by_return(
    meses, top_n=10, min_cotistas=100, salto_mensal_max=80.0, categoria=None
):
    """Os top_n fundos com maior retorno acumulado nos ultimos `meses` meses
    (janela fechada), entre os fundos com pelo menos min_cotistas cotistas
    (evita fundos exclusivos/institucionais distorcendo o ranking), sem
    nenhum salto mensal acima de salto_mensal_max% e, se `categoria` vier,
    so os fundos daquela categoria (ver `cadastro.CATEGORIAS`).

    Uma ressalva que a interface precisa dizer ao usuario: a fonte aqui e o
    informe diario (INF_DIARIO), que cobre as classes do tipo FIF. FII, ETF,
    Fiagro e boa parte dos FIDC/FIP nao reportam nele, entao essas categorias
    saem com poucos fundos ou vazias - o que e uma lacuna da fonte, nao uma
    ausencia de fundos.
    """
    chave = ("top10", meses, top_n, min_cotistas, salto_mensal_max, categoria)
    cacheado = _cache_get(chave)
    if cacheado is not None:
        return cacheado.copy()

    month_range = _month_range(meses)  # meses + 1 meses, antigo -> novo

    snaps = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(_snapshot_mes, y, m): (y, m) for y, m in month_range}
        for fut in as_completed(futures):
            snaps[futures[fut]] = fut.result()

    meses_validos = [ym for ym in month_range if snaps.get(ym) is not None]
    if len(meses_validos) < 2:
        return pd.DataFrame()

    quotas = pd.DataFrame({ym: snaps[ym]["VL_QUOTA"] for ym in meses_validos})[meses_validos]
    resultado = _ranking_a_partir_de(
        quotas,
        snaps[meses_validos[-1]],
        _registry_da_categoria(categoria),
        min_cotistas,
        salto_mensal_max,
        top_n,
        _cdi_acumulado(meses_validos),
    )
    _cache_set(chave, resultado)
    return resultado.copy()


# --------------------------------------------------------------------------- #
# Serie DIARIA de um fundo
# --------------------------------------------------------------------------- #
#
# O informe diario traz uma linha por (classe, pregao). O modulo original so
# guardava o fechamento de cada mes, o que basta para retorno mensal mas nao
# para o que esta tela precisa: janela de 1 mes, drawdown, volatilidade movel
# e patrimonio dia a dia. Entao a serie diaria tambem e persistida - mas so
# dos fundos que alguem realmente abriu, porque guardar todos os fundos de
# todos os dias seriam dezenas de milhoes de linhas para um punhado que
# interessa.

COLUNAS_DIARIAS = ("VL_PATRIM_LIQ", "VL_TOTAL", "CAPTC_DIA", "RESG_DIA", "NR_COTST")


def _ou_nulo(valor):
    return None if pd.isna(valor) else float(valor)


def _meses_entre(inicio: date, fim: date) -> list[tuple[int, int]]:
    """Todos os (ano, mes) de `inicio` a `fim`, inclusive, do mais antigo
    para o mais novo."""
    meses = []
    y, m = inicio.year, inicio.month
    while (y, m) <= (fim.year, fim.month):
        meses.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return meses


def _dias_ja_lidos(conn, cnpjs, year, month) -> set[str]:
    marcas = conn.execute(
        "SELECT cnpj_fmt FROM dias_lidos WHERE ano = ? AND mes = ? "
        "AND cnpj_fmt IN ({})".format(",".join("?" * len(cnpjs))),
        (year, month, *cnpjs),
    ).fetchall()
    return {r[0] for r in marcas}


def _ingere_mes_diario(cnpjs: tuple[str, ...], year: int, month: int) -> None:
    """Le o ZIP de um mes uma unica vez e grava a serie diaria de todos os
    `cnpjs` pedidos.

    Recebe varios CNPJs de proposito: analisar um book de 12 fundos nao pode
    custar 12 leituras do mesmo arquivo de meio milhao de linhas.
    """
    conn = _connect()
    try:
        faltando = tuple(c for c in cnpjs if c not in _dias_ja_lidos(conn, cnpjs, year, month))
        if not faltando:
            return

        path = _download_month(year, month)
        if path is None:
            return  # sem rede e sem arquivo local: nada a gravar, tenta de novo depois

        df = _read_informe(path, extra_cols=COLUNAS_DIARIAS)
        if df is None:
            return

        df = df[df["CNPJ_FUNDO_CLASSE"].isin(faltando)]
        linhas = [
            (
                r.CNPJ_FUNDO_CLASSE,
                str(r.DT_COMPTC)[:10],
                float(r.VL_QUOTA),
                _ou_nulo(r.VL_PATRIM_LIQ),
                _ou_nulo(r.VL_TOTAL),
                _ou_nulo(r.CAPTC_DIA),
                _ou_nulo(r.RESG_DIA),
                None if pd.isna(r.NR_COTST) else int(r.NR_COTST),
            )
            for r in df.itertuples()
            if pd.notna(r.VL_QUOTA)
        ]
        if linhas:
            conn.executemany(
                "INSERT OR REPLACE INTO cotas_diarias "
                "(cnpj_fmt, data, vl_quota, vl_patrim_liq, vl_total, captc_dia, "
                "resg_dia, nr_cotst) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                linhas,
            )
        # marca TODOS os pedidos, inclusive os que nao renderam linha nenhuma:
        # "li esse mes e esse fundo nao reportou" tambem e resposta, e nao pode
        # virar releitura do ZIP a cada consulta
        agora = time.time()
        conn.executemany(
            "INSERT OR REPLACE INTO dias_lidos (cnpj_fmt, ano, mes, lido_em) "
            "VALUES (?, ?, ?, ?)",
            [(c, year, month, agora) for c in faltando],
        )
        conn.commit()
    finally:
        conn.close()


def _garante_series_diarias(cnpjs: tuple[str, ...], meses: list[tuple[int, int]]) -> None:
    """Garante que todos os pares (fundo, mes) pedidos estejam no banco.

    Meses fechados antigos ja lidos nunca sao relidos; os recentes seguem a
    mesma regra de revisao da CVM usada no resto do modulo.
    """
    conn = _connect()
    try:
        pendentes = []
        for y, m in meses:
            lidos = _dias_ja_lidos(conn, cnpjs, y, m)
            if _mes_e_recente(y, m) and _precisa_rebaixar(conn, y, m):
                pendentes.append((y, m))  # mes ainda revisavel pela CVM: rele
            elif any(c not in lidos for c in cnpjs):
                pendentes.append((y, m))

        # mes recente que sera relido: a marca antiga sai para o ingest reescrever
        for y, m in pendentes:
            if _mes_e_recente(y, m):
                conn.execute(
                    "DELETE FROM dias_lidos WHERE ano = ? AND mes = ? "
                    "AND cnpj_fmt IN ({})".format(",".join("?" * len(cnpjs))),
                    (y, m, *cnpjs),
                )
        conn.commit()
    finally:
        conn.close()

    if not pendentes:
        return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for futuro in [ex.submit(_ingere_mes_diario, cnpjs, y, m) for y, m in pendentes]:
            futuro.result()


def serie_diaria(cnpjs, inicio: date | None = None, fim: date | None = None) -> pd.DataFrame:
    """Serie diaria (cota, PL, patrimonio total, captacao, resgate, cotistas)
    de um ou varios fundos, em formato longo.

    `inicio=None` significa "desde o comeco do historico disponivel", ate o
    teto de MAX_MESES_HISTORICO.

    Esse teto NAO usa a data de inicio da classe no cadastro como atalho: um
    CNPJ_FUNDO_CLASSE pode ter informe diario publicado antes da propria data
    de registro (migracao de classe pela RCVM 175, entre outros motivos), e
    um fundo real teve o historico de "desde o inicio" cortado por confiar
    nessa data. Sem atalho, a primeira consulta de um fundo busca ate o teto
    inteiro (mais lenta), mas o cache torna as seguintes instantaneas e o
    resultado nunca omite historico que existe.
    """
    if isinstance(cnpjs, str):
        cnpjs = [cnpjs]
    cnpjs = tuple(dict.fromkeys(cnpjs))
    if not cnpjs:
        return pd.DataFrame()

    # o mes CORRENTE entra aqui, ao contrario do resto do modulo: a CVM
    # publica o informe do mes aberto dia a dia, e e dele que saem a cota mais
    # recente, o drawdown atual e o valor de mercado do book. Ficar so nos
    # meses fechados atrasaria a carteira do usuario em ate um mes.
    fim_ref = fim or date.today()

    if inicio is None:
        y, m = _mes_n_atras(MAX_MESES_HISTORICO - 1)
        inicio_ref = date(y, m, 1)
    else:
        inicio_ref = inicio

    meses = _meses_entre(inicio_ref, fim_ref)
    if not meses:
        return pd.DataFrame()
    if len(meses) > MAX_MESES_HISTORICO:
        meses = meses[-MAX_MESES_HISTORICO:]

    _garante_series_diarias(cnpjs, meses)

    # o recorte por data no SQL usa o primeiro dia do primeiro mes lido, nao
    # `inicio_ref`, para uma janela de 1 mes ainda trazer o pregao anterior de
    # que o primeiro retorno precisa - quem apara a ponta e o analytics
    piso = date(meses[0][0], meses[0][1], 1)
    conn = _connect()
    try:
        df = pd.read_sql(
            "SELECT cnpj_fmt, data, vl_quota, vl_patrim_liq, vl_total, captc_dia, "
            "resg_dia, nr_cotst FROM cotas_diarias "
            "WHERE cnpj_fmt IN ({}) AND data >= ? AND data <= ? "
            "ORDER BY cnpj_fmt, data".format(",".join("?" * len(cnpjs))),
            conn,
            params=(*cnpjs, piso.isoformat(), fim_ref.isoformat()),
        )
    finally:
        conn.close()

    if df.empty:
        return df
    df["data"] = pd.to_datetime(df["data"])
    return df


def primeira_cota(cnpj_fmt: str) -> str | None:
    """Data da primeira cota ja lida para o fundo, se houver."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT MIN(data) FROM cotas_diarias WHERE cnpj_fmt = ?", (cnpj_fmt,)
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row and row[0] else None



# --------------------------------------------------------------------------- #
# Series mensais (fundo, CDI, indices)
# --------------------------------------------------------------------------- #

def fetch_fund_monthly_returns(cnpj_fmt, n_months):
    """Retorna (months, fund_list): retornos mensais (%) dos ultimos
    n_months meses FECHADOS (menos, se o fundo for mais novo que isso)."""
    month_range = _month_range(n_months)  # n_months + 1 meses, antigo -> novo

    snaps = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(_snapshot_mes, y, m): (y, m) for y, m in month_range}
        for fut in as_completed(futures):
            snaps[futures[fut]] = fut.result()

    def _quota(ym):
        snap = snaps.get(ym)
        if snap is None or cnpj_fmt not in snap.index:
            return None
        return float(snap.loc[cnpj_fmt, "VL_QUOTA"])

    ordered = [(ym, _quota(ym)) for ym in month_range]
    first_valid = next((i for i, (_, q) in enumerate(ordered) if q is not None), None)
    if first_valid is None:
        return [], []
    ordered = ordered[first_valid:]

    months, fund_list = [], []
    for i in range(1, len(ordered)):
        (_, q0), (ym1, q1) = ordered[i - 1], ordered[i]
        if q0 is None or q1 is None:
            continue
        months.append(ym1)
        fund_list.append(round((q1 / q0 - 1) * 100, 4))

    return months, fund_list


def fetch_cdi_monthly(months):
    """Retorna retornos mensais do CDI (%) alinhados com `months`
    (lista de tuplas (ano, mes)), via API SGS do Banco Central."""
    if not months:
        return []
    chave = ("cdi", tuple(months))
    cacheado = _cache_get(chave)
    if cacheado is not None:
        return list(cacheado)

    y0, m0 = months[0]
    y1, m1 = months[-1]
    data_ini = f"01/{m0:02d}/{y0}"
    ultimo_dia = calendar.monthrange(y1, m1)[1]
    data_fim = f"{ultimo_dia:02d}/{m1:02d}/{y1}"

    resp = None
    for tentativa in range(3):
        try:
            resp = sessao_requests().get(
                BCB_CDI_URL,
                params={"formato": "json", "dataInicial": data_ini, "dataFinal": data_fim},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            break
        except requests.RequestException:
            if tentativa == 2:
                raise
            time.sleep(1.5 * (tentativa + 1))
    df = pd.DataFrame(resp.json())
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = df["valor"].astype(float)
    df["ano_mes"] = df["data"].dt.to_period("M")

    cdi_by_month = {}
    for periodo, grupo in df.groupby("ano_mes"):
        fator = np.prod(1 + grupo["valor"].values / 100) - 1
        cdi_by_month[(periodo.year, periodo.month)] = round(fator * 100, 4)

    resultado = [cdi_by_month.get(ym, 0.0) for ym in months]
    _cache_set(chave, resultado)
    return resultado


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}

IBOVESPA_SYMBOL = "%5EBVSP"


def _yahoo_monthly_closes(symbol):
    """Fechamento ajustado de fim de mes (Yahoo Finance) dos ultimos ~6 anos
    para um simbolo (ex.: indice), como dict {(ano, mes): close}. Dict vazio
    se a API falhar - quem consome trata isso como "sem dado" por mes."""
    chave = ("yahoo", symbol)
    cacheado = _cache_get(chave)
    if cacheado is not None:
        return dict(cacheado)

    try:
        resp = sessao_requests().get(
            YAHOO_CHART_URL.format(symbol=symbol),
            params={"range": "6y", "interval": "1mo"},
            timeout=REQUEST_TIMEOUT, headers=YAHOO_HEADERS,
        )
        resp.raise_for_status()
        result = resp.json()["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["adjclose"][0]["adjclose"]
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return {}

    out = {}
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        d = date.fromtimestamp(ts)
        out[(d.year, d.month)] = close
    _cache_set(chave, out)
    return out


def _index_monthly_returns(symbol, months):
    """Retornos mensais (%) de um indice (Yahoo Finance) alinhados com
    `months` (lista de tuplas (ano, mes)); 0.0 nos meses sem dado (API fora
    do ar ou simbolo sem historico ali)."""
    if not months:
        return []
    closes = _yahoo_monthly_closes(symbol)

    y0, m0 = months[0]
    m0 -= 1
    if m0 == 0:
        m0, y0 = 12, y0 - 1
    anterior = (y0, m0)

    retornos = []
    for ym in months:
        if anterior in closes and ym in closes:
            retornos.append(round((closes[ym] / closes[anterior] - 1) * 100, 4))
        else:
            retornos.append(0.0)
        anterior = ym
    return retornos


def fetch_ibovespa_monthly(months):
    """Retornos mensais do Ibovespa (%), alinhados com `months`."""
    return _index_monthly_returns(IBOVESPA_SYMBOL, months)


# --------------------------------------------------------------------------- #
# Atualizacao - usado pelo endpoint POST /api/fundos/atualizar
# --------------------------------------------------------------------------- #

def limpar_cache() -> None:
    """Forca a proxima consulta a rebaixar/reprocessar tudo que pode ter
    mudado (registro de fundos + os MESES_RECENTES meses mais novos),
    ignorando a janela normal de ATUALIZACAO_HORAS."""
    _CACHE.clear()

    conn = _connect()
    try:
        cadastro.invalida(conn)
        carteira.invalida(conn)
        for diff in range(MESES_RECENTES + 1):
            y, m = _mes_n_atras(diff)
            conn.execute("DELETE FROM meses_baixados WHERE ano = ? AND mes = ?", (y, m))
            conn.execute("DELETE FROM cotas_mensais WHERE ano = ? AND mes = ?", (y, m))
        conn.commit()
    finally:
        conn.close()

    for diff in range(MESES_RECENTES + 1):
        y, m = _mes_n_atras(diff)
        path = INFORMES_DIR / f"inf_diario_fi_{y}{m:02d}.zip"
        if path.exists():
            try:
                os.remove(path)
            except OSError:
                pass


def ultima_atualizacao() -> str | None:
    """Data/hora (texto) em que os dados do mes fechado mais recente foram
    baixados pela ultima vez - mostrado na interface para transparencia."""
    y, m = _mes_n_atras(0)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT baixado_em FROM meses_baixados WHERE ano = ? AND mes = ?", (y, m)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    from datetime import datetime
    return datetime.fromtimestamp(row[0]).strftime("%d/%m/%Y %H:%M")
