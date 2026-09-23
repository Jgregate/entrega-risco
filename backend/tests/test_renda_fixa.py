"""Testes da marcacao a mercado do book de renda fixa.

Tudo com CSV sintetico: nenhum teste toca a rede.
"""

from datetime import date

import pandas as pd
import pytest

from app import titulos_publicos as tp
from app.renda_fixa import ErroRendaFixa, marcar, pesos_por_valor_marcado
from app.schemas import PosicaoRendaFixa
from app.titulos_publicos import parse_csv

CABECALHO = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;"
    "Taxa Venda Manha;PU Compra Manha;PU Venda Manha;PU Base Manha"
)

# Dois papeis com historico curto. O IPCA+ sobe de 3000 para 3300 no periodo;
# o Prefixado cai de 8000 para 7600 — assim ganho e perda aparecem no mesmo book.
LINHAS = [
    # 04/09 e sexta e 07/09 e segunda: o vao do fim de semana serve para testar
    # o recuo do PU quando a data de aquisicao cai em dia sem publicacao
    "Tesouro IPCA+;15/05/2035;04/09/2026;7,60;7,70;2910,00;2900,00;2900,00",
    "Tesouro IPCA+;15/05/2035;07/09/2026;7,50;7,60;3010,00;3000,00;3000,00",
    "Tesouro IPCA+;15/05/2035;08/09/2026;7,40;7,50;3110,00;3100,00;3100,00",
    "Tesouro IPCA+;15/05/2035;09/09/2026;7,30;7,40;3210,00;3200,00;3200,00",
    "Tesouro IPCA+;15/05/2035;10/09/2026;7,20;7,30;3310,00;3300,00;3300,00",
    "Tesouro Prefixado;01/01/2029;04/09/2026;12,90;13,00;8110,00;8100,00;8100,00",
    "Tesouro Prefixado;01/01/2029;07/09/2026;13,00;13,10;8010,00;8000,00;8000,00",
    "Tesouro Prefixado;01/01/2029;08/09/2026;13,20;13,30;7910,00;7900,00;7900,00",
    "Tesouro Prefixado;01/01/2029;09/09/2026;13,40;13,50;7810,00;7800,00;7800,00",
    "Tesouro Prefixado;01/01/2029;10/09/2026;13,60;13,70;7610,00;7600,00;7600,00",
]

HOJE = date(2026, 9, 12)
IPCA = "tesouro_ipca_2035-05-15"
PREFIXADO = "tesouro_prefixado_2029-01-01"


@pytest.fixture
def quadro():
    return parse_csv("\n".join([CABECALHO, *LINHAS]).encode("latin1"))


def posicao(titulo_id=IPCA, quantidade=10, data_aquisicao=None, pu_aquisicao=None):
    return PosicaoRendaFixa(
        titulo_id=titulo_id,
        quantidade=quantidade,
        data_aquisicao=data_aquisicao,
        pu_aquisicao=pu_aquisicao,
    )


def uma(quadro, **kwargs):
    """Marca um book de uma posicao só e devolve a linha."""
    return marcar(quadro, [posicao(**kwargs)], hoje=HOJE)["posicoes"][0]


# --------------------------------------------------------------------------- #
# PU de marcacao
# --------------------------------------------------------------------------- #

def test_marcacao_usa_o_pu_de_venda_e_nao_o_de_compra(quadro):
    """PU Compra e preco de emissao; marcacao e por quanto o Tesouro recompra."""
    linha = uma(quadro, pu_aquisicao=3000.0)
    assert linha["pu_marcacao"] == 3300.00  # PU Venda de 10/09
    assert linha["pu_marcacao"] != 3310.00  # PU Compra de 10/09


def test_marcacao_usa_o_ultimo_dia_util_publicado(quadro):
    linha = uma(quadro, pu_aquisicao=3000.0)
    assert linha["data_base"] == "2026-09-10"


def test_valor_marcado_e_quantidade_vezes_pu_de_marcacao(quadro):
    linha = uma(quadro, quantidade=10, pu_aquisicao=3000.0)
    assert linha["valor_marcado"] == pytest.approx(33_000.00)


def test_quantidade_fracionaria_e_aceita(quadro):
    """O Tesouro Direto vende fracao de titulo."""
    linha = uma(quadro, quantidade=0.5, pu_aquisicao=3000.0)
    assert linha["valor_marcado"] == pytest.approx(1650.00)


