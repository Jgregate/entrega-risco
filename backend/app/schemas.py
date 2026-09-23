"""Contratos de entrada e saida da API."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field, field_validator, model_validator


class Posicao(BaseModel):
    ticker: str = Field(..., description="Codigo no yfinance, ex.: PETR4.SA, AAPL")
    peso: float = Field(..., gt=0, description="Peso relativo na carteira")
    data_compra: date | None = Field(
        None,
        description=(
            "Quando a posicao foi comprada. Alimenta a rastreabilidade "
            "('comprei ha X dias, quanto valorizou'). Omitida, a posicao e "
            "tratada como comprada na primeira data da serie."
        ),
    )
    preco_compra: float | None = Field(
        None,
        gt=0,
        description=(
            "Preco pago por acao. Omitido, cai para o fechamento ajustado da "
            "data de compra e a linha sai marcada como estimada."
        ),
    )

    @field_validator("ticker")
    @classmethod
    def _limpa(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Ticker vazio.")
        return v

    @model_validator(mode="after")
    def _valida_compra(self) -> "Posicao":
        if self.data_compra and self.data_compra > date.today():
            raise ValueError("A data de compra nao pode estar no futuro.")
        return self


class PedidoVaR(BaseModel):
    posicoes: list[Posicao] = Field(..., min_length=1, max_length=20)
    inicio: date = Field(default_factory=lambda: date.today() - timedelta(days=365 * 3))
    fim: date | None = None
    confianca: float = Field(0.95, gt=0.5, lt=0.9999)
    horizonte: int = Field(1, ge=1, le=60, description="Horizonte do VaR em pregoes")
    janela: int = Field(252, ge=30, le=1500, description="Janela movel do backtest")
    horizonte_projecao: int = Field(
        21,
        ge=1,
        le=252,
        description=(
            "Pregoes a frente na projecao da aba de rastreabilidade. 21 = um "
            "mes de pregoes. Independente de `horizonte`, que e do VaR."
        ),
    )
    valor_carteira: float = Field(100_000.0, gt=0)
    selic_anual: float | None = Field(
        None,
        gt=0,
        lt=1,
        description=(
            "Taxa livre de risco anual usada apenas se a serie do BCB nao "
            "estiver disponivel (ex.: 0.15 para 15% a.a.)."
        ),
    )

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


class PosicaoRendaFixa(BaseModel):
    """Uma posicao em titulo publico.

    Ao contrario do book de acoes, que e dirigido por peso, aqui a posicao e
    dirigida por quantidade: o valor sai de `quantidade x PU`, nao de uma
    fatia do valor da carteira.
    """

    titulo_id: str = Field(
        ...,
        description="Identificador vindo de GET /api/titulos-publicos/disponiveis",
    )
    quantidade: float = Field(
        ..., gt=0, description="Fracionario permitido, ex.: 0.5 de um titulo"
    )
    data_aquisicao: date | None = Field(
        None, description="Se omitida, a posicao e tratada como adquirida na data base"
    )
    pu_aquisicao: float | None = Field(
        None,
        gt=0,
        description="Se omitido, cai para o PU de venda da data de aquisicao",
    )

    @field_validator("titulo_id")
    @classmethod
    def _limpa(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Identificador do titulo vazio.")
        return v

    @model_validator(mode="after")
    def _valida(self) -> "PosicaoRendaFixa":
        if self.data_aquisicao and self.data_aquisicao > date.today():
            raise ValueError("A data de aquisicao nao pode estar no futuro.")
        return self


class PedidoRendaFixa(BaseModel):
    posicoes: list[PosicaoRendaFixa] = Field(..., min_length=1, max_length=20)

    @model_validator(mode="after")
    def _valida(self) -> "PedidoRendaFixa":
        ids = [p.titulo_id for p in self.posicoes]
        if len(set(ids)) != len(ids):
            raise ValueError(
                "Ha titulos repetidos no book. Consolide a posicao em uma linha só."
            )
        return self


class ParametrosRisco(BaseModel):
    """Os mesmos parametros do book de acoes, para a comparacao ser honesta."""

    confianca: float = Field(0.95, gt=0.5, lt=0.9999)
    horizonte: int = Field(1, ge=1, le=60, description="Horizonte do VaR em pregoes")
    janela: int = Field(252, ge=30, le=1500, description="Janela movel do backtest")
    horizonte_projecao: int = Field(
        21,
        ge=1,
        le=252,
        description="Pregoes a frente na projecao da aba de rastreabilidade.",
    )
    inicio: date | None = Field(None, description="Se omitido, usa o historico inteiro")
    fim: date | None = None
    selic_anual: float | None = Field(None, gt=0, lt=1)

    @model_validator(mode="after")
    def _valida_periodo(self) -> "ParametrosRisco":
        if self.inicio and self.fim and self.inicio >= self.fim:
            raise ValueError("A data inicial precisa ser anterior a data final.")
        return self


class PedidoAnaliseRendaFixa(PedidoRendaFixa, ParametrosRisco):
    """Book de renda fixa mais os parametros de risco."""


class PedidoConsolidado(ParametrosRisco):
    """Os dois books na mesma analise.

    O valor das acoes vem de `valor_carteira`, como hoje; o da renda fixa sai
    da marcacao a mercado. A ponderacao entre as duas pernas e por valor.
    """

    acoes: list[Posicao] = Field(..., min_length=1, max_length=20)
    renda_fixa: list[PosicaoRendaFixa] = Field(..., min_length=1, max_length=20)
    valor_carteira: float = Field(
        100_000.0, gt=0, description="Valor alocado na perna de acoes"
    )

    @model_validator(mode="after")
    def _valida_books(self) -> "PedidoConsolidado":
        tickers = [p.ticker for p in self.acoes]
        if len(set(tickers)) != len(tickers):
            raise ValueError("Ha tickers repetidos na carteira de acoes.")
        ids = [p.titulo_id for p in self.renda_fixa]
        if len(set(ids)) != len(ids):
            raise ValueError("Ha titulos repetidos no book de renda fixa.")
        return self

    def pesos_acoes(self) -> dict[str, float]:
        total = sum(p.peso for p in self.acoes)
        return {p.ticker: p.peso / total for p in self.acoes}
