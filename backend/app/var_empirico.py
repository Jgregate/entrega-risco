"""VaR Empirico (simulacao historica).

Nenhuma hipotese sobre a forma da distribuicao: o VaR e o quantil da amostra
de retornos observados da carteira. Paga o preco de so enxergar o que ja
aconteceu, mas nao subestima cauda gorda como a normal faz.

Convencao de sinal: VaR e reportado como PERDA POSITIVA.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .var_core import (  # noqa: F401  (re-export por compatibilidade)
    Backtest,
    agrega_horizonte,
    estatisticas,
    histograma,
    kupiec_pof,
    monta_backtest,
    resumo_violacoes,
    retorno_carteira,
    retornos_simples,
    serializa_backtest,
)

NOME = "empirico"
ROTULO = "Empírico"
DESCRICAO = "Quantil da distribuição observada, sem hipótese de forma."


def var_empirico(retornos: np.ndarray | pd.Series, confianca: float) -> float:
    """Quantil empirico da cauda esquerda, devolvido como perda positiva."""
    amostra = np.asarray(retornos, dtype=float)
    amostra = amostra[~np.isnan(amostra)]
    if amostra.size == 0:
        return float("nan")
    return float(-np.quantile(amostra, 1.0 - confianca, method="linear"))


def expected_shortfall(retornos: np.ndarray | pd.Series, confianca: float) -> float:
    """Perda media condicional a ter estourado o VaR (CVaR)."""
    amostra = np.asarray(retornos, dtype=float)
    amostra = amostra[~np.isnan(amostra)]
    corte = -var_empirico(amostra, confianca)
    cauda = amostra[amostra <= corte]
    if cauda.size == 0:
        return float("nan")
    return float(-cauda.mean())


def pontual(retornos: pd.Series, confianca: float, horizonte: int) -> dict:
    """VaR e ES sobre a amostra inteira, no horizonte pedido."""
    serie = agrega_horizonte(retornos, horizonte)
    return {
        "var": var_empirico(serie, confianca),
        "es": expected_shortfall(serie, confianca),
    }


def var_rolling(retornos: pd.Series, confianca: float, janela: int) -> Backtest:
    """VaR recalculado a cada dia com a janela movel anterior (sem look-ahead)."""
    valores = retornos.to_numpy(dtype=float)
    if valores.size <= janela:
        return Backtest()
    vars_dia = np.array(
        [var_empirico(valores[t - janela : t], confianca) for t in range(janela, valores.size)]
    )
    return monta_backtest(retornos, vars_dia, janela)


# alias do contrato comum
rolling = var_rolling


def calcular(
    precos: pd.DataFrame,
    pesos: dict[str, float],
    confianca: float,
    horizonte: int,
    janela: int,
    valor_carteira: float,
) -> dict:
    """Payload de metodo unico — mantido para compatibilidade com /api/var/empirico."""
    ret_ativos = retornos_simples(precos)
    ret_carteira = retorno_carteira(ret_ativos, pesos)
    ret_horizonte = agrega_horizonte(ret_carteira, horizonte)

    p = pontual(ret_carteira, confianca, horizonte)
    bt = var_rolling(ret_carteira, confianca, janela)
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
        "resultado": {
            "var_percentual": round(p["var"], 6),
            "var_monetario": round(p["var"] * valor_carteira, 2),
            "es_percentual": round(p["es"], 6) if np.isfinite(p["es"]) else None,
            "es_monetario": round(p["es"] * valor_carteira, 2) if np.isfinite(p["es"]) else None,
            "pior_retorno": round(float(ret_horizonte.min()), 6),
        },
        "estatisticas": estatisticas(ret_horizonte),
        "distribuicao": histograma(ret_horizonte),
        "backtest": serializa_backtest(bt, confianca),
        "evolucao": [
            {"data": i.strftime("%Y-%m-%d"), "valor": round(float(v), 2)}
            for i, v in serie_valor.items()
        ],
    }