# --------------------------------------------------------------------------- #
# P&L
# --------------------------------------------------------------------------- #

def test_pnl_positivo_em_reais_e_percentual(quadro):
    linha = uma(quadro, quantidade=10, pu_aquisicao=3000.0)
    assert linha["valor_aquisicao"] == pytest.approx(30_000.00)
    assert linha["pnl_reais"] == pytest.approx(3_000.00)
    assert linha["pnl_percentual"] == pytest.approx(0.10)


def test_pnl_negativo_quando_o_papel_desvalorizou(quadro):
    linha = uma(quadro, titulo_id=PREFIXADO, quantidade=1, pu_aquisicao=8000.0)
    assert linha["pnl_reais"] == pytest.approx(-400.00)
    assert linha["pnl_percentual"] == pytest.approx(-0.05)


def test_pnl_percentual_independe_da_quantidade(quadro):
    uma_unidade = uma(quadro, quantidade=1, pu_aquisicao=3000.0)
    cem_unidades = uma(quadro, quantidade=100, pu_aquisicao=3000.0)
    assert uma_unidade["pnl_percentual"] == cem_unidades["pnl_percentual"]


# --------------------------------------------------------------------------- #
# PU de aquisicao informado x estimado
# --------------------------------------------------------------------------- #

def test_pu_informado_pelo_usuario_nao_e_marcado_como_estimado(quadro):
    linha = uma(quadro, pu_aquisicao=2500.0)
    assert linha["pu_aquisicao"] == 2500.00
    assert linha["pu_estimado"] is False
    assert linha["data_pu_aquisicao"] is None


def test_sem_pu_informado_cai_para_o_pu_de_venda_da_data_de_aquisicao(quadro):
    linha = uma(quadro, data_aquisicao=date(2026, 9, 8))
    assert linha["pu_aquisicao"] == 3100.00  # PU Venda de 08/09
    assert linha["pu_estimado"] is True
    assert linha["data_pu_aquisicao"] == "2026-09-08"


def test_data_de_aquisicao_sem_pregao_recua_para_o_ultimo_publicado(quadro):
    """06/09/2026 e domingo: recua para sexta (04/09), nao avanca para segunda."""
    linha = uma(quadro, data_aquisicao=date(2026, 9, 6))
    assert linha["data_pu_aquisicao"] == "2026-09-04"
    assert linha["pu_aquisicao"] == 2900.00
    assert linha["pu_estimado"] is True


def test_pu_estimado_registra_a_data_efetivamente_usada(quadro):
    """Aquisicao no dia 09 cai no PU do dia 09; a UI mostra qual data valeu."""
    linha = uma(quadro, data_aquisicao=date(2026, 9, 9))
    assert linha["data_pu_aquisicao"] == "2026-09-09"
    assert linha["pu_aquisicao"] == 3200.00


def test_sem_data_e_sem_pu_a_posicao_nasce_marcada_na_data_base(quadro):
    """Nao havendo referencia de compra, o P&L nasce zerado em vez de inventado."""
    linha = uma(quadro)
    assert linha["data_aquisicao"] == "2026-09-10"
    assert linha["pu_aquisicao"] == linha["pu_marcacao"]
    assert linha["pnl_reais"] == 0.0
    assert linha["pu_estimado"] is True


def test_aquisicao_anterior_ao_primeiro_preco_do_papel_e_recusada(quadro):
    with pytest.raises(ErroRendaFixa, match="so tem preco a partir de"):
        uma(quadro, data_aquisicao=date(2020, 1, 2))


def test_aquisicao_anterior_ao_historico_passa_se_o_pu_for_informado(quadro):
    """Papel recente com compra antiga: informar o PU resolve."""
    linha = uma(quadro, data_aquisicao=date(2020, 1, 2), pu_aquisicao=1500.0)
    assert linha["pu_aquisicao"] == 1500.00
    assert linha["pu_estimado"] is False


# --------------------------------------------------------------------------- #
# Book agregado
# --------------------------------------------------------------------------- #

