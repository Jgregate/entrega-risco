"""API do modulo de risco — Celula de Risco, Inteli Finance.

Tres VaRs (empirico, parametrico, EWMA) sobre a mesma carteira, backtest de
violacoes para cada um e a relacao risco-retorno contra a Selic.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import risco_retorno as rr
from .analise import analisar
from .data import ErroDeDados, baixar_precos, buscar_nome
from .fundos.router import router as fundos_router
from .schemas import PedidoVaR
from .selic import ErroSelic, alinha_com_carteira, serie_selic, taxa_anual_para_diaria
from .var_core import retorno_carteira, retornos_simples
from .var_empirico import calcular

SELIC_PADRAO_ANUAL = 0.15  # usada so se o BCB falhar e o pedido nao trouxer taxa

app = FastAPI(
    title="Risco | VaR e risco-retorno",
    description=(
        "VaR empirico, parametrico e EWMA sobre precos do yfinance, com "
        "backtest de violacoes e indices de risco-retorno contra a Selic "
        "(serie 11 do BCB). Modulo da celula de risco do Inteli Finance."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fundos_router)


@app.get("/api/health", tags=["infra"])
def health() -> dict:
    return {"status": "ok", "modulo": "risco", "data": date.today().isoformat()}


@app.get("/api/ativo", tags=["dados"])
def ativo(ticker: str = Query(..., min_length=1, max_length=20)) -> dict:
    """Valida um ticker no yfinance e devolve o nome do ativo."""
    ticker = ticker.strip().upper()
    hoje = date.today()
    try:
        precos = baixar_precos([ticker], inicio=str(hoje.replace(year=hoje.year - 1)))
    except ErroDeDados as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "ticker": ticker,
        "nome": buscar_nome(ticker),
        "ultimo_preco": round(float(precos[ticker].iloc[-1]), 4),
        "ultima_data": precos.index[-1].strftime("%Y-%m-%d"),
    }


def _carrega_precos(pedido: PedidoVaR) -> pd.DataFrame:
    pesos = pedido.pesos_normalizados()
    try:
        precos = baixar_precos(
            tickers=list(pesos.keys()),
            inicio=pedido.inicio.isoformat(),
            fim=pedido.fim.isoformat() if pedido.fim else None,
        )
    except ErroDeDados as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if len(precos) <= pedido.janela + 10:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Ha {len(precos)} pregoes no periodo, insuficiente para uma janela "
                f"de {pedido.janela} dias. Amplie o periodo ou reduza a janela."
            ),
        )
    return precos


def _bloco_risco_retorno(pedido: PedidoVaR, precos: pd.DataFrame) -> dict:
    """Sharpe/Sortino contra a Selic, com queda para taxa fixa se o BCB falhar."""
    ret_carteira = retorno_carteira(retornos_simples(precos), pedido.pesos_normalizados())
    inicio = ret_carteira.index[0].date()
    fim = ret_carteira.index[-1].date()

    fonte = "bcb-sgs-11"
    observacao = "Selic diária, série 11 do Banco Central."
    detalhe = None
    try:
        selic = alinha_com_carteira(serie_selic(inicio, fim), ret_carteira.index)
    except ErroSelic as exc:
        taxa = pedido.selic_anual or SELIC_PADRAO_ANUAL
        selic = pd.Series(
            taxa_anual_para_diaria(taxa), index=ret_carteira.index, name="selic"
        )
        fonte = "taxa-fixa"
        observacao = f"BCB indisponível — taxa fixa de {taxa * 100:.2f}% a.a."
        detalhe = str(exc)

    saida = rr.calcular(ret_carteira, selic, janela_rolling=pedido.janela)
    saida["fonte_taxa"] = fonte
    saida["observacao_taxa"] = observacao
    saida["detalhe_taxa"] = detalhe
    return saida


@app.post("/api/analise", tags=["analise"])
def analise(pedido: PedidoVaR) -> dict:
    """Payload completo: os tres VaRs, o book e a relacao risco-retorno."""
    precos = _carrega_precos(pedido)
    try:
        return analisar(
            precos=precos,
            pesos=pedido.pesos_normalizados(),
            confianca=pedido.confianca,
            horizonte=pedido.horizonte,
            janela=pedido.janela,
            valor_carteira=pedido.valor_carteira,
            risco_retorno=_bloco_risco_retorno(pedido, precos),
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Falha no calculo: {exc}") from exc


@app.post("/api/var/empirico", tags=["var"])
def var_empirico_endpoint(pedido: PedidoVaR) -> dict:
    """Somente o VaR empirico — mantido para quem ja consome este contrato."""
    precos = _carrega_precos(pedido)
    try:
        saida = calcular(
            precos=precos,
            pesos=pedido.pesos_normalizados(),
            confianca=pedido.confianca,
            horizonte=pedido.horizonte,
            janela=pedido.janela,
            valor_carteira=pedido.valor_carteira,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Falha no calculo: {exc}") from exc
    saida["metodo"] = "empirico"
    return saida
