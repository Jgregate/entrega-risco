"""VaR Empirico (simulacao historica).

Nenhuma hipotese sobre a forma da distribuicao: o VaR e simplesmente o
quantil da amostra de retornos observados da carteira.

Convencao de sinal: VaR e reportado como PERDA POSITIVA.
Um VaR de 0,032 a 95% significa "em 5% dos dias a perda supera 3,2%".
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Retornos
# --------------------------------------------------------------------------- #

def retornos_simples(precos: pd.DataFrame) -> pd.DataFrame:
    """Retornos aritmeticos diarios."""
    return precos.pct_change().dropna(how="any")


def retorno_carteira(retornos: pd.DataFrame, pesos: dict[str, float]) -> pd.Series:
    """Retorno da carteira: combinacao linear dos retornos simples.

    Assume rebalanceamento diario para os pesos alvo, que e a hipotese
    padrao em mensuracao de risco de curto prazo.
    """
    w = np.array([pesos[c] for c in retornos.columns], dtype=float)
    soma = w.sum()
    if not np.isclose(soma, 1.0):
        w = w / soma
    serie = pd.Series(retornos.to_numpy() @ w, index=retornos.index, name="carteira")
    return serie


def agrega_horizonte(retornos: pd.Series, horizonte: int) -> pd.Series:
    """Retornos acumulados de `horizonte` dias em janelas sobrepostas.

    Para h > 1 o VaR empirico e calculado direto sobre retornos de h dias,
    em vez de escalar por raiz(h) - assim nao se assume independencia
    nem variancia constante.
    """
    if horizonte <= 1:
        return retornos
    acumulado = (1.0 + retornos).rolling(horizonte).apply(np.prod, raw=True) - 1.0
    return acumulado.dropna()


# --------------------------------------------------------------------------- #
# VaR e Expected Shortfall
# --------------------------------------------------------------------------- #

def var_empirico(retornos: np.ndarray | pd.Series, confianca: float) -> float:
    """Quantil empirico da cauda esquerda, devolvido como perda positiva."""
    amostra = np.asarray(retornos, dtype=float)
    amostra = amostra[~np.isnan(amostra)]
    if amostra.size == 0:
        return float("nan")
    quantil = np.quantile(amostra, 1.0 - confianca, method="linear")
    return float(-quantil)


def expected_shortfall(retornos: np.ndarray | pd.Series, confianca: float) -> float:
    """Perda media condicional a ter estourado o VaR (CVaR)."""
    amostra = np.asarray(retornos, dtype=float)
    amostra = amostra[~np.isnan(amostra)]
    corte = -var_empirico(amostra, confianca)
    cauda = amostra[amostra <= corte]
    if cauda.size == 0:
        return float("nan")
    return float(-cauda.mean())


# --------------------------------------------------------------------------- #
# Backtest / historico de violacoes
# --------------------------------------------------------------------------- #

@dataclass
class Backtest:
    datas: list[str] = field(default_factory=list)
    retorno: list[float] = field(default_factory=list)
    var: list[float] = field(default_factory=list)
    violacao: list[bool] = field(default_factory=list)


def var_rolling(retornos: pd.Series, confianca: float, janela: int) -> Backtest:
    """VaR recalculado a cada dia com a janela movel anterior.

    O VaR do dia t usa apenas os `janela` retornos ATE t-1 (sem look-ahead).
    Ha violacao quando o retorno realizado em t fica abaixo de -VaR_t.
    """
    valores = retornos.to_numpy(dtype=float)
    n = valores.size
    bt = Backtest()
    if n <= janela:
        return bt

    for t in range(janela, n):
        historico = valores[t - janela : t]
        v = var_empirico(historico, confianca)
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

    p_valor = _p_valor_qui2_1gl(lr)
    return {
        "estatistica_lr": round(float(lr), 4),
        "p_valor": round(float(p_valor), 4),
        "rejeita_5pct": bool(p_valor < 0.05),
    }


def resumo_violacoes(bt: Backtest, confianca: float) -> dict:
    n = len(bt.retorno)
    violacoes = int(sum(bt.violacao))
    esperado = (1.0 - confianca) * n

    # maior sequencia de violacoes consecutivas (agrupamento de risco)
    maior_seq = atual = 0
    for v in bt.violacao:
        atual = atual + 1 if v else 0
        maior_seq = max(maior_seq, atual)

    excessos = [
        -(r + v) for r, v, viol in zip(bt.retorno, bt.var, bt.violacao) if viol
    ]

    return {
        "observacoes": n,
        "violacoes": violacoes,
        "violacoes_esperadas": round(esperado, 2),
        "taxa_observada": round(violacoes / n, 6) if n else None,
        "taxa_esperada": round(1.0 - confianca, 6),
        "maior_sequencia": maior_seq,
        "excesso_medio": round(float(np.mean(excessos)), 6) if excessos else None,
        "pior_excesso": round(float(np.max(excessos)), 6) if excessos else None,
        "kupiec": kupiec_pof(n, violacoes, confianca),
    }


# --------------------------------------------------------------------------- #
# Distribuicao
# --------------------------------------------------------------------------- #

def histograma(retornos: pd.Series, n_bins: int = 60) -> list[dict]:
    """Histograma de densidade + densidade normal de mesma media/desvio.

    A normal serve so de referencia visual: o VaR empirico nao a utiliza.
    """
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
    n = v.size
    mu = float(v.mean())
    sigma = float(v.std(ddof=1))
    z = (v - mu) / sigma if sigma > 0 else np.zeros_like(v)
    return {
        "observacoes": int(n),
        "media": round(mu, 6),
        "desvio_padrao": round(sigma, 6),
        "vol_anualizada": round(sigma * math.sqrt(252), 6),
        "assimetria": round(float((z ** 3).mean()), 4),
        "curtose_excesso": round(float((z ** 4).mean() - 3.0), 4),
        "minimo": round(float(v.min()), 6),
        "maximo": round(float(v.max()), 6),
    }


# --------------------------------------------------------------------------- #
# Orquestracao
# --------------------------------------------------------------------------- #

def calcular(
    precos: pd.DataFrame,
    pesos: dict[str, float],
    confianca: float,
    horizonte: int,
    janela: int,
    valor_carteira: float,
) -> dict:
    """Pipeline completo do VaR empirico para a carteira."""
    ret_ativos = retornos_simples(precos)
    ret_carteira = retorno_carteira(ret_ativos, pesos)
    ret_horizonte = agrega_horizonte(ret_carteira, horizonte)

    var = var_empirico(ret_horizonte, confianca)
    es = expected_shortfall(ret_horizonte, confianca)

    # o backtest de violacoes e sempre diario (horizonte 1), que e o
    # padrao regulatorio para contagem de excecoes
    bt = var_rolling(ret_carteira, confianca, janela)

    serie_precos = (1.0 + ret_carteira).cumprod() * valor_carteira

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
            "var_percentual": round(var, 6),
            "var_monetario": round(var * valor_carteira, 2),
            "es_percentual": round(es, 6) if np.isfinite(es) else None,
            "es_monetario": round(es * valor_carteira, 2) if np.isfinite(es) else None,
            "pior_retorno": round(float(ret_horizonte.min()), 6),
        },
        "estatisticas": estatisticas(ret_horizonte),
        "distribuicao": histograma(ret_horizonte),
        "backtest": {
            "serie": [
                {"data": d, "retorno": round(r, 6), "var": round(-v, 6), "violacao": viol}
                for d, r, v, viol in zip(bt.datas, bt.retorno, bt.var, bt.violacao)
            ],
            "resumo": resumo_violacoes(bt, confianca),
        },
        "evolucao": [
            {"data": i.strftime("%Y-%m-%d"), "valor": round(float(v), 2)}
            for i, v in serie_precos.items()
        ],
    }
