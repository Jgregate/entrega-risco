"""Testes dos tres metodos de VaR e da orquestracao, com dados sinteticos."""

import numpy as np
import pandas as pd
import pytest

from app import var_empirico, var_ewma, var_parametrico
from app.analise import analisar
from app.var_core import z_score


def serie_normal(n=3000, mu=0.0004, sigma=0.02, semente=42) -> pd.Series:
    rng = np.random.default_rng(semente)
    return pd.Series(rng.normal(mu, sigma, n), index=pd.bdate_range("2013-01-01", periods=n))


def precos_sinteticos(n=1500, semente=7) -> pd.DataFrame:
    rng = np.random.default_rng(semente)
    datas = pd.bdate_range("2016-01-04", periods=n)
    return pd.DataFrame(
        {
            nome: 30.0 * np.cumprod(1 + rng.normal(0.0003, 0.018 + 0.004 * i, n))
            for i, nome in enumerate(["AAA3.SA", "BBB4.SA"])
        },
        index=datas,
    )


MODULOS = [var_empirico, var_parametrico, var_ewma]


def test_z_score_bate_com_a_tabela():
    assert z_score(0.95) == pytest.approx(-1.6449, abs=1e-4)
    assert z_score(0.99) == pytest.approx(-2.3263, abs=1e-4)


@pytest.mark.parametrize("modulo", MODULOS, ids=lambda m: m.NOME)
def test_contrato_comum(modulo):
    """Os tres metodos respondem a mesma assinatura — e o que o front assume."""
    r = serie_normal()
    p = modulo.pontual(r, 0.95, 1)
    assert p["var"] > 0 and p["es"] > p["var"]
    assert modulo.NOME and modulo.ROTULO and modulo.DESCRICAO

    bt = modulo.rolling(r, 0.95, 252)
    assert len(bt.retorno) == len(bt.var) == len(bt.violacao) == len(r) - 252
    for ret, v, viol in zip(bt.retorno, bt.var, bt.violacao):
        assert viol == (ret < -v)


@pytest.mark.parametrize("modulo", MODULOS, ids=lambda m: m.NOME)
def test_var_cresce_com_confianca_e_horizonte(modulo):
    r = serie_normal()
    assert modulo.pontual(r, 0.90, 1)["var"] < modulo.pontual(r, 0.99, 1)["var"]
    assert modulo.pontual(r, 0.95, 1)["var"] < modulo.pontual(r, 0.95, 10)["var"]


@pytest.mark.parametrize("modulo", MODULOS, ids=lambda m: m.NOME)
def test_cobertura_do_backtest_orbita_o_nivel(modulo):
    """Com dados normais, os tres devem violar perto de 5% das vezes."""
    r = serie_normal(n=4000, semente=11)
    bt = modulo.rolling(r, 0.95, 252)
    taxa = sum(bt.violacao) / len(bt.violacao)
    assert 0.03 < taxa < 0.07


def test_parametrico_reproduz_a_formula_fechada():
    r = serie_normal()
    mu, sigma = r.mean(), r.std(ddof=1)
    esperado = -(mu + z_score(0.99) * sigma)
    assert var_parametrico.var_parametrico(r, 0.99) == pytest.approx(esperado)


def test_metodos_concordam_quando_os_dados_sao_normais():
    """Amostra normal grande: empirico e parametrico devem quase coincidir."""
    r = serie_normal(n=60_000, semente=3)
    emp = var_empirico.var_empirico(r, 0.95)
    par = var_parametrico.var_parametrico(r, 0.95)
    assert emp == pytest.approx(par, rel=0.03)


def test_parametrico_subestima_cauda_gorda():
    """Com curtose alta, o empirico enxerga o que a normal nao ve.

    t de Student com 3 g.l. padronizada: mesma variancia da normal, cauda
    muito mais pesada. A distancia entre os dois metodos cresce conforme se
    anda para a ponta da distribuicao — e por isso que ela e medida a 99,5%.
    """
    rng = np.random.default_rng(5)
    bruto = rng.standard_t(3, 20_000)
    r = pd.Series(
        bruto / bruto.std() * 0.02, index=pd.bdate_range("2000-01-03", periods=20_000)
    )
    assert var_empirico.var_empirico(r, 0.995) > var_parametrico.var_parametrico(r, 0.995) * 1.2
    # a 95% o efeito se inverte: no miolo a normal e mais conservadora
    assert var_empirico.var_empirico(r, 0.95) < var_parametrico.var_parametrico(r, 0.95)


def test_ewma_reage_mais_rapido_a_choque_de_volatilidade():
    """Depois de um susto, o EWMA sobe o limite antes do empirico."""
    rng = np.random.default_rng(9)
    calmo = rng.normal(0, 0.008, 600)
    estresse = rng.normal(0, 0.045, 40)
    r = pd.Series(
        np.concatenate([calmo, estresse]),
        index=pd.bdate_range("2019-01-01", periods=640),
    )
    janela = 252
    ewma = var_ewma.rolling(r, 0.95, janela)
    emp = var_empirico.rolling(r, 0.95, janela)
    # ultimo dia do periodo de estresse
    assert ewma.var[-1] > emp.var[-1] * 1.5


def test_ewma_nao_usa_o_retorno_do_proprio_dia():
    """Trocar o ultimo retorno nao pode mexer no VaR previsto para ele."""
    r = serie_normal(n=800, semente=21)
    bt1 = var_ewma.rolling(r, 0.95, 252)
    alterada = r.copy()
    alterada.iloc[-1] = -0.35
    bt2 = var_ewma.rolling(alterada, 0.95, 252)
    assert bt1.var[-1] == pytest.approx(bt2.var[-1])
    assert bt2.violacao[-1] is True  # o choque vira violacao, nao vira limite


def test_payload_da_analise_tem_os_tres_metodos():
    precos = precos_sinteticos()
    saida = analisar(
        precos=precos,
        pesos={"AAA3.SA": 0.6, "BBB4.SA": 0.4},
        confianca=0.95,
        horizonte=1,
        janela=252,
        valor_carteira=250_000.0,
    )
    assert set(saida["metodos"]) == {"empirico", "parametrico", "ewma"}
    for bloco in saida["metodos"].values():
        assert bloco["var_percentual"] > 0
        assert bloco["backtest"]["resumo"]["observacoes"] == len(precos) - 1 - 252
        assert bloco["backtest"]["resumo"]["kupiec"]["p_valor"] is not None

    book = saida["book"]
    assert len(book) == 2
    assert sum(l["valor_nominal"] for l in book) == pytest.approx(250_000.0, abs=0.5)
    assert book[0]["valor_nominal"] == pytest.approx(0.6 * 250_000.0, abs=0.5)
    assert book[0]["quantidade"] * book[0]["preco_final"] == pytest.approx(
        book[0]["valor_nominal"], rel=1e-3
    )
