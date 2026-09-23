"""Categoria do fundo, metricas do ranking por janela e ficha qualitativa.

Tudo sem rede: `categoria` e `perfil` sao funcoes puras sobre o dict do
cadastro, e `_ranking_a_partir_de` recebe DataFrames sinteticos - o mesmo
padrao dos testes de ranking que ja existiam em `test_fundos_metrics.py`.
"""

import pandas as pd
import pytest

from app.fundos import sobre
from app.fundos.cadastro import CATEGORIAS_POR_CHAVE, categoria
from app.fundos.cvm_data import _ranking_a_partir_de


# --------------------------------------------------------------------------- #
# Categoria
# --------------------------------------------------------------------------- #

def test_categoria_usa_o_veiculo_antes_da_classe():
    """FIDC/FIP/FII/ETF se definem pelo tipo de fundo, nao pela classe CVM."""
    assert categoria({"tipo_fundo": "FIDC"}) == "fidc"
    assert categoria({"tipo_fundo": "FIP"}) == "fip"
    assert categoria({"tipo_fundo": "FII"}) == "fii"
    assert categoria({"tipo_fundo": "FIAGRO"}) == "fiagro"
    # FIIM e o "fundo de indice de mercado" da CVM - o ETF do mercado
    assert categoria({"tipo_fundo": "FIIM"}) == "etf"


def test_categoria_previdencia_vence_a_classe_cvm():
    """A CVM classifica "Previdencia RF" como Renda Fixa; para quem escolhe o
    produto, previdencia e outra prateleira."""
    fundo = {
        "tipo_fundo": "FI",
        "classificacao_cvm": "Renda Fixa",
        "classificacao_anbima": "Previdência RF Duração Livre Crédito Liv",
    }
    assert categoria(fundo) == "previdencia"


def test_categoria_cai_para_anbima_quando_a_cvm_nao_classifica():
    fundo = {
        "tipo_fundo": "FI",
        "classificacao_cvm": None,
        "classificacao_anbima": "Multimercados Macro",
    }
    assert categoria(fundo) == "multimercado"


def test_categoria_sem_fonte_nao_chuta():
    assert categoria({"tipo_fundo": None}) is None
    assert categoria({"tipo_fundo": "FI", "classificacao_anbima": None}) is None


def test_todas_as_categorias_tem_rotulo():
    assert all(c["rotulo"] for c in CATEGORIAS_POR_CHAVE.values())


# --------------------------------------------------------------------------- #
# Ranking: metricas na janela e filtro de categoria
# --------------------------------------------------------------------------- #

def _quotas(dados, months):
    return pd.DataFrame(dados, index=months).T[months]


def _snap(cnpjs):
    return pd.DataFrame(
        {"VL_PATRIM_LIQ": [1e8] * len(cnpjs), "NR_COTST": [500] * len(cnpjs)},
        index=cnpjs,
    )


def test_ranking_calcula_volatilidade_e_drawdown_na_janela():
    months = [(2024, m) for m in range(1, 6)]
    # sobe, cai 20% e volta: drawdown maximo tem que sair -20%
    quotas = _quotas({"11.111.111/0001-11": [100.0, 110.0, 88.0, 99.0, 110.0]}, months)
    registry = pd.DataFrame({
        "cnpj_fmt": ["11.111.111/0001-11"],
        "Denominacao_Social": ["Fundo Volátil"],
    })

    saida = _ranking_a_partir_de(quotas, _snap(quotas.index), registry, 100, 80.0, 10)

    assert saida.iloc[0]["retorno_%"] == pytest.approx(10.0)
    assert saida.iloc[0]["drawdown_%"] == pytest.approx(-20.0)
    assert saida.iloc[0]["volatilidade_%"] > 0


def test_ranking_nao_anualiza_sharpe_em_janela_curta():
    """Mesma regra de `analytics.anualizado`: periodo menor que um ano nao e
    extrapolado - o numero seria lido como projecao."""
    months = [(2024, 1), (2024, 2), (2024, 3)]
    quotas = _quotas({"11.111.111/0001-11": [100.0, 103.0, 106.0]}, months)
    registry = pd.DataFrame({
        "cnpj_fmt": ["11.111.111/0001-11"],
        "Denominacao_Social": ["Fundo Novo"],
    })

    saida = _ranking_a_partir_de(
        quotas, _snap(quotas.index), registry, 100, 80.0, 10, cdi_acumulado=0.02
    )

    assert pd.isna(saida.iloc[0]["sharpe"])