def test_totais_somam_as_posicoes(quadro):
    book = marcar(
        quadro,
        [
            posicao(IPCA, quantidade=10, pu_aquisicao=3000.0),
            posicao(PREFIXADO, quantidade=1, pu_aquisicao=8000.0),
        ],
        hoje=HOJE,
    )
    totais = book["totais"]

    assert totais["posicoes"] == 2
    assert totais["valor_aquisicao"] == pytest.approx(38_000.00)
    assert totais["valor_marcado"] == pytest.approx(40_600.00)
    assert totais["pnl_reais"] == pytest.approx(2_600.00)
    assert totais["pnl_percentual"] == pytest.approx(2_600.00 / 38_000.00)


def test_peso_sai_do_valor_marcado_e_soma_um(quadro):
    """No book de renda fixa a quantidade e o dado primario; o peso e derivado."""
    book = marcar(
        quadro,
        [
            posicao(IPCA, quantidade=10, pu_aquisicao=3000.0),
            posicao(PREFIXADO, quantidade=1, pu_aquisicao=8000.0),
        ],
        hoje=HOJE,
    )
    pesos = pesos_por_valor_marcado(book)

    assert pesos[IPCA] == pytest.approx(33_000 / 40_600, abs=1e-6)
    assert pesos[PREFIXADO] == pytest.approx(7_600 / 40_600, abs=1e-6)
    assert sum(pesos.values()) == pytest.approx(1.0, abs=1e-6)


def test_totais_sinalizam_quando_algum_pu_foi_estimado(quadro):
    book = marcar(
        quadro,
        [
            posicao(IPCA, quantidade=10, pu_aquisicao=3000.0),
            posicao(PREFIXADO, quantidade=1, data_aquisicao=date(2026, 9, 8)),
        ],
        hoje=HOJE,
    )
    assert book["totais"]["algum_pu_estimado"] is True


def test_book_sai_ordenado_por_tipo_e_vencimento(quadro):
    book = marcar(
        quadro,
        [posicao(PREFIXADO, quantidade=1), posicao(IPCA, quantidade=1)],
        hoje=HOJE,
    )
    assert [l["id"] for l in book["posicoes"]] == [IPCA, PREFIXADO]


# --------------------------------------------------------------------------- #
# Data base explicita
# --------------------------------------------------------------------------- #

def test_book_declara_a_data_base_e_a_defasagem(quadro):
    """A interface precisa dizer que nao e o preco de agora."""
    book = marcar(quadro, [posicao(pu_aquisicao=3000.0)], hoje=HOJE)

    assert book["data_base"] == "2026-09-10"
    assert book["defasagem_dias"] == 2
    assert "10/09/2026" in book["observacao"]


# --------------------------------------------------------------------------- #
# Erros
# --------------------------------------------------------------------------- #

def test_titulo_fora_do_universo_e_recusado(quadro):
    with pytest.raises(ErroRendaFixa, match="nao esta disponivel"):
        uma(quadro, titulo_id="tesouro_selic_2027-03-01")


def test_titulo_ja_vencido_e_recusado(quadro):
    """Em 2030 o Prefixado 2029 ja venceu, mas o IPCA+ 2035 segue de pe."""
    with pytest.raises(ErroRendaFixa, match="nao esta disponivel"):
        marcar(quadro, [posicao(PREFIXADO)], hoje=date(2030, 1, 1))

    assert marcar(quadro, [posicao(IPCA)], hoje=date(2030, 1, 1))["totais"]["posicoes"] == 1


def test_book_sem_nenhum_titulo_disponivel_e_recusado(quadro):
    with pytest.raises(ErroRendaFixa, match="Nao ha titulos disponiveis"):
        marcar(quadro, [posicao(IPCA)], hoje=date(2040, 1, 1))


def test_quantidade_nao_positiva_e_barrada_no_schema():
    with pytest.raises(ValueError):
        PosicaoRendaFixa(titulo_id=IPCA, quantidade=0)


def test_pu_de_aquisicao_nao_positivo_e_barrado_no_schema():
    with pytest.raises(ValueError):
        PosicaoRendaFixa(titulo_id=IPCA, quantidade=1, pu_aquisicao=0)


def test_data_de_aquisicao_no_futuro_e_barrada_no_schema():
    futuro = date.today() + pd.Timedelta(days=1).to_pytimedelta()
    with pytest.raises(ValueError, match="futuro"):
        PosicaoRendaFixa(titulo_id=IPCA, quantidade=1, data_aquisicao=futuro)
