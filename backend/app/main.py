"""API do modulo de VaR Empirico - Celula de Risco, Inteli Finance."""

from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .data import ErroDeDados, baixar_precos, buscar_nome
from .schemas import PedidoVaR
from .var_empirico import calcular

app = FastAPI(
    title="Risco | VaR Empirico",
    description=(
        "Value at Risk por simulacao historica sobre precos do yfinance. "
        "Modulo da celula de risco do Inteli Finance."
    ),
    version="1.0.0",
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


@app.get("/api/health", tags=["infra"])
def health() -> dict:
    return {"status": "ok", "modulo": "var-empirico", "data": date.today().isoformat()}


@app.get("/api/ativo", tags=["dados"])
def ativo(ticker: str = Query(..., min_length=1, max_length=20)) -> dict:
    """Valida um ticker no yfinance e devolve o nome do ativo."""
    ticker = ticker.strip().upper()
    try:
        precos = baixar_precos([ticker], inicio=str(date.today().replace(year=date.today().year - 1)))
    except ErroDeDados as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "ticker": ticker,
        "nome": buscar_nome(ticker),
        "ultimo_preco": round(float(precos[ticker].iloc[-1]), 4),
        "ultima_data": precos.index[-1].strftime("%Y-%m-%d"),
    }


@app.post("/api/var/empirico", tags=["var"])
def var_empirico_endpoint(pedido: PedidoVaR) -> dict:
    """Calcula o VaR empirico (simulacao historica) da carteira."""
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

    try:
        saida = calcular(
            precos=precos,
            pesos=pesos,
            confianca=pedido.confianca,
            horizonte=pedido.horizonte,
            janela=pedido.janela,
            valor_carteira=pedido.valor_carteira,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Falha no calculo: {exc}") from exc

    saida["metodo"] = "empirico"
    return saida
