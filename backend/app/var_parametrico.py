"""VaR Parametrico (normal / variancia-covariancia).

Assume que os retornos da carteira seguem uma normal e estima so dois
parametros: media e desvio. Rapido e analitico, mas subestima a cauda
sempre que o mercado tem curtose alta — que e o caso da B3.

    VaR = -(mu + z_alpha * sigma),  com z_alpha < 0
    ES  = sigma * phi(z_alpha)/alpha - mu

Convencao de sinal: VaR e reportado como PERDA POSITIVA.

NOTA: modulo escrito para destravar a comparacao entre os tres metodos.
Se a celula entregar a versao oficial do parametrico, basta trocar o corpo
de `pontual` e `rolling` — o contrato e o resto da aplicacao nao mudam.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .var_core import Backtest, monta_backtest, z_score

NOME = "parametrico"
ROTULO = "Paramétrico"
DESCRICAO = "Normal de média e desvio estimados; forma fechada."


def var_parametrico(retornos: np.ndarray | pd.Series, confianca: float) -> float:
    amostra = np.asarray(retornos, dtype=float)
    amostra = amostra[~np.isnan(amostra)]
    if amostra.size < 2:
        return float("nan")
    mu = float(amostra.mean())
    sigma = float(amostra.std(ddof=1))
    return float(-(mu + z_score(confianca) * sigma))


def es_parametrico(retornos: np.ndarray | pd.Series, confianca: float) -> float:
    """Expected shortfall analitico sob normalidade."""
    amostra = np.asarray(retornos, dtype=float)
    amostra = amostra[~np.isnan(amostra)]
    if amostra.size < 2:
        return float("nan")
    mu = float(amostra.mean())
    sigma = float(amostra.std(ddof=1))
    alpha = 1.0 - confianca
    z = z_score(confianca)
    densidade = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    return float(sigma * densidade / alpha - mu)


def pontual(retornos: pd.Series, confianca: float, horizonte: int) -> dict:
    """Escala pela raiz do tempo — coerente com a hipotese i.i.d. do metodo."""
    amostra = retornos.to_numpy(dtype=float)
    mu = float(amostra.mean()) * horizonte
    sigma = float(amostra.std(ddof=1)) * math.sqrt(horizonte)
    alpha = 1.0 - confianca
    z = z_score(confianca)
    densidade = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    return {
        "var": float(-(mu + z * sigma)),
        "es": float(sigma * densidade / alpha - mu),
    }


def rolling(retornos: pd.Series, confianca: float, janela: int) -> Backtest:
    """Media e desvio recalculados na janela movel anterior a cada pregao."""
    valores = retornos.to_numpy(dtype=float)
    n = valores.size
    if n <= janela:
        return Backtest()

    serie = pd.Series(valores)
    mu = serie.rolling(janela).mean().to_numpy()[janela - 1 : n - 1]
    sigma = serie.rolling(janela).std(ddof=1).to_numpy()[janela - 1 : n - 1]
    vars_dia = -(mu + z_score(confianca) * sigma)
    return monta_backtest(retornos, vars_dia, janela)
