"""Testes das metricas de fundo — tudo sem rede, com series sinteticas cujo
resultado correto da para calcular na mao, no mesmo espirito de
test_risco_retorno.py.
"""

import math

import numpy as np
import pandas as pd
import pytest

from app.fundos import analytics


def serie_cotas(retornos, inicio="2025-01-01", cota_inicial=100.0):
    """Cotas diarias em dias uteis a partir de uma lista de retornos."""
    datas = pd.bdate_range(inicio, periods=len(retornos) + 1)
    cotas = [cota_inicial]
    for r in retornos:
        cotas.append(cotas[-1] * (1 + r))
    return pd.Series(cotas, index=datas)


# --------------------------------------------------------------------------- #
# Series basicas
# --------------------------------------------------------------------------- #

def test_retornos_diarios_reproduz_os_retornos_de_origem():
    origem = [0.01, -0.02, 0.005, 0.0]
    r = analytics.retornos_diarios(serie_cotas(origem))

    assert len(r) == len(origem)
    assert r.to_numpy() == pytest.approx(origem, abs=1e-12)


def test_retorno_acumulado_e_composto_nao_somado():
    r = analytics.retornos_diarios(serie_cotas([0.10, 0.10, 0.10]))

    # 1,1^3 - 1 = 33,1%, nao 30%
    assert analytics.acumulado(r) == pytest.approx(0.331, abs=1e-9)


def test_anualizado_nao_extrapola_periodo_menor_que_um_ano():
    """Anualizar 20 dias de alta forte produziria um numero que o usuario
    leria como projecao — o contrato e devolver NaN."""
    curto = analytics.retornos_diarios(serie_cotas([0.01] * 20))
    assert math.isnan(analytics.anualizado(curto))

    seis_meses = analytics.retornos_diarios(serie_cotas([0.001] * 126))
    assert math.isnan(analytics.anualizado(seis_meses))

    longo = analytics.retornos_diarios(serie_cotas([0.0004] * 252))
    acum = analytics.acumulado(longo)
    dias = (longo.index[-1] - longo.index[0]).days
    esperado = (1 + acum) ** (365.25 / dias) - 1
    assert analytics.anualizado(longo) == pytest.approx(esperado, rel=1e-9)


def test_anualiza_janela_de_12_meses_mesmo_com_menos_de_252_pregoes():
    """Fundo nao reporta todo dia util: 12 meses costumam render 245-251
    pregoes, e um corte por contagem apagaria o Sharpe da janela principal."""
    # fundo que deixa de reportar ~1 dia a cada 20, como acontece de verdade
    completa = serie_cotas([0.0005] * 400, inicio="2025-01-01")
    esparsa = completa[[i % 20 != 7 for i in range(len(completa))]]
    doze_meses = analytics.retornos_diarios(analytics.recorta(esparsa, 12))

    assert len(doze_meses) < analytics.DIAS_UTEIS_ANO
    assert math.isfinite(analytics.anualizado(doze_meses))

    cdi = pd.Series(0.0001, index=doze_meses.index)
    assert analytics.metricas(doze_meses, None, cdi)["sharpe"] is not None


def test_volatilidade_anualiza_por_raiz_de_252():
    rng = np.random.default_rng(42)
    diarios = rng.normal(0.0, 0.01, 1000)
    r = analytics.retornos_diarios(serie_cotas(diarios))

    esperado = float(np.std(diarios, ddof=1)) * math.sqrt(252)
    assert analytics.volatilidade(r) == pytest.approx(esperado, rel=1e-9)


def test_serie_sem_variacao_tem_volatilidade_zero_e_sharpe_indefinido():
    r = analytics.retornos_diarios(serie_cotas([0.0] * 300))
    saida = analytics.metricas(r, None, r)

    assert saida["volatilidade_anualizada"] == pytest.approx(0.0)
    assert saida["sharpe"] is None  # divisao por zero nao vira numero


# --------------------------------------------------------------------------- #
# Drawdown
# --------------------------------------------------------------------------- #

def test_drawdown_mede_queda_sobre_o_topo_anterior():
    # sobe 20%, cai 50% do topo, recupera parte
    r = analytics.retornos_diarios(serie_cotas([0.20, -0.50, 0.30]))
    dd = analytics.serie_drawdown(r)

    assert dd.iloc[0] == pytest.approx(0.0)      # no topo
    assert dd.iloc[1] == pytest.approx(-0.50)    # fundo
    assert dd.iloc[2] == pytest.approx(-0.35)    # 0,5 * 1,3 = 0,65 do topo


def test_resumo_drawdown_acha_fundo_topo_e_recuperacao():
    r = analytics.retornos_diarios(serie_cotas([-0.10, -0.10, 0.50]))
    resumo = analytics.resumo_drawdown(r)

    assert resumo["maximo"] == pytest.approx(-0.19, abs=1e-9)
    assert resumo["data_maximo"] == r.index[1].strftime("%Y-%m-%d")
    assert resumo["em_recuperacao"] is False
    assert resumo["dias_recuperacao"] is not None


def test_drawdown_ainda_aberto_e_sinalizado_como_em_recuperacao():
    r = analytics.retornos_diarios(serie_cotas([0.10, -0.30]))
    resumo = analytics.resumo_drawdown(r)

    assert resumo["em_recuperacao"] is True
    assert resumo["data_recuperacao"] is None
    assert resumo["dias_recuperacao"] is None
    assert resumo["atual"] == pytest.approx(resumo["maximo"])


# --------------------------------------------------------------------------- #
# Serie mensal e consistencia
# --------------------------------------------------------------------------- #

