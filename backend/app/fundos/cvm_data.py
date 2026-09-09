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

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DATA_DIR / "fundos_cache.db"
INFORMES_DIR = DATA_DIR / "cvm_informes"

REGISTRY_URL = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"
INFORME_URL = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{yyyymm}.zip"
BCB_CDI_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"

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
        CREATE TABLE IF NOT EXISTS registro (
            cnpj_fmt           TEXT PRIMARY KEY,
            denominacao_social TEXT NOT NULL,
            atualizado_em      REAL NOT NULL
        )
        """
    )
    return conn


def _read_informe(path, extra_cols=()):
    """Le o informe diario de um mes, tolerando os dois formatos que a CVM
    ja usou: ate nov/2023 a coluna de CNPJ se chamava CNPJ_FUNDO; a partir
    de dez/2023 (Resolucao CVM 175, fundos organizados em "classes") passou
    a ser CNPJ_FUNDO_CLASSE. Sempre devolve a coluna como CNPJ_FUNDO_CLASSE,
    ou None se o arquivo nao existir/nao puder ser lido em nenhum formato."""
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
                    return df
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
# Registro de fundos
# --------------------------------------------------------------------------- #

def _registro_precisa_rebaixar(conn) -> bool:
    row = conn.execute("SELECT MAX(atualizado_em) FROM registro").fetchone()
    if row is None or row[0] is None:
        return True
    return (time.time() - row[0]) >= ATUALIZACAO_HORAS * 3600


def _rebaixa_registro(conn) -> None:
    tem_dados = conn.execute("SELECT 1 FROM registro LIMIT 1").fetchone() is not None
    conteudo = None
    for tentativa in range(3):
        try:
            resp = sessao_requests().get(REGISTRY_URL, timeout=60)
            resp.raise_for_status()
            conteudo = resp.content
            break
        except requests.RequestException:
            if tentativa == 2:
                if not tem_dados:
                    raise
                return  # rede falhou mas ja existe registro (mesmo que velho) - mantem
            time.sleep(1.5 * (tentativa + 1))

    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        with z.open("registro_classe.csv") as f:
            df = pd.read_csv(
                f, sep=";", encoding="latin1",
                usecols=["CNPJ_Classe", "Denominacao_Social", "Situacao"],
            )

    df = df[df["Situacao"] == "Em Funcionamento Normal"].copy()
    df["Denominacao_Social"] = df["Denominacao_Social"].str.strip()
    df["cnpj_fmt"] = df["CNPJ_Classe"].apply(_cnpj_fmt)
    df = df.drop_duplicates(subset="cnpj_fmt")

    agora = time.time()
    conn.execute("DELETE FROM registro")
    conn.executemany(
        "INSERT INTO registro (cnpj_fmt, denominacao_social, atualizado_em) VALUES (?, ?, ?)",
        [(r.cnpj_fmt, r.Denominacao_Social, agora) for r in df.itertuples()],
    )
    conn.commit()


def load_registry() -> pd.DataFrame:
    """Registro de classes de fundos ativas na CVM (nome + CNPJ), restrito
    as que de fato reportaram cota recentemente (tem dados para analisar)."""
    conn = _connect()
    try:
        if _registro_precisa_rebaixar(conn):
            _rebaixa_registro(conn)
        df = pd.read_sql("SELECT cnpj_fmt, denominacao_social FROM registro", conn)
    finally:
        conn.close()

    df = df.rename(columns={"denominacao_social": "Denominacao_Social"})
    cnpjs_ativos = _cnpjs_com_dados_recentes()
    if cnpjs_ativos:
        df = df[df["cnpj_fmt"].isin(cnpjs_ativos)]
    return df.reset_index(drop=True)


def search_funds(query, registry, limit=40):
    """Filtra o registro pelo nome do fundo (case-insensitive)."""
    q = query.strip().upper()
    if not q:
        return registry.head(0)
    mask = registry["Denominacao_Social"].str.upper().str.contains(q, regex=False)
    return registry[mask].head(limit)


def fund_by_cnpj(cnpj_fmt: str, registry: pd.DataFrame) -> str | None:
    linha = registry[registry["cnpj_fmt"] == cnpj_fmt]
    return None if linha.empty else str(linha.iloc[0]["Denominacao_Social"])


# --------------------------------------------------------------------------- #
# Ranking Top N
# --------------------------------------------------------------------------- #

def _ranking_a_partir_de(
    quotas: pd.DataFrame,
    snap_final: pd.DataFrame,
    registry: pd.DataFrame,
    min_cotistas: int,
    salto_mensal_max: float,
    top_n: int,
) -> pd.DataFrame:
    """Nucleo puro do ranking (sem rede/banco) - isolado para ser testavel
    com DataFrames sinteticos."""
    primeiro, ultimo = quotas.columns[0], quotas.columns[-1]
    base = quotas[[primeiro, ultimo]].dropna()
    if base.empty:
        return pd.DataFrame()
    retorno_total = (base[ultimo] / base[primeiro] - 1) * 100

    # saltos mensais acima do limite quase sempre sao desdobramento/
    # grupamento de cotas ou erro de reporte da CVM, nao desempenho real
    pico_mensal = quotas.loc[retorno_total.index].pct_change(axis=1).abs().max(axis=1) * 100
    sem_saltos = pico_mensal <= salto_mensal_max

    resultado = pd.DataFrame({
        "cnpj_fmt": retorno_total.index,
        "retorno_%": retorno_total.values,
        "patrimonio_mi": (snap_final["VL_PATRIM_LIQ"].reindex(retorno_total.index) / 1e6).values,
        "cotistas": snap_final["NR_COTST"].reindex(retorno_total.index).values,
    })
    resultado = resultado[sem_saltos.values & (resultado["cotistas"] >= min_cotistas)]

    resultado = resultado.merge(
        registry[["cnpj_fmt", "Denominacao_Social"]], on="cnpj_fmt", how="inner"
    )
    return resultado.sort_values("retorno_%", ascending=False).head(top_n).reset_index(drop=True)


def top_funds_by_return(n_years, top_n=10, min_cotistas=100, salto_mensal_max=80.0):
    """Os top_n fundos com maior retorno acumulado nos ultimos n_years anos
    (janela fechada), entre os fundos com pelo menos min_cotistas cotistas
    (evita fundos exclusivos/institucionais distorcendo o ranking) e sem
    nenhum salto mensal acima de salto_mensal_max%."""
    chave = ("top10", n_years, top_n, min_cotistas, salto_mensal_max)
    cacheado = _cache_get(chave)
    if cacheado is not None:
        return cacheado.copy()

    month_range = _month_range(n_years * 12)  # n_years*12 + 1 meses, antigo -> novo

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
        quotas, snaps[meses_validos[-1]], load_registry(), min_cotistas, salto_mensal_max, top_n
    )
    _cache_set(chave, resultado)
    return resultado.copy()


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
        conn.execute("DELETE FROM registro")
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
