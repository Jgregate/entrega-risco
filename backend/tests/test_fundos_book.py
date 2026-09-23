"""Testes da consolidacao do book.

O foco esta nas tres decisoes que definem o significado dos numeros da tela:
rentabilidade time-weighted, contribuicao de retorno e contribuicao de risco.
Tudo com series sinteticas, sem rede.
"""

import math

import numpy as np
import pandas as pd
import pytest

from app.fundos import analytics, book


def serie_cotas(retornos, inicio="2025-01-01", cota_inicial=100.0):
    datas = pd.bdate_range(inicio, periods=len(retornos) + 1)
    cotas = [cota_inicial]
    for r in retornos:
        cotas.append(cotas[-1] * (1 + r))
    return pd.Series(cotas, index=datas)


# --------------------------------------------------------------------------- #
# Posicao
# --------------------------------------------------------------------------- #

def test_valor_investido_com_data_de_entrada_vira_quantidade_de_cotas():
    cotas = serie_cotas([0.0] * 10)  # cota constante em 100
    pos = book.resolve_posicao(
        {"valor_investido": 5000.0, "data_entrada": cotas.index[3].date().isoformat()},
        cotas,
    )

    assert pos["quantidade_cotas"] == pytest.approx(50.0)
    assert pos["preco_medio"] == pytest.approx(100.0)
    assert pos["valor_atual"] == pytest.approx(5000.0)
    assert pos["resultado"] == pytest.approx(0.0)


def test_quantidade_informada_tem_precedencia_sobre_valor():
    cotas = serie_cotas([0.10])  # 100 -> 110
    pos = book.resolve_posicao(
        {
            "quantidade_cotas": 10.0,
            "valor_investido": 999999.0,
            "preco_medio": 100.0,
        },
        cotas,
    )

    assert pos["quantidade_cotas"] == pytest.approx(10.0)
    assert pos["valor_atual"] == pytest.approx(1100.0)
    assert pos["resultado"] == pytest.approx(100.0)
    assert pos["rentabilidade"] == pytest.approx(0.10)


def test_sem_preco_medio_nao_ha_resultado_financeiro_inventado():
    """So o valor atual, sem data de entrada: nao da para saber o custo, e o
    contrato e devolver None em vez de supor."""
    cotas = serie_cotas([0.10])
    pos = book.resolve_posicao({"valor_investido": 1100.0}, cotas)

    assert pos["valor_atual"] == pytest.approx(1100.0)
    assert pos["preco_medio"] is None
    assert pos["resultado"] is None
    assert pos["valor_investido"] is None


def test_posicao_sem_quantidade_nem_valor_e_rejeitada():
    assert book.resolve_posicao({}, serie_cotas([0.01])) is None


# --------------------------------------------------------------------------- #
# Curva time-weighted
# --------------------------------------------------------------------------- #

def test_aporte_novo_nao_vira_rentabilidade():
    """O ponto central do TWR: por um fundo novo no book aumenta o patrimonio,
    nao a rentabilidade daquele dia."""
    cotas_a = serie_cotas([0.0] * 10)
    cotas_b = serie_cotas([0.0] * 10)
    entrada_b = cotas_b.index[5].strftime("%Y-%m-%d")

    posicoes = [
        {"cnpj": "A", "quantidade_cotas": 10.0, "data_entrada": None},
        {"cnpj": "B", "quantidade_cotas": 1000.0, "data_entrada": entrada_b},
    ]
    retornos, _ = book.curva_do_book(posicoes, {"A": cotas_a, "B": cotas_b})

    # nenhuma cota se moveu: o retorno do book tem que ser zero em todo dia,
    # inclusive no dia em que B entrou com 100x o patrimonio de A
    assert np.allclose(retornos.to_numpy(), 0.0, atol=1e-12)


def test_retorno_do_book_com_um_fundo_so_e_o_retorno_do_fundo():
    cotas = serie_cotas([0.01, -0.02, 0.03])
    posicoes = [{"cnpj": "A", "quantidade_cotas": 7.0, "data_entrada": None}]

    retornos, pesos = book.curva_do_book(posicoes, {"A": cotas})

    assert retornos.to_numpy() == pytest.approx([0.01, -0.02, 0.03], abs=1e-12)
    assert np.allclose(pesos["A"].to_numpy(), 1.0)