def test_retornos_mensais_compoem_dentro_do_mes():
    r = analytics.retornos_diarios(serie_cotas([0.001] * 40, inicio="2025-01-01"))
    mensal = analytics.retornos_mensais(r)

    de_janeiro = r[r.index.month == 1]
    assert float(mensal.loc[pd.Period("2025-01", freq="M")]) == pytest.approx(
        1.001 ** len(de_janeiro) - 1, rel=1e-9
    )


def test_tabela_mensal_fecha_o_ano_com_o_produto_dos_meses():
    r = analytics.retornos_diarios(serie_cotas([0.001] * 300, inicio="2025-01-01"))
    linhas = analytics.tabela_mensal(r)

    primeiro = linhas[0]
    meses_preenchidos = [m for m in primeiro["meses"] if m is not None]
    esperado = float(np.prod([1 + m for m in meses_preenchidos])) - 1
    assert primeiro["acumulado"] == pytest.approx(esperado, abs=1e-6)


def test_consistencia_conta_meses_e_maior_sequencia():
    # 3 meses positivos seguidos, 2 negativos, 1 positivo
    mensais = [0.02, 0.02, 0.02, -0.01, -0.01, 0.03]
    datas = pd.PeriodIndex(
        [f"2025-{m:02d}" for m in range(1, 7)], freq="M"
    ).to_timestamp(how="end").normalize()
    r = pd.Series(mensais, index=datas)

    saida = analytics.consistencia(r)

    assert saida["meses"] == 6
    assert saida["positivos"] == 4
    assert saida["negativos"] == 2
    assert saida["percentual_positivos"] == pytest.approx(4 / 6)
    assert saida["maior_sequencia_positiva"] == 3
    assert saida["maior_sequencia_negativa"] == 2


def test_percentual_acima_do_benchmark_so_conta_meses_comparaveis():
    datas = pd.PeriodIndex(
        [f"2025-{m:02d}" for m in range(1, 5)], freq="M"
    ).to_timestamp(how="end").normalize()
    fundo = pd.Series([0.02, 0.01, 0.03, -0.01], index=datas)
    bench = pd.Series([0.01, 0.01, 0.01, 0.01], index=datas)

    saida = analytics.consistencia(fundo, bench)

    assert saida["acima_benchmark"] == 2       # jan e mar; fev empata, abr perde
    assert saida["meses_comparaveis"] == 4
    assert saida["percentual_acima_benchmark"] == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# Sharpe e benchmark
# --------------------------------------------------------------------------- #

def test_sharpe_usa_excesso_anualizado_sobre_volatilidade():
    rng = np.random.default_rng(7)
    diarios = rng.normal(0.0008, 0.01, 504)
    r = analytics.retornos_diarios(serie_cotas(diarios))
    cdi = pd.Series(0.0002, index=r.index)

    saida = analytics.metricas(r, None, cdi)
    esperado = (
        (saida["retorno_anualizado"] - saida["cdi_anualizado"])
        / saida["volatilidade_anualizada"]
    )
    assert saida["sharpe"] == pytest.approx(esperado, rel=1e-6)


def test_percentual_do_benchmark_e_razao_dos_acumulados():
    r = analytics.retornos_diarios(serie_cotas([0.001] * 300))
    bench = pd.Series(0.0005, index=r.index)

    saida = analytics.metricas(r, bench, bench)
    razao = saida["retorno_acumulado"] / saida["benchmark_acumulado"]

    assert saida["percentual_do_benchmark"] == pytest.approx(razao, rel=1e-9)
    assert saida["excesso_acumulado"] == pytest.approx(
        saida["retorno_acumulado"] - saida["benchmark_acumulado"], abs=1e-9
    )


def test_metricas_sem_benchmark_nao_inventam_comparacao():
    r = analytics.retornos_diarios(serie_cotas([0.001] * 60))
    saida = analytics.metricas(r, None, None)

    assert saida["sharpe"] is None
    assert saida["benchmark_acumulado"] is None
    assert saida["percentual_do_benchmark"] is None


# --------------------------------------------------------------------------- #
# Recortes de periodo
# --------------------------------------------------------------------------- #

def test_recorta_mantem_o_pregao_anterior_a_janela():
    """Sem o pregao anterior, o primeiro dia da janela nao teria retorno e a
    janela de 1 mes perderia justamente o comeco."""
    cotas = serie_cotas([0.001] * 200, inicio="2025-01-01")
    recorte = analytics.recorta(cotas, 1)

    corte = analytics.corte_do_periodo(cotas.index[-1], 1)
    assert recorte.index[0] <= corte
    assert analytics.retornos_diarios(recorte).index[0] > corte


def test_janela_maior_que_o_historico_e_marcada_como_incompleta():
    cotas = serie_cotas([0.001] * 40)  # ~2 meses
    janelas = {j["chave"]: j for j in analytics.retornos_por_janela(cotas)}

    assert janelas["1m"]["disponivel"] is True
    assert janelas["1m"]["completo"] is True
    assert janelas["36m"]["completo"] is False


def test_serie_para_json_preserva_primeiro_e_ultimo_ponto_ao_reduzir():
    r = analytics.retornos_diarios(serie_cotas([0.001] * 3000))
    pontos = analytics.serie_para_json(r, maximo_pontos=200)

    assert len(pontos) <= 201
    assert pontos[0]["data"] == r.index[0].strftime("%Y-%m-%d")
    assert pontos[-1]["data"] == r.index[-1].strftime("%Y-%m-%d")
    # o ultimo valor exibido tem que bater com o indicador do cartao
    assert pontos[-1]["fundo"] == pytest.approx(analytics.acumulado(r), abs=1e-6)