def test_ranking_da_sharpe_positivo_quando_o_fundo_bate_o_cdi_em_12_meses():
    months = [(2024, m) for m in range(1, 14)]
    quotas = _quotas({"11.111.111/0001-11": [100.0 * 1.02 ** i for i in range(13)]}, months)
    registry = pd.DataFrame({
        "cnpj_fmt": ["11.111.111/0001-11"],
        "Denominacao_Social": ["Fundo Consistente"],
    })

    saida = _ranking_a_partir_de(
        quotas, _snap(quotas.index), registry, 100, 80.0, 10, cdi_acumulado=0.10
    )

    assert saida.iloc[0]["sharpe"] > 0


def test_ranking_so_devolve_fundos_do_registry_filtrado():
    """O filtro de categoria e aplicado no registry; o merge e inner, entao
    quem ficou de fora nao entra no ranking mesmo tendo o melhor retorno."""
    months = [(2024, 1), (2024, 2)]
    quotas = _quotas(
        {
            "11.111.111/0001-11": [100.0, 130.0],  # melhor retorno, outra categoria
            "22.222.222/0001-22": [100.0, 110.0],
        },
        months,
    )
    registry = pd.DataFrame({
        "cnpj_fmt": ["22.222.222/0001-22"],
        "Denominacao_Social": ["Fundo de Ações"],
        "categoria": ["acoes"],
    })

    saida = _ranking_a_partir_de(quotas, _snap(quotas.index), registry, 100, 80.0, 10)

    assert list(saida["cnpj_fmt"]) == ["22.222.222/0001-22"]
    assert list(saida["categoria"]) == ["acoes"]


# --------------------------------------------------------------------------- #
# Sobre o fundo
# --------------------------------------------------------------------------- #

def test_perfil_traduz_a_classificacao_anbima_em_estrategia():
    fundo = {
        "gestora": "XYZ Asset",
        "tipo_fundo": "FI",
        "classificacao_cvm": "Multimercado",
        "classificacao_anbima": "Multimercados L/S - Direcional",
        "benchmark": "DI de um dia",
        "publico_alvo": "Público Geral",
    }
    saida = sobre.perfil(fundo)

    assert saida["estrategia"] == "Long & Short Direcional"
    assert "compradas e vendidas" in saida["implementacao"]
    assert saida["perfil_risco"] == "Moderado a arrojado"
    assert "XYZ Asset" in saida["resumo"]


def test_perfil_nao_inventa_o_que_a_cvm_nao_publica():
    """Descricao da gestora e nome do gestor de carteira nao existem em
    nenhum arquivo de dados abertos - tem que sair vazio, nao plausivel."""
    saida = sobre.perfil({"gestora": "XYZ Asset", "tipo_fundo": "FI"})

    assert saida["descricao_gestora"] is None
    assert saida["equipe_gestao"] is None
    assert saida["estrategia"] is None  # sem ANBIMA, sem estrategia
    assert saida["classe_ativos"] is None


def test_perfil_de_previdencia_olha_o_mandato_por_baixo_do_veiculo():
    fundo = {
        "tipo_fundo": "FI",
        "classificacao_cvm": "Ações",
        "classificacao_anbima": "Previdência Ações Ativo",
        "previdenciario": "Sim",
    }
    saida = sobre.perfil(fundo)

    assert saida["categoria"] == "previdencia"
    assert saida["classe_ativos"] == "Ações"  # o mandato e de acoes
    assert "aposentadoria" in saida["horizonte"]
    assert "Estrutura previdenciária (PGBL/VGBL)" in saida["caracteristicas"]


def test_perfil_le_o_exterior_do_campo_registral():
    permitido = sobre.perfil({"tipo_fundo": "FI", "cem_por_cento_exterior": "Sim"})
    assert permitido["exterior"].startswith("Sim")

    negado = sobre.perfil({"tipo_fundo": "FI", "cem_por_cento_exterior": "Não"})
    assert negado["exterior"].startswith("Não")

    sem_dado = sobre.perfil({"tipo_fundo": "FI"})
    assert sem_dado["exterior"] is None


def test_perfil_de_cadastro_vazio_e_dicionario_vazio():
    assert sobre.perfil(None) == {}
