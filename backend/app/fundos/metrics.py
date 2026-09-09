"""Metricas mensais de fundo (retorno, volatilidade, Sharpe, Sortino).

Portado de `prot.py` do sistema FUNDOS original - so a funcao generica
`metrics_mensais`, que ja era parametrizada por series (nao pelo dataset
hardcoded de um fundo especifico que vivia no resto daquele arquivo).
"""

from __future__ import annotations

import math

import numpy as np


def metrics_mensais(n_meses, fund_list, cdi_list, months) -> dict:
    """Retorno acumulado, volatilidade anualizada, Sharpe e Sortino usando
    os ultimos n_meses meses FECHADOS da serie (CDI como risk-free/MAR)."""
    f = np.array(fund_list[-n_meses:]) / 100
    c = np.array(cdi_list[-n_meses:]) / 100
    janela = months[-n_meses:]

    cum_fund = np.prod(1 + f) - 1
    cum_cdi = np.prod(1 + c) - 1
    vol_ann = np.std(f, ddof=1) * math.sqrt(12)
    ann_fund = (1 + cum_fund) ** (12 / n_meses) - 1
    ann_cdi = (1 + cum_cdi) ** (12 / n_meses) - 1
    sharpe = (ann_fund - ann_cdi) / vol_ann if vol_ann else float("nan")

    excess = f - c
    downside = excess[excess < 0]
    dd_ann = np.sqrt(np.mean(downside ** 2)) * math.sqrt(12) if len(downside) else np.nan
    sortino = (np.mean(excess) * 12) / dd_ann if dd_ann else float("nan")

    return {
        "janela_meses": n_meses,
        "periodo": f"{janela[0][1]:02d}/{janela[0][0]} a {janela[-1][1]:02d}/{janela[-1][0]}",
        "retorno_acumulado_%": round(cum_fund * 100, 2),
        "retorno_cdi_%": round(cum_cdi * 100, 2),
        "volatilidade_anualizada_%": round(vol_ann * 100, 2),
        "sharpe": round(sharpe, 3) if np.isfinite(sharpe) else None,
        "sortino": round(sortino, 3) if np.isfinite(sortino) else None,
    }
