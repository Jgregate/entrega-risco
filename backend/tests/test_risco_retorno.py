"""Testes de Sharpe, Sortino e do tratamento da Selic."""

import math

import numpy as np
import pandas as pd
import pytest

from app import risco_retorno as rr
from app.selic import alinha_com_carteira, taxa_anual_para_diaria


def serie(n=1260, mu=0.0006, sigma=0.012, semente=1) -> pd.Series:
    rng = np.random.default_rng(semente)
    return pd.Series(rng.normal(mu, sigma, n), index=pd.bdate_range("2020-01-01", periods=n))


def selic_constante(indice, anual=0.1) -> pd.Series:
    return pd.Series(taxa_anual_para_diaria(anual), index=indice)


def test_taxa_anual_vira_diaria_composta():
    d = taxa_anual_para_diaria(0.15)
    assert (1 + d) ** 252 == pytest.approx(1.15)


def test_sharpe_bate_com_a_formula():
    r = serie()
    rf = selic_constante(r.index)
    excesso = (r - rf).to_numpy()
    esperado = excesso.mean() / excesso.std(ddof=1) * math.sqrt(252)
    assert rr.sharpe(excesso) == pytest.approx(esperado)


def test_sortino_maior_que_sharpe_quando_a_cauda_esquerda_e_curta():
    """Retornos com assimetria positiva: o desvio total pune, o downside nao."""
    rng = np.random.default_rng(4)
    base = rng.normal(0.0004, 0.008, 2000)
    base[::40] += 0.05  # saltos so para cima
    excesso = base - taxa_anual_para_diaria(0.10)
    assert rr.sortino(excesso) > rr.sharpe(excesso)


def test_sharpe_zero_quando_a_carteira_rende_a_selic():
    idx = pd.bdate_range("2021-01-01", periods=500)
    taxa = taxa_anual_para_diaria(0.12)
    carteira = pd.Series(taxa, index=idx)
    saida = rr.calcular(carteira, pd.Series(taxa, index=idx))
    assert saida["sharpe"] is None  # desvio zero: indice indefinido, nao infinito
    assert saida["retorno_anualizado"] == pytest.approx(0.12, abs=1e-6)
    assert saida["excesso_anualizado"] == pytest.approx(0.0, abs=1e-9)


def test_downside_usa_todas_as_observacoes_no_denominador():
    excesso = np.array([0.02, -0.01, 0.03, -0.02])
    esperado = math.sqrt((0.01 ** 2 + 0.02 ** 2) / 4)
    assert rr.desvio_downside(excesso) == pytest.approx(esperado)


def test_max_drawdown_de_queda_conhecida():
    # sobe 10%, cai 20%, sobe 5%  ->  pior queda = -20% a partir do topo
    r = pd.Series([0.10, -0.20, 0.05], index=pd.bdate_range("2022-01-03", periods=3))
    saida = rr.calcular(r, pd.Series(0.0, index=r.index))
    assert saida["max_drawdown"] == pytest.approx(-0.20, abs=1e-9)
    assert saida["data_max_drawdown"] == "2022-01-04"


def test_payload_traz_as_curvas():
    r = serie()
    saida = rr.calcular(r, selic_constante(r.index), janela_rolling=252)
    assert len(saida["evolucao"]) == len(r)
    assert {"data", "carteira", "selic", "drawdown"} <= set(saida["evolucao"][0])
    assert len(saida["indices_moveis"]) > 0
    assert saida["dias_positivos"] + saida["dias_negativos"] <= len(r)


def test_selic_e_reindexada_no_calendario_da_carteira():
    """Feriado bancario que nao e feriado de bolsa nao pode furar a serie."""
    idx_selic = pd.bdate_range("2023-01-02", periods=10)
    s = pd.Series(np.linspace(0.0004, 0.0005, 10), index=idx_selic)
    s = s.drop(s.index[3])  # dia sem publicacao

    alinhada = alinha_com_carteira(s, idx_selic)
    assert len(alinhada) == 10
    assert not alinhada.isna().any()
    assert alinhada.iloc[3] == alinhada.iloc[2]  # manteve a ultima taxa conhecida