def test_book_meio_a_meio_rende_a_media_dos_dois_fundos():
    cotas_a = serie_cotas([0.02])
    cotas_b = serie_cotas([0.00])
    posicoes = [
        {"cnpj": "A", "quantidade_cotas": 1.0, "data_entrada": None},
        {"cnpj": "B", "quantidade_cotas": 1.0, "data_entrada": None},
    ]

    retornos, _ = book.curva_do_book(posicoes, {"A": cotas_a, "B": cotas_b})

    assert float(retornos.iloc[0]) == pytest.approx(0.01, abs=1e-12)


# --------------------------------------------------------------------------- #
# Contribuicoes
# --------------------------------------------------------------------------- #

def test_contribuicoes_de_retorno_somam_o_retorno_a_menos_da_capitalizacao():
    cotas_a = serie_cotas([0.01, 0.02, -0.01])
    cotas_b = serie_cotas([0.00, 0.01, 0.02])
    posicoes = [
        {"cnpj": "A", "quantidade_cotas": 1.0, "data_entrada": None},
        {"cnpj": "B", "quantidade_cotas": 1.0, "data_entrada": None},
    ]
    series = {"A": cotas_a, "B": cotas_b}

    retornos, pesos = book.curva_do_book(posicoes, series)
    retornos_fundos = pd.DataFrame(
        {k: analytics.retornos_diarios(v).reindex(retornos.index) for k, v in series.items()}
    )
    total = analytics.acumulado(retornos)
    saida = book.contribuicao_retorno(pesos, retornos_fundos, total)

    assert saida["soma"] == pytest.approx(sum(i["contribuicao"] for i in saida["itens"]))
    # o residuo e o efeito de capitalizacao, e e explicitado em vez de rateado
    assert saida["residuo_capitalizacao"] == pytest.approx(total - saida["soma"], abs=1e-9)
    assert abs(saida["residuo_capitalizacao"]) < 0.01


def test_contribuicoes_de_risco_somam_exatamente_a_volatilidade():
    """A MCTR existe justamente por isso: a soma FECHA na vol da carteira."""
    rng = np.random.default_rng(3)
    retornos_fundos = pd.DataFrame(
        {
            "A": rng.normal(0, 0.01, 400),
            "B": rng.normal(0, 0.02, 400),
            "C": rng.normal(0, 0.005, 400),
        },
        index=pd.bdate_range("2024-01-01", periods=400),
    )
    pesos = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})

    saida = book.contribuicao_risco(pesos, retornos_fundos)
    soma = sum(i["contribuicao"] for i in saida["itens"])

    assert soma == pytest.approx(saida["volatilidade"], rel=1e-9)
    assert sum(i["participacao"] for i in saida["itens"]) == pytest.approx(1.0, rel=1e-9)


