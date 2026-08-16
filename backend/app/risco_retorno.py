"""Relacao risco-retorno: Sharpe, Sortino e companhia.

Ambos medem retorno por unidade de risco; a diferenca esta no denominador.
Sharpe divide pelo desvio de TODOS os retornos — pune oscilacao para cima
do mesmo jeito que para baixo. Sortino divide so pelo desvio das quedas.
Carteira assimetrica costuma ter Sortino bem melhor que Sharpe, e a
distancia entre os dois ja diz algo sobre o perfil da estrategia.

Taxa livre de risco: Selic diaria (serie 11 do BCB).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

DIAS_UTEIS_ANO = 252


def _anualiza_retorno(retornos: np.ndarray) -> float:
    """Retorno geometrico anualizado (CAGR sobre pregoes)."""
    n = retornos.size
    if n == 0:
        return float("nan")
    acumulado = float(np.prod(1.0 + retornos))
    if acumulado <= 0:
        return -1.0
    return acumulado ** (DIAS_UTEIS_ANO / n) - 1.0


def sharpe(excesso: np.ndarray) -> float:
    """Sharpe anualizado sobre os retornos em excesso a Selic."""
    if excesso.size < 2:
        return float("nan")
    desvio = float(excesso.std(ddof=1))
    if desvio == 0:
        return float("nan")
    return float(excesso.mean() / desvio * math.sqrt(DIAS_UTEIS_ANO))


def desvio_downside(excesso: np.ndarray) -> float:
    """Desvio das quedas (alvo = 0 no excesso), na base diaria.

    Divide pelo total de observacoes, nao so pelas negativas: e a definicao
    de Sortino: uma carteira que raramente cai deve ser premiada por isso.
    """
    if excesso.size == 0:
        return float("nan")
    quedas = np.minimum(excesso, 0.0)
    return float(math.sqrt(float((quedas ** 2).mean())))


def sortino(excesso: np.ndarray) -> float:
    """Sortino anualizado sobre os retornos em excesso a Selic."""
    dd = desvio_downside(excesso)
    if not np.isfinite(dd) or dd == 0:
        return float("nan")
    return float(excesso.mean() / dd * math.sqrt(DIAS_UTEIS_ANO))


def drawdown(retornos: pd.Series) -> pd.Series:
    """Queda percentual em relacao ao topo historico, dia a dia."""
    curva = (1.0 + retornos).cumprod()
    return curva / curva.cummax() - 1.0


def _limpa(x: float) -> float | None:
    return round(float(x), 6) if np.isfinite(x) else None


def calcular(
    retorno_carteira: pd.Series,
    selic_diaria: pd.Series,
    janela_rolling: int = 252,
) -> dict:
    """Metricas de risco-retorno da carteira contra a Selic."""
    rc = retorno_carteira.astype(float)
    rf = selic_diaria.reindex(rc.index).ffill().bfill().astype(float)
    excesso = (rc - rf).to_numpy()

    r_carteira = rc.to_numpy()
    r_selic = rf.to_numpy()
    dd = drawdown(rc)

    # Sharpe e Sortino moveis: mostram se a relacao risco-retorno se manteve
    janela = min(janela_rolling, max(30, len(rc) // 3))
    exc = pd.Series(excesso, index=rc.index)
    media_movel = exc.rolling(janela).mean()
    desvio_movel = exc.rolling(janela).std(ddof=1)
    quedas2 = exc.clip(upper=0.0) ** 2
    dd_movel = quedas2.rolling(janela).mean().pow(0.5)

    fator = math.sqrt(DIAS_UTEIS_ANO)
    sharpe_movel = (media_movel / desvio_movel * fator).replace([np.inf, -np.inf], np.nan)
    sortino_movel = (media_movel / dd_movel * fator).replace([np.inf, -np.inf], np.nan)

    evolucao = []
    curva_carteira = (1.0 + rc).cumprod() - 1.0
    curva_selic = (1.0 + rf).cumprod() - 1.0
    for data, c, s, d in zip(rc.index, curva_carteira, curva_selic, dd):
        evolucao.append(
            {
                "data": data.strftime("%Y-%m-%d"),
                "carteira": round(float(c), 6),
                "selic": round(float(s), 6),
                "drawdown": round(float(d), 6),
            }
        )

    serie_indices = [
        {
            "data": data.strftime("%Y-%m-%d"),
            "sharpe": None if pd.isna(sh) else round(float(sh), 4),
            "sortino": None if pd.isna(so) else round(float(so), 4),
        }
        for data, sh, so in zip(rc.index, sharpe_movel, sortino_movel)
        if not (pd.isna(sh) and pd.isna(so))
    ]

    return {
        "sharpe": _limpa(sharpe(excesso)),
        "sortino": _limpa(sortino(excesso)),
        "retorno_anualizado": _limpa(_anualiza_retorno(r_carteira)),
        "retorno_acumulado": _limpa(float(np.prod(1.0 + r_carteira) - 1.0)),
        "selic_anualizada": _limpa(_anualiza_retorno(r_selic)),
        "selic_acumulada": _limpa(float(np.prod(1.0 + r_selic) - 1.0)),
        "excesso_anualizado": _limpa(
            _anualiza_retorno(r_carteira) - _anualiza_retorno(r_selic)
        ),
        "vol_anualizada": _limpa(float(rc.std(ddof=1)) * fator),
        "desvio_downside_anualizado": _limpa(desvio_downside(excesso) * fator),
        "max_drawdown": _limpa(float(dd.min())),
        "data_max_drawdown": dd.idxmin().strftime("%Y-%m-%d") if len(dd) else None,
        "dias_positivos": int((rc > 0).sum()),
        "dias_negativos": int((rc < 0).sum()),
        "janela_rolling": int(janela),
        "evolucao": evolucao,
        "indices_moveis": serie_indices,
    }
