"""Testes da rastreabilidade do book e da projecao.

Duas invariantes guiam o arquivo, as mesmas que guiam os testes de renda fixa:

    1. NAO HA MOTOR NOVO. O VaR que sustenta o piso da projecao tem que ser
       identicamente o numero que `var_empirico`/`var_parametrico`/`var_ewma`
       produzem sobre a mesma janela. Se divergir, foi escrito motor paralelo.

    2. A JANELA NAO VE O FUTURO. `janela_para_prever` tem que devolver so o que
       e estritamente anterior ao dia projetado.

Tudo com serie sintetica: nenhum teste toca a rede.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app import rastreabilidade as ra
from app import var_empirico, var_ewma, var_parametrico

HOJE = date(2026, 9, 14)


def _passeio(n, inicial, sigma, semente, deriva=0.0004):
    rng = np.random.default_rng(semente)
    return inicial * np.cumprod(1.0 + rng.normal(deriva, sigma, n))


@pytest.fixture
def precos():
    """Dois ativos com 600 pregoes, terminando numa sexta-feira."""
    datas = pd.bdate_range(end="2026-09-11", periods=600)
    return pd.DataFrame(
        {
            "PETR4.SA": _passeio(600, 30.0, 0.02, 1),
            "VALE3.SA": _passeio(600, 60.0, 0.018, 2),
        },
        index=datas,
    )


@pytest.fixture
def serie(precos):
    return precos["PETR4.SA"]


def rastrear(serie, **kwargs):
    base = dict(
        identificador="PETR4.SA",
        rotulo="PETR4.SA",
        classe="acoes",
        quantidade=100.0,
        valor_atual=100.0 * float(serie.iloc[-1]),
        preco_atual=float(serie.iloc[-1]),
        data_preco_atual=serie.index[-1],
    )
    base.update(kwargs)
    return ra.rastrear_posicao(serie, **base)


# --------------------------------------------------------------------------- #
# Janela de estimacao: sem look-ahead
# --------------------------------------------------------------------------- #

def test_janela_nao_inclui_o_dia_que_esta_sendo_previsto(serie):
    retornos = serie.pct_change().dropna()
    alvo = retornos.index[-1]

    janela = ra.janela_para_prever(alvo, retornos, 252)

    assert alvo not in janela.index
    assert janela.index[-1] < alvo


def test_janela_aceita_dia_alvo_que_nao_existe_no_indice(serie):
    """O dia projetado e futuro: cortar por `.iloc[:-1]` descartaria hoje."""
    retornos = serie.pct_change().dropna()
    amanha = retornos.index[-1] + pd.Timedelta(days=3)

    janela = ra.janela_para_prever(amanha, retornos, 252)

    assert janela.index[-1] == retornos.index[-1]
    assert len(janela) == 252


def test_janela_respeita_o_tamanho_pedido(serie):
    retornos = serie.pct_change().dropna()

    assert len(ra.janela_para_prever(retornos.index[-1], retornos, 60)) == 60


# --------------------------------------------------------------------------- #
# Rastreabilidade de uma posicao
# --------------------------------------------------------------------------- #

def test_valorizacao_e_o_retorno_do_preco_entre_compra_e_hoje(serie):
    compra = serie.index[-100]
    linha = rastrear(serie, data_compra=compra.date())

    esperado = float(serie.iloc[-1]) / float(serie.loc[compra]) - 1.0
    assert linha["valorizacao_percentual"] == pytest.approx(esperado, abs=1e-6)


def test_valorizacao_em_reais_e_a_diferenca_dos_dois_valores(serie):
    linha = rastrear(serie, data_compra=serie.index[-100].date())

    assert linha["valorizacao_reais"] == pytest.approx(
        linha["valor_atual"] - linha["valor_compra"], abs=0.01
    )


def test_conta_pregoes_e_dias_corridos_separadamente(serie):
    """Um e o tempo de mercado, o outro e o tempo de calendario; nao sao iguais."""
    compra = serie.index[-101]
    linha = rastrear(serie, data_compra=compra.date())

    assert linha["pregoes"] == 100
    assert linha["dias_corridos"] == (serie.index[-1] - compra).days
    assert linha["dias_corridos"] > linha["pregoes"]


def test_retorno_anualizado_usa_252_pregoes(serie):
    linha = rastrear(serie, data_compra=serie.index[-253].date())

    base = 1.0 + linha["valorizacao_percentual"]
    esperado = base ** (252 / linha["pregoes"]) - 1.0
    assert linha["retorno_anualizado"] == pytest.approx(esperado, abs=1e-6)


def test_nao_anualiza_posse_curta_demais(serie):
    """Uma semana de posse virando '% ao ano' seria numerologia, nao metrica."""
    linha = rastrear(serie, data_compra=serie.index[-5].date())

    assert linha["pregoes"] < ra.MINIMO_PREGOES_ANUALIZAR
    assert linha["retorno_anualizado"] is None
    assert linha["valorizacao_percentual"] is not None


def test_data_de_compra_em_dia_sem_pregao_recua_para_o_anterior(serie):
    """Sabado nao tem preco: `asof` ancora no ultimo pregao conhecido."""
    sextas = [d for d in serie.index[-80:-20] if d.weekday() == 4]
    pregao = sextas[0]
    sabado = pregao + pd.Timedelta(days=1)
    assert sabado.weekday() == 5

    linha = rastrear(serie, data_compra=sabado.date())

    assert linha["data_compra"] == pregao.strftime("%Y-%m-%d")
    assert linha["data_compra_informada"] == sabado.strftime("%Y-%m-%d")
    assert linha["data_compra_recuada"] is True


def test_preco_de_compra_informado_nao_e_estimado(serie):
    linha = rastrear(serie, data_compra=serie.index[-100].date(), preco_compra=25.0)

    assert linha["preco_compra"] == 25.0
    assert linha["preco_compra_estimado"] is False
    assert linha["valor_compra"] == pytest.approx(100.0 * 25.0, abs=0.01)


def test_sem_preco_informado_usa_o_fechamento_da_data_e_marca_como_estimado(serie):
    compra = serie.index[-100]
    linha = rastrear(serie, data_compra=compra.date())

    assert linha["preco_compra"] == pytest.approx(float(serie.loc[compra]), abs=1e-4)
    assert linha["preco_compra_estimado"] is True


def test_sem_data_de_compra_a_posse_cobre_a_serie_inteira(serie):
    """Degrada para o comportamento de hoje em vez de inventar uma referencia."""
    linha = rastrear(serie)

    assert linha["data_compra"] == serie.index[0].strftime("%Y-%m-%d")
    assert linha["data_compra_informada"] is None
    assert linha["data_compra_recuada"] is False
    assert linha["pregoes"] == len(serie) - 1


def test_compra_anterior_ao_inicio_da_serie_ancora_na_primeira_data(serie):
    antes = (serie.index[0] - pd.Timedelta(days=30)).date()
    linha = rastrear(serie, data_compra=antes)

    assert linha["data_compra"] == serie.index[0].strftime("%Y-%m-%d")
    assert linha["data_compra_recuada"] is True


def test_pico_fundo_e_queda_desde_o_pico_do_periodo_de_posse(serie):
    compra = serie.index[-200]
    linha = rastrear(serie, data_compra=compra.date())

    posse = serie.loc[compra:]
    assert linha["pico"]["preco"] == pytest.approx(float(posse.max()), abs=1e-4)
    assert linha["fundo"]["preco"] == pytest.approx(float(posse.min()), abs=1e-4)
    assert linha["queda_desde_o_pico"] == pytest.approx(
        float(serie.iloc[-1]) / float(posse.max()) - 1.0, abs=1e-6
    )
    assert linha["queda_desde_o_pico"] <= 0


def test_evolucao_comeca_na_compra_e_esta_em_reais(serie):
    compra = serie.index[-100]
    linha = rastrear(serie, data_compra=compra.date())

    assert len(linha["evolucao"]) == linha["pregoes"] + 1 == 100
    assert linha["evolucao"][0]["data"] == compra.strftime("%Y-%m-%d")
    assert linha["evolucao"][-1]["valor"] == pytest.approx(linha["valor_atual"], abs=0.01)


# --------------------------------------------------------------------------- #
# Projecao: o mesmo motor de VaR, levado adiante
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "modulo", [var_empirico, var_parametrico, var_ewma], ids=lambda m: m.NOME
)
def test_var_da_projecao_e_identico_ao_do_modulo_original(serie, modulo):
    """Sem motor paralelo: o numero tem que bater com o modulo `var_*`."""
    retornos = serie.pct_change().dropna()
    projecao = ra.projetar(retornos, 100_000.0, 0.95, horizonte=21, janela=252)

    janela = ra.janela_para_prever(
        ra._dias_uteis_a_frente(retornos.index[-1], 21)[0], retornos, 252
    )
    esperado = modulo.pontual(janela, 0.95, 21)

    assert projecao["metodos"][modulo.NOME]["var_percentual"] == pytest.approx(
        round(esperado["var"], 6), abs=1e-9
    )


def test_valor_esperado_compoe_a_deriva_no_horizonte(serie):
    retornos = serie.pct_change().dropna()
    projecao = ra.projetar(retornos, 100_000.0, 0.95, horizonte=21, janela=252)

    deriva = projecao["deriva_diaria"]
    assert projecao["valor_esperado"] == pytest.approx(
        100_000.0 * (1.0 + deriva) ** 21, abs=1.0
    )


def test_piso_e_o_esperado_menos_o_var_em_reais(serie):
    retornos = serie.pct_change().dropna()
    projecao = ra.projetar(retornos, 100_000.0, 0.95, horizonte=21, janela=252)

    for bloco in projecao["metodos"].values():
        assert bloco["var_monetario"] > 0  # serie com risco: VaR positivo
        assert bloco["piso"] == pytest.approx(
            projecao["valor_esperado"] - bloco["var_monetario"], abs=0.02
        )
        assert bloco["teto"] == pytest.approx(
            projecao["valor_esperado"] + bloco["var_monetario"], abs=0.02
        )


def test_projecao_parte_da_ultima_observacao_e_mira_dias_uteis(serie):
    retornos = serie.pct_change().dropna()
    projecao = ra.projetar(retornos, 100_000.0, 0.95, horizonte=21, janela=252)

    assert projecao["data_partida"] == retornos.index[-1].strftime("%Y-%m-%d")
    alvo = pd.Timestamp(projecao["data_alvo"])
    assert alvo > retornos.index[-1]
    assert alvo.weekday() < 5


def test_trajetoria_fecha_no_piso_e_no_teto_do_metodo_do_cone(serie):
    retornos = serie.pct_change().dropna()
    projecao = ra.projetar(retornos, 100_000.0, 0.95, horizonte=21, janela=252)

    cone = projecao["metodos"][projecao["metodo_do_cone"]]
    ultimo = projecao["trajetoria"][-1]
    assert ultimo["passo"] == 21
    assert ultimo["piso"] == pytest.approx(cone["piso"], abs=0.02)
    assert ultimo["teto"] == pytest.approx(cone["teto"], abs=0.02)


def test_trajetoria_alarga_com_o_tempo(serie):
    """Raiz do tempo: a incerteza de 20 dias e maior que a de 1 dia."""
    retornos = serie.pct_change().dropna()
    traj = ra.projetar(retornos, 100_000.0, 0.95, horizonte=21, janela=252)["trajetoria"]

    larguras = [p["teto"] - p["piso"] for p in traj]
    assert larguras == sorted(larguras)
    assert larguras[-1] > larguras[0]


def test_trajetoria_longa_e_amostrada_para_nao_inflar_o_payload(serie):
    retornos = serie.pct_change().dropna()
    traj = ra.projetar(retornos, 100_000.0, 0.95, horizonte=252, janela=252)["trajetoria"]

    assert len(traj) <= ra.MAXIMO_PONTOS_TRAJETORIA + 1
    assert traj[-1]["passo"] == 252


def test_var_negativo_nao_inverte_o_intervalo(serie):
    """Numa LFT o percentil de 5% e ganho, e o VaR sai negativo — acontece de verdade.

    O intervalo tem que continuar com piso <= esperado <= teto, e o flag tem
    que dizer que naquela confianca nao ha perda.
    """
    so_sobe = pd.Series(
        1000.0 * np.cumprod(np.full(300, 1.0004)), index=serie.index[-300:]
    ).pct_change().dropna()

    projecao = ra.projetar(so_sobe, 100_000.0, 0.95, horizonte=21, janela=252)

    empirico = projecao["metodos"]["empirico"]
    assert empirico["var_percentual"] < 0
    assert empirico["sem_perda_na_confianca"] is True
    assert empirico["piso"] <= empirico["teto"]


def test_cone_com_var_negativo_tambem_fica_na_ordem(serie):
    so_sobe = pd.Series(
        1000.0 * np.cumprod(np.full(300, 1.0004)), index=serie.index[-300:]
    ).pct_change().dropna()

    traj = ra.projetar(so_sobe, 100_000.0, 0.95, horizonte=21, janela=252)["trajetoria"]

    assert all(p["piso"] <= p["teto"] for p in traj)


def test_var_positivo_nao_levanta_o_flag(serie):
    projecao = ra.projetar(
        serie.pct_change().dropna(), 100_000.0, 0.95, horizonte=21, janela=252
    )

    assert all(
        m["sem_perda_na_confianca"] is False for m in projecao["metodos"].values()
    )


def test_projecao_sem_amostra_sai_indisponivel_com_motivo(serie):
    retornos = serie.pct_change().dropna().tail(10)

    projecao = ra.projetar(retornos, 100_000.0, 0.95, horizonte=21, janela=252)

    assert projecao["disponivel"] is False
    assert str(ra.MINIMO_OBSERVACOES_PROJETAR) in projecao["observacao"]
    assert projecao["confiabilidade"]["nivel"] == "CRITICA"


# --------------------------------------------------------------------------- #
# Confiabilidade: o numero sai sempre, o nivel diz o quanto confiar
# --------------------------------------------------------------------------- #

def test_janela_cheia_e_saudavel_e_nao_emite_motivo(serie):
    """Aviso permanente vira papel de parede: SAUDAVEL nao avisa nada."""
    janela = serie.pct_change().dropna().tail(252)

    saude = ra.confiabilidade(janela)

    assert saude["nivel"] == "SAUDAVEL"
    assert saude["motivos"] == []


@pytest.mark.parametrize(
    "observacoes, nivel",
    [(252, "SAUDAVEL"), (130, "REDUZIDA"), (70, "BAIXA"), (40, "CRITICA")],
)
def test_nivel_degrada_conforme_a_janela_encurta(serie, observacoes, nivel):
    janela = serie.pct_change().dropna().tail(observacoes)

    assert ra.confiabilidade(janela)["nivel"] == nivel


def test_janela_curta_nomeia_o_tamanho_no_motivo(serie):
    saude = ra.confiabilidade(serie.pct_change().dropna().tail(70))

    assert saude["nivel"] == "BAIXA"
    assert "70 observações" in saude["motivos"][0]


def test_serie_sem_volatilidade_rebaixa_um_degrau_e_explica(serie):
    """Marcacao na curva: vol perto de zero estreita o intervalo artificialmente."""
    plana = pd.Series(
        1000.0 * np.cumprod(np.full(300, 1.00001)), index=serie.index[-300:]
    ).pct_change().dropna()

    saude = ra.confiabilidade(plana)

    assert saude["nivel"] == "REDUZIDA"  # rebaixado de SAUDAVEL
    assert any("volatilidade anualizada" in m for m in saude["motivos"])


def test_ultima_observacao_velha_rebaixa_e_explica(serie):
    janela = serie.pct_change().dropna().tail(252)

    saude = ra.confiabilidade(janela, hoje=date(2026, 12, 25))

    assert saude["nivel"] == "REDUZIDA"
    assert any("última observação" in m for m in saude["motivos"])


def test_um_rebaixamento_so_mesmo_com_dois_gatilhos(serie):
    """Os motivos se acumulam; o degrau perdido e um so."""
    plana = pd.Series(
        1000.0 * np.cumprod(np.full(300, 1.00001)), index=serie.index[-300:]
    ).pct_change().dropna()

    saude = ra.confiabilidade(plana, hoje=date(2026, 12, 25))

    assert len(saude["motivos"]) == 2
    assert saude["nivel"] == "REDUZIDA"


# --------------------------------------------------------------------------- #
# Book inteiro
# --------------------------------------------------------------------------- #

def itens(precos, **por_ticker):
    saida = []
    for ticker, extra in por_ticker.items():
        preco = float(precos[ticker].iloc[-1])
        valor = extra.pop("valor_atual", 50_000.0)
        saida.append(
            {
                "id": ticker,
                "rotulo": ticker,
                "classe": "acoes",
                "peso": extra.pop("peso", 0.5),
                "preco_atual": preco,
                "valor_atual": valor,
                "quantidade": valor / preco,
                **extra,
            }
        )
    return saida


def test_totais_somam_as_posicoes(precos):
    book = ra.rastrear_book(
        precos,
        itens(precos, **{"PETR4.SA": {}, "VALE3.SA": {}}),
        confianca=0.95,
        horizonte_projecao=21,
        janela=252,
    )

    totais = book["totais"]
    assert totais["posicoes"] == 2
    assert totais["valor_atual"] == pytest.approx(100_000.0, abs=0.02)
    assert totais["valorizacao_reais"] == pytest.approx(
        sum(p["valorizacao_reais"] for p in book["posicoes"]), abs=0.02
    )


def test_totais_contam_ganhadoras_e_perdedoras(precos):
    book = ra.rastrear_book(
        precos,
        itens(precos, **{"PETR4.SA": {}, "VALE3.SA": {}}),
        confianca=0.95,
        horizonte_projecao=21,
        janela=252,
    )

    totais = book["totais"]
    assert totais["ganhadoras"] + totais["perdedoras"] <= totais["posicoes"]


def test_posicoes_saem_ordenadas_por_valor(precos):
    book = ra.rastrear_book(
        precos,
        itens(
            precos,
            **{"PETR4.SA": {"valor_atual": 20_000.0}, "VALE3.SA": {"valor_atual": 80_000.0}},
        ),
        confianca=0.95,
        horizonte_projecao=21,
        janela=252,
    )

    assert [p["id"] for p in book["posicoes"]] == ["VALE3.SA", "PETR4.SA"]


def test_projecao_do_book_usa_o_retorno_da_carteira_nos_pesos(precos):
    """O piso projetado tem que ser o do book, nao a soma dos pisos por posicao."""
    pesos = {"PETR4.SA": 0.6, "VALE3.SA": 0.4}
    book = ra.rastrear_book(
        precos,
        itens(
            precos,
            **{"PETR4.SA": {"valor_atual": 60_000.0, "peso": 0.6},
               "VALE3.SA": {"valor_atual": 40_000.0, "peso": 0.4}},
        ),
        confianca=0.95,
        horizonte_projecao=21,
        janela=252,
        pesos=pesos,
    )

    projecao = book["projecao"]
    assert projecao["disponivel"] is True
    assert projecao["valor_atual"] == pytest.approx(100_000.0, abs=0.02)

    soma_dos_pisos = sum(
        p["projecao"]["metodos"]["empirico"]["var_monetario"] for p in book["posicoes"]
    )
    # diversificacao: o VaR do book e menor que a soma dos VaRs isolados
    assert projecao["metodos"]["empirico"]["var_monetario"] < soma_dos_pisos


def test_sem_pesos_nao_ha_projecao_agregada(precos):
    book = ra.rastrear_book(
        precos,
        itens(precos, **{"PETR4.SA": {}}),
        confianca=0.95,
        horizonte_projecao=21,
        janela=252,
    )

    assert book["projecao"] is None
    assert book["posicoes"][0]["projecao"]["disponivel"] is True


def test_evolucao_do_book_conta_posicoes_vivas_em_cada_data(precos):
    """Salto na curva e entrada de posicao, nao valorizacao — e precisa dar para ver."""
    antiga = precos.index[-300].date()
    nova = precos.index[-50].date()
    book = ra.rastrear_book(
        precos,
        itens(
            precos,
            **{"PETR4.SA": {"data_compra": antiga}, "VALE3.SA": {"data_compra": nova}},
        ),
        confianca=0.95,
        horizonte_projecao=21,
        janela=252,
    )

    curva = book["evolucao"]
    assert curva[0]["posicoes"] == 1
    assert curva[-1]["posicoes"] == 2
    assert len(curva) == 300


def test_aviso_quando_a_compra_e_anterior_a_serie(precos):
    antes = (precos.index[0] - pd.Timedelta(days=60)).date()
    book = ra.rastrear_book(
        precos,
        itens(precos, **{"PETR4.SA": {"data_compra": antes}}),
        confianca=0.95,
        horizonte_projecao=21,
        janela=252,
    )

    codigos = [a["codigo"] for a in book["avisos"]]
    assert "compra_fora_do_periodo" in codigos


def test_aviso_quando_o_preco_de_compra_foi_estimado(precos):
    book = ra.rastrear_book(
        precos,
        itens(precos, **{"PETR4.SA": {"data_compra": precos.index[-100].date()}}),
        confianca=0.95,
        horizonte_projecao=21,
        janela=252,
    )

    codigos = [a["codigo"] for a in book["avisos"]]
    assert "preco_compra_estimado" in codigos


def test_sem_aviso_quando_tudo_foi_informado(precos):
    book = ra.rastrear_book(
        precos,
        itens(
            precos,
            **{"PETR4.SA": {"data_compra": precos.index[-100].date(), "preco_compra": 28.0}},
        ),
        confianca=0.95,
        horizonte_projecao=21,
        janela=252,
    )

    assert book["avisos"] == []
