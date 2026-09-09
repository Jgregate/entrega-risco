"""Serie historica da Selic — API SGS do Banco Central.

O yfinance nao publica a Selic, entao a taxa livre de risco vem da fonte
oficial: serie 11 do SGS (taxa Selic diaria, em % ao dia).

    https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados?formato=json

E publica e nao exige chave. Se a API estiver fora do ar ou bloqueada por
rede corporativa, `serie_selic` levanta ErroSelic e a camada de cima cai
para uma taxa anual fixa informada pelo usuario — a aplicacao nunca deixa
de responder por causa disso.
"""

from __future__ import annotations

import time
from datetime import date

import pandas as pd

from ._certs import sessao_requests

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
SERIE_SELIC_DIARIA = 11
DIAS_UTEIS_ANO = 252

_CACHE: dict[tuple, tuple[float, pd.Series]] = {}
_TTL_SEGUNDOS = 60 * 60 * 6


class ErroSelic(Exception):
    """Falha ao obter a serie da Selic."""


def serie_selic(inicio: date, fim: date, usar_cache: bool = True) -> pd.Series:
    """Selic diaria como fracao (0,0004 = 0,04% ao dia), indexada por data."""
    chave = (inicio.isoformat(), fim.isoformat())
    agora = time.time()
    if usar_cache and chave in _CACHE:
        carimbo, cacheada = _CACHE[chave]
        if agora - carimbo < _TTL_SEGUNDOS:
            return cacheada.copy()

    parametros = {
        "formato": "json",
        "dataInicial": inicio.strftime("%d/%m/%Y"),
        "dataFinal": fim.strftime("%d/%m/%Y"),
    }
    try:
        resposta = sessao_requests().get(
            URL_SGS.format(serie=SERIE_SELIC_DIARIA),
            params=parametros,
            timeout=20,
            headers={"Accept": "application/json"},
        )
        resposta.raise_for_status()
        dados = resposta.json()
    except Exception as exc:  # pragma: no cover - depende de rede
        raise ErroSelic(f"Nao foi possivel consultar o SGS do Banco Central: {exc}") from exc

    if not dados:
        raise ErroSelic("O SGS nao retornou nenhum ponto da Selic para o periodo.")

    quadro = pd.DataFrame(dados)
    quadro["data"] = pd.to_datetime(quadro["data"], format="%d/%m/%Y")
    quadro["valor"] = pd.to_numeric(quadro["valor"].astype(str).str.replace(",", "."))
    serie = quadro.set_index("data")["valor"] / 100.0
    serie.name = "selic"

    _CACHE[chave] = (agora, serie.copy())
    return serie


def taxa_anual_para_diaria(taxa_anual: float) -> float:
    """Converte % ao ano efetivo para taxa diaria composta (252 dias uteis)."""
    return (1.0 + taxa_anual) ** (1.0 / DIAS_UTEIS_ANO) - 1.0


def alinha_com_carteira(
    selic: pd.Series, indice_carteira: pd.DatetimeIndex
) -> pd.Series:
    """Encaixa a Selic no calendario da carteira.

    Feriado de bolsa que nao e feriado bancario (e vice-versa) faz as duas
    series divergirem em alguns dias; o reindex com forward fill mantem a
    ultima taxa conhecida em vez de furar a serie.
    """
    return selic.reindex(indice_carteira).ffill().bfill()
