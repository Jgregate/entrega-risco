"""Testes do nucleo de calculo, com dados sinteticos (sem rede)."""

import numpy as np
import pandas as pd
import pytest

from app.var_empirico import (
    agrega_horizonte,
    calcular,
    expected_shortfall,
    retorno_carteira,
    retornos_simples,
    kupiec_pof,
    var_empirico,
    var_rolling,
)


def serie_normal(n=2000, mu=0.0004, sigma=0.02, semente=42) -> pd.Series:
    rng = np.random.default_rng(semente)
    datas = pd.bdate_range("2015-01-01", periods=n)
    return pd.Series(rng.normal(mu, sigma, n), index=datas)


def precos_sinteticos(n=1500, semente=7) -> pd.DataFrame:
    rng = np.random.default_rng(semente)
    datas = pd.bdate_range("2016-01-04", periods=n)
    dados = {}
    for i, nome in enumerate(["AAA3.SA", "BBB4.SA"]):
        r = rng.normal(0.0003, 0.018 + 0.004 * i, n)
        dados[nome] = 30.0 * np.cumprod(1 + r)
    return pd.DataFrame(dados, index=datas)


def test_var_bate_com_quantil_do_numpy():
    r = serie_normal()
    for c in (0.90, 0.95, 0.99):
        assert var_empirico(r, c) == pytest.approx(-np.quantile(r.to_numpy(), 1 - c))


def test_var_cresce_com_a_confianca():
    r = serie_normal()
    assert var_empirico(r, 0.90) < var_empirico(r, 0.95) < var_empirico(r, 0.99)


def test_var_proximo_do_teorico_para_normal():
    # normal(0, 2%): VaR 95% teorico = 1.645 * 0.02 - 0.0004
    r = serie_normal(n=50_000, semente=1)
    assert var_empirico(r, 0.95) == pytest.approx(1.6449 * 0.02 - 0.0004, abs=0.001)


def test_es_maior_que_var():
    r = serie_normal()
    assert expected_shortfall(r, 0.95) > var_empirico(r, 0.95)


def test_carteira_com_um_ativo_reproduz_o_ativo():
    precos = precos_sinteticos()
    ret = retornos_simples(precos[["AAA3.SA"]])
    carteira = retorno_carteira(ret, {"AAA3.SA": 1.0})
    assert np.allclose(carteira.to_numpy(), ret["AAA3.SA"].to_numpy())


def test_pesos_sao_normalizados():
    precos = precos_sinteticos()
    ret = retornos_simples(precos)
    a = retorno_carteira(ret, {"AAA3.SA": 0.5, "BBB4.SA": 0.5})
    b = retorno_carteira(ret, {"AAA3.SA": 20.0, "BBB4.SA": 20.0})
    assert np.allclose(a.to_numpy(), b.to_numpy())


def test_diversificacao_reduz_o_var():
    precos = precos_sinteticos()
    ret = retornos_simples(precos)
    so_b = var_empirico(retorno_carteira(ret, {"AAA3.SA": 0.0001, "BBB4.SA": 0.9999}), 0.95)
    meio = var_empirico(retorno_carteira(ret, {"AAA3.SA": 0.5, "BBB4.SA": 0.5}), 0.95)
    assert meio < so_b  # ativos independentes: a mistura tem menos risco


def test_horizonte_maior_gera_var_maior():
    r = serie_normal()
    v1 = var_empirico(agrega_horizonte(r, 1), 0.95)
    v10 = var_empirico(agrega_horizonte(r, 10), 0.95)
    assert v10 > v1
    # ordem de grandeza compativel com a raiz do tempo
    assert 2.0 < v10 / v1 < 4.5


def test_backtest_sem_look_ahead_e_cobertura_correta():
    r = serie_normal(n=3000, semente=11)
    bt = var_rolling(r, confianca=0.95, janela=252)
    assert len(bt.retorno) == 3000 - 252
    taxa = sum(bt.violacao) / len(bt.violacao)
    assert 0.03 < taxa < 0.07  # deve orbitar os 5% esperados

    # violacao == retorno abaixo de -VaR
    for ret, v, viol in zip(bt.retorno, bt.var, bt.violacao):
        assert viol == (ret < -v)


def test_backtest_curto_demais_retorna_vazio():
    r = serie_normal(n=100)
    assert var_rolling(r, 0.95, 252).retorno == []


def test_kupiec_aceita_modelo_calibrado_e_rejeita_descalibrado():
    ok = kupiec_pof(n_obs=1000, n_violacoes=50, confianca=0.95)
    assert ok["p_valor"] > 0.05 and ok["rejeita_5pct"] is False

    ruim = kupiec_pof(n_obs=1000, n_violacoes=150, confianca=0.95)
    assert ruim["rejeita_5pct"] is True


def test_payload_completo():
    precos = precos_sinteticos()
    saida = calcular(
        precos=precos,
        pesos={"AAA3.SA": 0.6, "BBB4.SA": 0.4},
        confianca=0.95,
        horizonte=1,
        janela=252,
        valor_carteira=100_000.0,
    )
    assert saida["resultado"]["var_percentual"] > 0
    assert saida["resultado"]["var_monetario"] == pytest.approx(
        saida["resultado"]["var_percentual"] * 100_000, abs=0.5
    )
    assert saida["backtest"]["resumo"]["observacoes"] == len(precos) - 1 - 252
    assert len(saida["distribuicao"]) == 60
    assert saida["estatisticas"]["vol_anualizada"] > 0
