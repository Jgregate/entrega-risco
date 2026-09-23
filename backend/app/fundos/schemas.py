"""Entrada validada dos endpoints do book.

Tudo aqui e opcional de proposito, menos o CNPJ. O usuario monta o book com o
que tem em maos: as vezes a quantidade de cotas do extrato, as vezes so
quanto colocou e quando. O que nao vier e o que a tela vai mostrar como
lacuna - ver `book.resolve_posicao` para a ordem de precisao entre os
caminhos, e `cadastro.py` para por que taxa e liquidez vem do usuario.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from .cadastro import cnpj_formatado


class PosicaoBook(BaseModel):
    cnpj: str = Field(..., min_length=14, max_length=20)
    quantidade_cotas: float | None = Field(None, gt=0)
    valor_investido: float | None = Field(None, gt=0)
    preco_medio: float | None = Field(None, gt=0)
    data_entrada: date | None = None

    # informados pelo usuario: a CVM nao publica nenhum dos tres nos dados
    # abertos pos-RCVM 175
    liquidez_dias: int | None = Field(None, ge=0, le=3650)
    taxa_administracao: float | None = Field(None, ge=0, le=100)
    taxa_performance: float | None = Field(None, ge=0, le=100)

    @field_validator("cnpj")
    @classmethod
    def _normaliza_cnpj(cls, v: str) -> str:
        return cnpj_formatado(v)


class PedidoBook(BaseModel):
    posicoes: list[PosicaoBook] = Field(..., min_length=1, max_length=60)
    periodo: str = "12m"
    benchmarks: list[str] = Field(default_factory=lambda: ["cdi"], max_length=6)
