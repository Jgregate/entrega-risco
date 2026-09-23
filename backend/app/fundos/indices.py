"""Benchmarks diarios para comparar com fundos e com o book.

Tres fontes, cada uma com uma natureza diferente, e e a natureza que decide
como a serie e alinhada ao calendario do fundo:

  SGS/BCB (CDI, Selic)  taxa diaria em % ao dia -> ja e retorno, compoe direto
  SGS/BCB (IPCA)        indice MENSAL           -> distribuido nos dias uteis
  Yahoo (Ibovespa, ...) preco de fechamento     -> retorno = variacao do preco

O alinhamento e sempre feito contra o calendario do FUNDO, nunca o contrario:
o que interessa e "quanto o benchmark rendeu nos mesmos dias em que o fundo
rendeu". Dia em que o fundo reportou e o benchmark nao (feriado so de bolsa,
por exemplo) entra como retorno zero, nao como buraco - assim as duas curvas
acumuladas tem exatamente o mesmo numero de pontos e podem ser comparadas
ponto a ponto no grafico.
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests

from .._certs import sessao_requests

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}

REQUEST_TIMEOUT = 30
TTL_SEGUNDOS = 6 * 3600

SERIE_SELIC = 11
SERIE_CDI = 12
SERIE_IPCA = 433

# Catalogo exposto na interface. `fonte` define como a serie e obtida e
# `tipo` como ela vira retorno diario.
BENCHMARKS = {
    "cdi": {"rotulo": "CDI", "fonte": "sgs", "codigo": SERIE_CDI, "tipo": "taxa"},
    "ibovespa": {"rotulo": "Ibovespa", "fonte": "yahoo", "codigo": "^BVSP", "tipo": "preco"},
    "ipca": {"rotulo": "IPCA", "fonte": "sgs", "codigo": SERIE_IPCA, "tipo": "mensal"},
    "selic": {"rotulo": "Selic", "fonte": "sgs", "codigo": SERIE_SELIC, "tipo": "taxa"},
    "sp500": {"rotulo": "S&P 500", "fonte": "yahoo", "codigo": "^GSPC", "tipo": "preco"},
    "dolar": {"rotulo": "Dólar", "fonte": "yahoo", "codigo": "BRL=X", "tipo": "preco"},
}

# Benchmark "oficial" de um fundo vem do campo Indicador_Desempenho do
# cadastro, que e texto livre padronizado pela CVM. Este mapa traduz os
# rotulos mais frequentes para uma das series que sabemos buscar; o que nao
# estiver aqui simplesmente nao ganha comparacao automatica (e a interface
# mostra o texto da CVM sem grafico, em vez de comparar com o benchmark errado).
BENCHMARK_DO_CADASTRO = {
    "DI DE UM DIA": "cdi",
    "TAXA SELIC": "selic",
    "IBOVESPA": "ibovespa",
    "ÍNDICE DE PREÇOS AO CONSUMIDOR AMPLO (IPCA/IBGE)": "ipca",
    "IBRX": "ibovespa",
    "IBRX-50": "ibovespa",
}

_CACHE: dict[tuple, tuple[float, pd.Series]] = {}


def _cache_get(chave):
    item = _CACHE.get(chave)
    if item is None:
        return None
    carimbo, valor = item
    if time.time() - carimbo >= TTL_SEGUNDOS:
        return None
    return valor.copy()


def _cache_set(chave, valor: pd.Series) -> None:
    _CACHE[chave] = (time.time(), valor.copy())


# --------------------------------------------------------------------------- #
# Fontes
# --------------------------------------------------------------------------- #

def _sgs(codigo: int, inicio: date, fim: date) -> pd.Series:
    """Serie do SGS/BCB como fracao (0,0004 = 0,04%), indexada por data."""
    chave = ("sgs", codigo, inicio.isoformat(), fim.isoformat())
    cacheada = _cache_get(chave)
    if cacheada is not None:
        return cacheada

    resp = sessao_requests().get(
        URL_SGS.format(serie=codigo),
        params={
            "formato": "json",
            "dataInicial": inicio.strftime("%d/%m/%Y"),
            "dataFinal": fim.strftime("%d/%m/%Y"),
        },
        timeout=REQUEST_TIMEOUT,
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    dados = resp.json()
    if not dados:
        return pd.Series(dtype=float)

    df = pd.DataFrame(dados)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"].astype(str).str.replace(",", "."))
    serie = df.set_index("data")["valor"] / 100.0
    _cache_set(chave, serie)
    return serie


def _yahoo(symbol: str, inicio: date, fim: date) -> pd.Series:
    """Fechamento ajustado diario. Devolve serie vazia se a API falhar - o
    benchmark some do grafico, mas a analise do fundo continua de pe."""
    chave = ("yahoo", symbol, inicio.isoformat(), fim.isoformat())
    cacheada = _cache_get(chave)
    if cacheada is not None:
        return cacheada

    try:
        resp = sessao_requests().get(
            YAHOO_CHART_URL.format(symbol=symbol),
            params={
                "period1": int(pd.Timestamp(inicio).timestamp()),
                # o Yahoo trata period2 como exclusivo em alguns intervalos
                "period2": int(pd.Timestamp(fim + timedelta(days=2)).timestamp()),
                "interval": "1d",
            },
            timeout=REQUEST_TIMEOUT,
            headers=YAHOO_HEADERS,
        )
        resp.raise_for_status()
        resultado = resp.json()["chart"]["result"][0]
        carimbos = resultado["timestamp"]
        fechamentos = resultado["indicators"]["adjclose"][0]["adjclose"]
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return pd.Series(dtype=float)

    serie = pd.Series(
        [f for f in fechamentos if f is not None],
        index=pd.to_datetime(
            [pd.Timestamp(t, unit="s").normalize() for t, f in zip(carimbos, fechamentos)
             if f is not None]
        ),
        dtype=float,
    )
    serie = serie[~serie.index.duplicated(keep="last")].sort_index()
    _cache_set(chave, serie)
    return serie


# --------------------------------------------------------------------------- #
# Alinhamento
# --------------------------------------------------------------------------- #

def _mensal_para_diario(mensal: pd.Series, datas: pd.DatetimeIndex) -> pd.Series:
    """Espalha um indice mensal (IPCA) pelos dias do calendario do fundo.

    O mes inteiro e distribuido geometricamente pelos pregoes daquele mes, de
    forma que o acumulado do mes bata exatamente com o divulgado. Nao e uma
    previsao do dia a dia da inflacao - e a unica forma honesta de por uma
    serie mensal no mesmo eixo de uma diaria sem inventar oscilacao.
    """
    if mensal.empty or len(datas) == 0:
        return pd.Series(0.0, index=datas)

    periodos = datas.to_period("M")
    contagem = pd.Series(1, index=datas).groupby(periodos).transform("size")
    por_mes = {p.to_period("M"): v for p, v in mensal.items()}
    mensal_alinhado = pd.Series(
        [por_mes.get(p, 0.0) for p in periodos], index=datas, dtype=float
    )
    return (1.0 + mensal_alinhado) ** (1.0 / contagem.to_numpy()) - 1.0


def retornos_benchmark(chave: str, datas: pd.DatetimeIndex) -> pd.Series:
    """Retornos diarios de um benchmark alinhados ao calendario `datas`.

    Sempre devolve uma serie do mesmo tamanho de `datas`, com 0.0 no primeiro
    ponto (nao ha retorno no dia inicial) e em qualquer dia sem dado.
    """
    if chave not in BENCHMARKS or len(datas) == 0:
        return pd.Series(dtype=float)

    spec = BENCHMARKS[chave]
    datas = pd.DatetimeIndex(datas)
    inicio = datas[0].date()
    fim = datas[-1].date()

    try:
        if spec["fonte"] == "sgs":
            # uma folga para tras garante o ponto anterior ao primeiro pregao
            bruta = _sgs(spec["codigo"], inicio - timedelta(days=45), fim)
        else:
            bruta = _yahoo(spec["codigo"], inicio - timedelta(days=15), fim)
    except requests.RequestException:
        return pd.Series(dtype=float)

    if bruta.empty:
        return pd.Series(dtype=float)

    if spec["tipo"] == "taxa":
        # taxa ao dia: dia sem publicacao (feriado bancario) rendeu zero
        serie = bruta.reindex(datas).fillna(0.0)
    elif spec["tipo"] == "mensal":
        serie = _mensal_para_diario(bruta, datas)
    else:
        # preco: leva o ultimo fechamento conhecido para o pregao do fundo
        precos = bruta.reindex(bruta.index.union(datas)).ffill().reindex(datas)
        serie = precos.pct_change().fillna(0.0)

    serie.iloc[0] = 0.0
    return serie.replace([np.inf, -np.inf], 0.0).astype(float)


def rotulo(chave: str) -> str:
    return BENCHMARKS.get(chave, {}).get("rotulo", chave)


def chave_do_cadastro(indicador: str | None) -> str | None:
    """Traduz o Indicador_Desempenho da CVM para uma chave de benchmark."""
    if not indicador:
        return None
    return BENCHMARK_DO_CADASTRO.get(indicador.strip().upper())


def catalogo() -> list[dict]:
    return [{"chave": k, "rotulo": v["rotulo"]} for k, v in BENCHMARKS.items()]
