"""Contratos de entrada e saida da API."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field, field_validator, model_validator


class Posicao(BaseModel):
    ticker: str = Field(..., description="Codigo no yfinance, ex.: PETR4.SA, AAPL")
    peso: float = Field(..., gt=0, description="Peso relativo na carteira")

    @field_validator("ticker")
    @classmethod
    def _limpa(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Ticker vazio.")
        return v


class PedidoVaR(BaseModel):
    posicoes: list[Posicao] = Field(..., min_length=1, max_length=20)
    inicio: date = Field(default_factory=lambda: date.today() - timedelta(days=365 * 3))
    fim: date | None = None
    confianca: float = Field(0.95, gt=0.5, lt=0.9999)
    horizonte: int = Field(1, ge=1, le=60, description="Horizonte do VaR em pregoes")
    janela: int = Field(252, ge=30, le=1500, description="Janela movel do backtest")
    valor_carteira: float = Field(100_000.0, gt=0)

    @model_validator(mode="after")
    def _valida(self) -> "PedidoVaR":
        fim = self.fim or date.today()
        if self.inicio >= fim:
            raise ValueError("A data inicial precisa ser anterior a data final.")
        tickers = [p.ticker for p in self.posicoes]
        if len(set(tickers)) != len(tickers):
            raise ValueError("Ha tickers repetidos na carteira.")
        return self

    def pesos_normalizados(self) -> dict[str, float]:
        total = sum(p.peso for p in self.posicoes)
        return {p.ticker: p.peso / total for p in self.posicoes}
