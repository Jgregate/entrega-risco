"""Nucleo compartilhado pelos tres metodos de VaR.

Cada metodo (empirico, parametrico, EWMA) precisa responder duas perguntas
com a mesma assinatura, e e isso que este modulo padroniza:

  1. VaR pontual   -> qual a perda no horizonte, dada a amostra inteira?
  2. VaR rolling   -> qual era o limite em cada pregao, usando so o passado?

Convencao de sinal em todo o projeto: VaR e PERDA POSITIVA.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist

import numpy as np
import pandas as pd

DIAS_UTEIS_ANO = 252


# --------------------------------------------------------------------------- #
# Retornos da carteira
# --------------------------------------------------------------------------- #

def retornos_simples(precos: pd.DataFrame) -> pd.DataFrame:
    """Retornos aritmeticos diarios."""
    return precos.pct_change().dropna(how="any")


def retorno_carteira(retornos: pd.DataFrame, pesos: dict[str, float]) -> pd.Series:
    """Retorno da carteira: combinacao linear dos retornos simples.

    Assume rebalanceamento diario para os pesos alvo, hipotese padrao em
    mensuracao de risco de curto prazo.
    """
    w = np.array([pesos[c] for c in retornos.columns], dtype=float)
    soma = w.sum()
    if not np.isclose(soma, 1.0):
        w = w / soma
    return pd.Series(retornos.to_numpy() @ w, index=retornos.index, name="carteira")


def agrega_horizonte(retornos: pd.Series, horizonte: int) -> pd.Series:
    """Retornos acumulados de `horizonte` dias em janelas sobrepostas."""
    if horizonte <= 1:
        return retornos
    acumulado = (1.0 + retornos).rolling(horizonte).apply(np.prod, raw=True) - 1.0
    return acumulado.dropna()


def z_score(confianca: float) -> float:
    """Quantil da normal padrao na cauda esquerda (valor negativo)."""
    return NormalDist().inv_cdf(1.0 - confianca)


# --------------------------------------------------------------------------- #
# Backtest
# --------------------------------------------------------------------------- #

@dataclass
class Backtest:
    datas: list[str] = field(default_factory=list)
    retorno: list[float] = field(default_factory=list)
    var: list[float] = field(default_factory=list)  # perda positiva
    violacao: list[bool] = field(default_factory=list)


def monta_backtest(retornos: pd.Series, vars_por_dia: np.ndarray, inicio: int) -> Backtest:
    """Emparelha a serie de VaR com o retorno realizado a partir de `inicio`."""
    valores = retornos.to_numpy(dtype=float)
    bt = Backtest()
    for k, t in enumerate(range(inicio, valores.size)):
        v = float(vars_por_dia[k])
        r = float(valores[t])
        bt.datas.append(retornos.index[t].strftime("%Y-%m-%d"))
        bt.retorno.append(r)
        bt.var.append(v)
        bt.violacao.append(bool(r < -v))
    return bt


def _p_valor_qui2_1gl(estatistica: float) -> float:
    """P(X > x) para qui-quadrado com 1 grau de liberdade."""
    if not np.isfinite(estatistica) or estatistica <= 0:
        return 1.0
    return float(math.erfc(math.sqrt(estatistica / 2.0)))


def kupiec_pof(n_obs: int, n_violacoes: int, confianca: float) -> dict:
    """Teste de cobertura incondicional de Kupiec (POF).

    H0: a taxa de violacoes e igual a (1 - confianca).
    Rejeitar H0 a 5% indica modelo mal calibrado.
    """
    p = 1.0 - confianca
    x, n = n_violacoes, n_obs
    if n == 0:
        return {"estatistica_lr": None, "p_valor": None, "rejeita_5pct": None}

    pi = x / n
    if x == 0:
        lr = -2.0 * (n * math.log(1 - p))
    elif x == n:
        lr = -2.0 * (n * math.log(p))
    else:
        log_h0 = (n - x) * math.log(1 - p) + x * math.log(p)
        log_h1 = (n - x) * math.log(1 - pi) + x * math.log(pi)
        lr = -2.0 * (log_h0 - log_h1)

    return {
        "estatistica_lr": round(float(lr), 4),
        "p_valor": round(float(_p_valor_qui2_1gl(lr)), 4),
        "rejeita_5pct": bool(_p_valor_qui2_1gl(lr) < 0.05),
    }


def resumo_violacoes(bt: Backtest, confianca: float) -> dict:
    n = len(bt.retorno)
    violacoes = int(sum(bt.violacao))
    if n == 0:
        return {
            "observacoes": 0,
            "violacoes": 0,
            "violacoes_esperadas": 0.0,
            "taxa_observada": None,
            "taxa_esperada": round(1.0 - confianca, 6),
            "maior_sequencia": 0,
            "excesso_medio": None,
            "pior_excesso": None,
            "kupiec": kupiec_pof(0, 0, confianca),
        }

    maior_seq = atual = 0
    for v in bt.violacao:
        atual = atual + 1 if v else 0
        maior_seq = max(maior_seq, atual)

    excessos = [-(r + v) for r, v, viol in zip(bt.retorno, bt.var, bt.violacao) if viol]

    return {
        "observacoes": n,
        "violacoes": violacoes,
        "violacoes_esperadas": round((1.0 - confianca) * n, 2),
        "taxa_observada": round(violacoes / n, 6),
        "taxa_esperada": round(1.0 - confianca, 6),
        "maior_sequencia": maior_seq,
        "excesso_medio": round(float(np.mean(excessos)), 6) if excessos else None,
        "pior_excesso": round(float(np.max(excessos)), 6) if excessos else None,
        "kupiec": kupiec_pof(n, violacoes, confianca),
    }


def serializa_backtest(bt: Backtest, confianca: float) -> dict:
    return {
        "serie": [
            {"data": d, "retorno": round(r, 6), "var": round(-v, 6), "violacao": viol}
            for d, r, v, viol in zip(bt.datas, bt.retorno, bt.var, bt.violacao)
        ],
        "resumo": resumo_violacoes(bt, confianca),
    }


# --------------------------------------------------------------------------- #
# Distribuicao e estatisticas descritivas
# --------------------------------------------------------------------------- #

def histograma(retornos: pd.Series, n_bins: int = 60) -> list[dict]:
    """Histograma de densidade + normal de mesma media/desvio (referencia)."""
    valores = retornos.to_numpy(dtype=float)
    contagem, bordas = np.histogram(valores, bins=n_bins, density=True)
    centros = (bordas[:-1] + bordas[1:]) / 2.0
    mu, sigma = float(valores.mean()), float(valores.std(ddof=1))
    normal = (
        1.0 / (sigma * math.sqrt(2 * math.pi)) * np.exp(-0.5 * ((centros - mu) / sigma) ** 2)
        if sigma > 0
        else np.zeros_like(centros)
    )
    return [
        {
            "retorno": round(float(c), 6),
            "densidade": round(float(d), 4),
            "normal": round(float(nrm), 4),
        }
        for c, d, nrm in zip(centros, contagem, normal)
    ]


def estatisticas(retornos: pd.Series) -> dict:
    v = retornos.to_numpy(dtype=float)
    mu = float(v.mean())
    sigma = float(v.std(ddof=1))
    z = (v - mu) / sigma if sigma > 0 else np.zeros_like(v)
    return {
        "observacoes": int(v.size),
        "media": round(mu, 6),
        "desvio_padrao": round(sigma, 6),
        "vol_anualizada": round(sigma * math.sqrt(DIAS_UTEIS_ANO), 6),
        "assimetria": round(float((z ** 3).mean()), 4),
        "curtose_excesso": round(float((z ** 4).mean() - 3.0), 4),
        "minimo": round(float(v.min()), 6),
        "maximo": round(float(v.max()), 6),
    }
