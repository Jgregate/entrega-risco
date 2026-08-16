"""Camada de dados: tudo vem do yfinance."""

from __future__ import annotations

import time
from typing import Sequence

import pandas as pd
import yfinance as yf

# cache simples em memoria: (chave) -> (timestamp, DataFrame)
_CACHE: dict[tuple, tuple[float, pd.DataFrame]] = {}
_TTL_SEGUNDOS = 60 * 15


class ErroDeDados(Exception):
    """Falha ao obter ou validar precos."""


def _normaliza_fechamento(bruto: pd.DataFrame, tickers: Sequence[str]) -> pd.DataFrame:
    """Extrai o Close ajustado como DataFrame com uma coluna por ticker."""
    if bruto is None or len(bruto) == 0:
        raise ErroDeDados("O yfinance nao retornou nenhuma linha para os tickers informados.")

    if isinstance(bruto.columns, pd.MultiIndex):
        nivel0 = bruto.columns.get_level_values(0)
        campo = "Close" if "Close" in nivel0 else "Adj Close"
        fechamento = bruto[campo].copy()
    else:
        campo = "Close" if "Close" in bruto.columns else "Adj Close"
        fechamento = bruto[[campo]].copy()
        fechamento.columns = [tickers[0]]

    fechamento = fechamento.reindex(columns=list(tickers))
    fechamento.index = pd.to_datetime(fechamento.index).tz_localize(None)
    return fechamento


def baixar_precos(
    tickers: Sequence[str],
    inicio: str,
    fim: str | None = None,
    usar_cache: bool = True,
) -> pd.DataFrame:
    """Baixa precos de fechamento ajustado do yfinance.

    Retorna um DataFrame indexado por data, uma coluna por ticker,
    apenas com as datas em que todos os ativos negociaram.
    """
    tickers = [t.strip().upper() for t in tickers if t and t.strip()]
    if not tickers:
        raise ErroDeDados("Informe ao menos um ticker.")

    chave = (tuple(tickers), inicio, fim)
    agora = time.time()
    if usar_cache and chave in _CACHE:
        carimbo, cacheado = _CACHE[chave]
        if agora - carimbo < _TTL_SEGUNDOS:
            return cacheado.copy()

    try:
        bruto = yf.download(
            tickers=list(tickers),
            start=inicio,
            end=fim,
            auto_adjust=True,
            progress=False,
            group_by="column",
            threads=True,
        )
    except Exception as exc:  # pragma: no cover - depende de rede
        raise ErroDeDados(f"Falha na comunicacao com o yfinance: {exc}") from exc

    fechamento = _normaliza_fechamento(bruto, tickers)

    vazios = [c for c in fechamento.columns if fechamento[c].dropna().empty]
    if vazios:
        raise ErroDeDados(
            "Sem dados para: " + ", ".join(vazios) + ". Confira os tickers "
            "(acoes brasileiras usam sufixo .SA, ex.: PETR4.SA)."
        )

    fechamento = fechamento.dropna(how="any")
    if len(fechamento) < 30:
        raise ErroDeDados(
            f"Serie muito curta ({len(fechamento)} pregoes em comum). "
            "Amplie o periodo ou reduza a quantidade de ativos."
        )

    _CACHE[chave] = (agora, fechamento.copy())
    return fechamento


def buscar_nome(ticker: str) -> str | None:
    """Nome amigavel do ativo, quando o yfinance devolver."""
    try:
        info = yf.Ticker(ticker).get_info()
        return info.get("longName") or info.get("shortName")
    except Exception:  # pragma: no cover - depende de rede
        return None
