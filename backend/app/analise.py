"""Orquestracao: monta o payload unico que alimenta as tres abas do front."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import var_empirico, var_ewma, var_parametrico
from .var_core import (
    agrega_horizonte,
    estatisticas,
    histograma,
    retorno_carteira,
    retornos_simples,
    serializa_backtest,
)

METODOS = (var_empirico, var_parametrico, var_ewma)


def _bloco_metodo(
    modulo,
    ret_carteira: pd.Series,
    confianca: float,
    horizonte: int,
    janela: int,
    valor_carteira: float,
) -> dict:
    p = modulo.pontual(ret_carteira, confianca, horizonte)
    bt = modulo.rolling(ret_carteira, confianca, janela)
    var, es = p["var"], p["es"]
    return {
        "nome": modulo.NOME,
        "rotulo": modulo.ROTULO,
        "descricao": modulo.DESCRICAO,
        "var_percentual": round(var, 6) if np.isfinite(var) else None,
        "var_monetario": round(var * valor_carteira, 2) if np.isfinite(var) else None,
        "es_percentual": round(es, 6) if np.isfinite(es) else None,
        "es_monetario": round(es * valor_carteira, 2) if np.isfinite(es) else None,
        "backtest": serializa_backtest(bt, confianca),
    }


def _book(
    precos: pd.DataFrame, pesos: dict[str, float], valor_carteira: float
) -> list[dict]:
    """Posicoes com o valor nominal alocado em cada ativo."""
    linhas = []
    for ticker, peso in pesos.items():
        serie = precos[ticker]
        preco_inicial = float(serie.iloc[0])
        preco_final = float(serie.iloc[-1])
        valor_nominal = peso * valor_carteira
        linhas.append(
            {
                "ticker": ticker,
                "peso": round(peso, 6),
                "valor_nominal": round(valor_nominal, 2),
                "preco_inicial": round(preco_inicial, 4),
                "preco_final": round(preco_final, 4),
                "quantidade": round(valor_nominal / preco_final, 2) if preco_final else None,
                "retorno_periodo": round(preco_final / preco_inicial - 1.0, 6),
            }
        )
    return linhas


def analisar(
    precos: pd.DataFrame,
    pesos: dict[str, float],
    confianca: float,
    horizonte: int,
    janela: int,
    valor_carteira: float,
    risco_retorno: dict | None = None,
) -> dict:
    ret_ativos = retornos_simples(precos)
    ret_carteira = retorno_carteira(ret_ativos, pesos)
    ret_horizonte = agrega_horizonte(ret_carteira, horizonte)

    metodos = {
        m.NOME: _bloco_metodo(m, ret_carteira, confianca, horizonte, janela, valor_carteira)
        for m in METODOS
    }

    serie_valor = (1.0 + ret_carteira).cumprod() * valor_carteira

    return {
        "parametros": {
            "confianca": confianca,
            "horizonte_dias": horizonte,
            "janela_backtest": janela,
            "valor_carteira": valor_carteira,
            "pesos": {k: round(v, 6) for k, v in pesos.items()},
            "inicio": precos.index[0].strftime("%Y-%m-%d"),
            "fim": precos.index[-1].strftime("%Y-%m-%d"),
            "pregoes": int(len(precos)),
        },
        "book": _book(precos, pesos, valor_carteira),
        "metodos": metodos,
        "ordem_metodos": [m.NOME for m in METODOS],
        "estatisticas": estatisticas(ret_horizonte),
        "distribuicao": histograma(ret_horizonte),
        "pior_retorno": round(float(ret_horizonte.min()), 6),
        "evolucao": [
            {"data": i.strftime("%Y-%m-%d"), "valor": round(float(v), 2)}
            for i, v in serie_valor.items()
        ],
        "risco_retorno": risco_retorno,
    }
