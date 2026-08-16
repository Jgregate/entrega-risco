"""VaR EWMA (RiskMetrics).

Mesma forma fechada do parametrico, mas com a variancia estimada por media
movel exponencial: o passado recente pesa mais que o antigo.

    sigma²_t = lambda * sigma²_{t-1} + (1 - lambda) * r²_{t-1}
    VaR_t    = -z_alpha * sigma_t          (media assumida como zero)

lambda = 0,94 e o valor do RiskMetrics para dados diarios. Como sigma_t so
usa retornos ate t-1, o backtest continua livre de look-ahead.

Convencao de sinal: VaR e reportado como PERDA POSITIVA.

NOTA: modulo escrito para destravar a comparacao entre os tres metodos.
Se a celula entregar a versao oficial do EWMA, basta trocar o corpo de
`pontual` e `rolling` — o contrato e o resto da aplicacao nao mudam.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .var_core import Backtest, monta_backtest, z_score

NOME = "ewma"
ROTULO = "EWMA"
DESCRICAO = "Volatilidade com decaimento exponencial (λ = 0,94)."

LAMBDA_PADRAO = 0.94


def serie_volatilidade(
    retornos: np.ndarray, lamb: float = LAMBDA_PADRAO, aquecimento: int = 60
) -> np.ndarray:
    """Vetor de sigma previsto para cada dia t, usando so retornos ate t-1.

    Devolve um array do mesmo tamanho da entrada. As primeiras `aquecimento`
    posicoes servem de semente e nao devem ser usadas para decidir risco.
    """
    n = retornos.size
    sigma2 = np.empty(n, dtype=float)
    semente = max(2, min(aquecimento, n))
    var_inicial = float(np.var(retornos[:semente], ddof=1))
    sigma2[0] = var_inicial
    for t in range(1, n):
        sigma2[t] = lamb * sigma2[t - 1] + (1.0 - lamb) * retornos[t - 1] ** 2
    return np.sqrt(sigma2)


def var_ewma(
    retornos: np.ndarray | pd.Series, confianca: float, lamb: float = LAMBDA_PADRAO
) -> float:
    """VaR de 1 dia a frente, com a volatilidade EWMA no fim da amostra."""
    amostra = np.asarray(retornos, dtype=float)
    amostra = amostra[~np.isnan(amostra)]
    if amostra.size < 3:
        return float("nan")
    sigmas = serie_volatilidade(amostra, lamb)
    sigma_frente = math.sqrt(
        lamb * sigmas[-1] ** 2 + (1.0 - lamb) * amostra[-1] ** 2
    )
    return float(-z_score(confianca) * sigma_frente)


def pontual(
    retornos: pd.Series, confianca: float, horizonte: int, lamb: float = LAMBDA_PADRAO
) -> dict:
    amostra = retornos.to_numpy(dtype=float)
    sigmas = serie_volatilidade(amostra, lamb)
    sigma = math.sqrt(lamb * sigmas[-1] ** 2 + (1.0 - lamb) * amostra[-1] ** 2)
    sigma_h = sigma * math.sqrt(horizonte)

    alpha = 1.0 - confianca
    z = z_score(confianca)
    densidade = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    return {
        "var": float(-z * sigma_h),
        "es": float(sigma_h * densidade / alpha),
        "vol_atual": round(float(sigma), 6),
    }


def rolling(
    retornos: pd.Series, confianca: float, janela: int, lamb: float = LAMBDA_PADRAO
) -> Backtest:
    """Serie de VaR diaria.

    A janela aqui so define de onde o backtest comeca a valer — o EWMA em si
    tem memoria infinita com peso decrescente, nao janela fixa. Manter o mesmo
    ponto de partida dos outros metodos e o que torna a comparacao honesta.
    """
    valores = retornos.to_numpy(dtype=float)
    n = valores.size
    if n <= janela:
        return Backtest()

    sigmas = serie_volatilidade(valores, lamb, aquecimento=janela)
    vars_dia = -z_score(confianca) * sigmas[janela:]
    return monta_backtest(retornos, vars_dia, janela)