def test_fundo_descorrelacionado_contribui_menos_que_sua_vol_isolada():
    """Duas posicoes de mesma vol e peso: a que anda na contramao carrega menos
    risco para a carteira do que sua volatilidade individual sugere."""
    n = 600
    rng = np.random.default_rng(11)
    base = rng.normal(0, 0.01, n)
    idx = pd.bdate_range("2024-01-01", periods=n)
    retornos_fundos = pd.DataFrame(
        {"junto": base, "contra": -base}, index=idx
    )
    pesos = pd.Series({"junto": 0.5, "contra": 0.5})

    saida = book.contribuicao_risco(pesos, retornos_fundos)

    # carteira perfeitamente hedgeada: volatilidade praticamente nula
    assert saida["volatilidade"] == pytest.approx(0.0, abs=1e-9)
    assert saida["correlacao"]["valores"][0][1] == pytest.approx(-1.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# Agregacoes, custos e tributacao
# --------------------------------------------------------------------------- #

def test_classe_do_fundo_prioriza_previdencia_e_exterior():
    assert book.classe_do_fundo({"previdenciario": "Sim", "classificacao_cvm": "Ações"}) \
        == "Previdência"
    assert book.classe_do_fundo({"classificacao_anbima": "Ações Invest. no Exterior"}) \
        == "Internacional"
    assert book.classe_do_fundo({"classificacao_cvm": "Renda Fixa"}) == "Renda Fixa"
    assert book.classe_do_fundo({"classificacao_cvm": "Multimercado"}) == "Multimercado"
    assert book.classe_do_fundo(None) == "Outros"
    assert book.classe_do_fundo({}) == "Outros"


def test_faixa_de_liquidez_usa_o_primeiro_teto_que_cabe():
    assert book.faixa_liquidez(0) == "D+0"
    assert book.faixa_liquidez(3) == "D+5"
    assert book.faixa_liquidez(91) == "Acima de D+90"
    assert book.faixa_liquidez(None) == "Não informado"


def test_custo_so_conta_fundos_com_taxa_e_declara_a_cobertura():
    itens = [
        {"cnpj": "A", "valor_atual": 80.0, "taxa_administracao": 2.0},
        {"cnpj": "B", "valor_atual": 20.0, "taxa_administracao": None},
    ]
    saida = book.custos(itens, 100.0)

    assert saida["custo_administracao_ano"] == pytest.approx(1.6)
    assert saida["cobertura"] == pytest.approx(0.8)
    assert saida["fundos_sem_taxa"] == 1


def test_ir_segue_a_tabela_regressiva_pelo_prazo_informado():
    from datetime import date

    def item(dias, classe="Multimercado", ganho=1000.0):
        entrada = date(2026, 1, 1)
        return {
            "cnpj": "A", "classe": classe, "valor_atual": 10000.0,
            "resultado": ganho, "data_entrada": entrada.isoformat(),
            "tributacao_longo_prazo": "Sim",
        }, date(2026, 1, 1) + pd.Timedelta(days=dias).to_pytimedelta()

    for dias, aliquota in ((100, 0.225), (300, 0.20), (500, 0.175), (900, 0.15)):
        i, hoje = item(dias)
        saida = book.tributacao([i], hoje)
        assert saida["ir_estimado"] == pytest.approx(1000.0 * aliquota)


def test_fundo_de_acoes_tem_aliquota_unica_de_15():
    from datetime import date

    i = {
        "cnpj": "A", "classe": "Renda Variável", "valor_atual": 10000.0,
        "resultado": 1000.0, "data_entrada": "2026-01-01",
        "tributacao_longo_prazo": None,
    }
    saida = book.tributacao([i], date(2026, 2, 1))

    assert saida["ir_estimado"] == pytest.approx(150.0)


def test_posicao_sem_data_de_entrada_fica_fora_da_estimativa_de_ir():
    from datetime import date

    itens = [
        {"cnpj": "A", "classe": "Multimercado", "valor_atual": 100.0,
         "resultado": 10.0, "data_entrada": None, "tributacao_longo_prazo": "Sim"},
    ]
    saida = book.tributacao(itens, date(2026, 6, 1))

    assert saida["ir_estimado"] is None
    assert saida["fundos_sem_estimativa"] == 1
    assert saida["cobertura"] == pytest.approx(0.0)


def test_concentracao_hhi_reconhece_carteira_concentrada():
    espalhada = book.concentracao([25.0, 25.0, 25.0, 25.0], 100.0)
    concentrada = book.concentracao([90.0, 10.0], 100.0)

    assert espalhada["hhi"] == pytest.approx(0.25)
    assert concentrada["hhi"] == pytest.approx(0.82)
    assert concentrada["maior"] == pytest.approx(0.9)


def test_agrupa_soma_valores_e_conta_fundos_por_grupo():
    itens = [
        {"gestora": "X", "valor_atual": 60.0},
        {"gestora": "X", "valor_atual": 20.0},
        {"gestora": None, "valor_atual": 20.0},
    ]
    grupos = {g["nome"]: g for g in book.agrupa(itens, "gestora", 100.0)}

    assert grupos["X"]["valor"] == pytest.approx(80.0)
    assert grupos["X"]["fundos"] == 2
    assert grupos["X"]["percentual"] == pytest.approx(0.8)
    assert "Não informado" in grupos
