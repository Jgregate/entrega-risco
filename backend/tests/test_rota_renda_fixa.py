"""Testes da rota POST /api/renda-fixa/marcacao. Sem rede."""

import pytest
from fastapi.testclient import TestClient

from app import titulos_publicos as tp
from app.main import app
from app.titulos_publicos import ErroTesouro
from tests.test_renda_fixa import CABECALHO, IPCA, LINHAS, PREFIXADO

ROTA = "/api/renda-fixa/marcacao"


def csv_bytes() -> bytes:
    return "\n".join([CABECALHO, *LINHAS]).encode("latin1")


@pytest.fixture(autouse=True)
def cache_isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "DIRETORIO_CACHE", tmp_path)
    monkeypatch.setattr(tp, "_baixa_bytes", csv_bytes)
    tp.limpar_cache(memoria=True)
    yield
    tp.limpar_cache(memoria=True)


@pytest.fixture
def cliente():
    return TestClient(app)


def test_rota_marca_o_book_e_devolve_o_pnl(cliente):
    resposta = cliente.post(
        ROTA,
        json={
            "posicoes": [
                {"titulo_id": IPCA, "quantidade": 10, "pu_aquisicao": 3000.0},
                {"titulo_id": PREFIXADO, "quantidade": 1, "pu_aquisicao": 8000.0},
            ]
        },
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["totais"]["valor_marcado"] == 40_600.00
    assert corpo["totais"]["pnl_reais"] == 2_600.00


def test_rota_expoe_a_data_base_da_marcacao(cliente):
    corpo = cliente.post(
        ROTA, json={"posicoes": [{"titulo_id": IPCA, "quantidade": 1}]}
    ).json()

    assert corpo["data_base"] == "2026-09-10"
    assert "10/09/2026" in corpo["observacao"]
    assert corpo["fonte"]["data_base"] == "2026-09-10"


def test_rota_entrega_todos_os_campos_da_marcacao(cliente):
    linha = cliente.post(
        ROTA,
        json={"posicoes": [{"titulo_id": IPCA, "quantidade": 10, "pu_aquisicao": 3000.0}]},
    ).json()["posicoes"][0]

    assert set(linha) == {
        "id", "tipo", "tipo_slug", "codigo", "rotulo", "vencimento", "quantidade",
        "data_aquisicao", "pu_aquisicao", "pu_estimado", "data_pu_aquisicao",
        "pu_marcacao", "data_base", "valor_aquisicao", "valor_marcado",
        "pnl_reais", "pnl_percentual", "peso",
    }


def test_rota_sinaliza_pu_estimado(cliente):
    corpo = cliente.post(
        ROTA,
        json={
            "posicoes": [
                {"titulo_id": IPCA, "quantidade": 1, "data_aquisicao": "2026-09-08"}
            ]
        },
    ).json()

    assert corpo["posicoes"][0]["pu_estimado"] is True
    assert corpo["posicoes"][0]["data_pu_aquisicao"] == "2026-09-08"
    assert corpo["totais"]["algum_pu_estimado"] is True


def test_rota_recusa_titulo_fora_do_universo(cliente):
    resposta = cliente.post(
        ROTA, json={"posicoes": [{"titulo_id": "tesouro_selic_2027-03-01", "quantidade": 1}]}
    )

    assert resposta.status_code == 400
    assert "nao esta disponivel" in resposta.json()["detail"]


def test_rota_recusa_titulo_repetido(cliente):
    resposta = cliente.post(
        ROTA,
        json={
            "posicoes": [
                {"titulo_id": IPCA, "quantidade": 1},
                {"titulo_id": IPCA, "quantidade": 2},
            ]
        },
    )

    assert resposta.status_code == 422


def test_rota_recusa_quantidade_zero(cliente):
    resposta = cliente.post(ROTA, json={"posicoes": [{"titulo_id": IPCA, "quantidade": 0}]})
    assert resposta.status_code == 422


def test_rota_recusa_book_vazio(cliente):
    assert cliente.post(ROTA, json={"posicoes": []}).status_code == 422


def test_rota_responde_503_quando_nao_ha_fonte_nem_cache(cliente, monkeypatch):
    def falha():
        raise ErroTesouro("Tesouro Transparente fora do ar")

    monkeypatch.setattr(tp, "_baixa_bytes", falha)
    resposta = cliente.post(ROTA, json={"posicoes": [{"titulo_id": IPCA, "quantidade": 1}]})

    assert resposta.status_code == 503


# --------------------------------------------------------------------------- #
# POST /api/analise/renda-fixa
# --------------------------------------------------------------------------- #

ANALISE = "/api/analise/renda-fixa"


@pytest.fixture
def historico_longo(monkeypatch):
    """600 dias de historico: da para janela de 252 sem aviso."""
    import numpy as np
    import pandas as pd

    datas = pd.bdate_range(end="2026-09-10", periods=600)
    rng = np.random.default_rng(11)
    pus = 3000 * np.cumprod(1 + rng.normal(0.0002, 0.004, 600))
    linhas = [
        f"Tesouro IPCA+;15/05/2035;{d:%d/%m/%Y};7,00;7,10;"
        f"{pu + 10:.2f};{pu:.2f};{pu:.2f}".replace(".", ",")
        for d, pu in zip(datas, pus)
    ]
    monkeypatch.setattr(
        tp, "_baixa_bytes", lambda: "\n".join([CABECALHO, *linhas]).encode("latin1")
    )


def test_analise_devolve_o_mesmo_contrato_da_rota_de_acoes(cliente, historico_longo):
    corpo = cliente.post(
        ANALISE, json={"posicoes": [{"titulo_id": IPCA, "quantidade": 10}], "janela": 252}
    ).json()

    # as abas de metricas nao precisam saber de que classe vieram os numeros
    for chave in ("parametros", "book", "metodos", "ordem_metodos", "estatisticas",
                  "distribuicao", "evolucao", "risco_retorno"):
        assert chave in corpo
    assert set(corpo["metodos"]) == {"empirico", "parametrico", "ewma"}


def test_analise_acrescenta_os_blocos_de_renda_fixa(cliente, historico_longo):
    corpo = cliente.post(
        ANALISE, json={"posicoes": [{"titulo_id": IPCA, "quantidade": 10}], "janela": 252}
    ).json()

    assert corpo["classe"] == "renda-fixa"
    assert corpo["marcacao"]["data_base"] == "2026-09-10"
    assert len(corpo["por_titulo"]) == 1
    assert corpo["avisos"] == []


def test_analise_traz_var_sharpe_e_sortino(cliente, historico_longo):
    corpo = cliente.post(
        ANALISE, json={"posicoes": [{"titulo_id": IPCA, "quantidade": 10}], "janela": 252}
    ).json()

    assert corpo["metodos"]["empirico"]["var_percentual"] > 0
    assert corpo["risco_retorno"]["sharpe"] is not None
    assert corpo["risco_retorno"]["sortino"] is not None
    assert corpo["metodos"]["empirico"]["backtest"]["resumo"]["kupiec"]["p_valor"] is not None


def test_analise_avisa_quando_o_kupiec_fica_sem_poder(cliente, historico_longo):
    """599 retornos com janela de 560 deixam so 39 observacoes de backtest."""
    corpo = cliente.post(
        ANALISE,
        json={"posicoes": [{"titulo_id": IPCA, "quantidade": 1}], "janela": 560},
    ).json()

    aviso = next(a for a in corpo["avisos"] if a["codigo"] == "kupiec_baixa_potencia")
    assert aviso["severidade"] == "aviso"
    assert aviso["detalhe"]["violacoes_esperadas"] < 5.0


def test_analise_avisa_quando_o_kupiec_nao_tem_amostra(cliente, historico_longo):
    """Janela maior que o historico: o backtest nao roda."""
    corpo = cliente.post(
        ANALISE,
        json={"posicoes": [{"titulo_id": IPCA, "quantidade": 1}], "janela": 700},
    ).json()

    aviso = next(a for a in corpo["avisos"] if a["codigo"] == "kupiec_sem_amostra")
    assert aviso["severidade"] == "erro"
    resumo = corpo["metodos"]["empirico"]["backtest"]["resumo"]
    assert resumo["kupiec"]["p_valor"] is None


def test_analise_recusa_book_com_historico_insuficiente(cliente):
    """O fixture padrao tem 5 datas: abaixo do minimo de 30."""
    resposta = cliente.post(
        ANALISE, json={"posicoes": [{"titulo_id": IPCA, "quantidade": 1}]}
    )
    assert resposta.status_code == 400
    assert "mínimo de 30" in resposta.json()["detail"]


def test_analise_valor_da_carteira_e_o_total_marcado(cliente, historico_longo):
    corpo = cliente.post(
        ANALISE, json={"posicoes": [{"titulo_id": IPCA, "quantidade": 10}], "janela": 252}
    ).json()

    assert corpo["parametros"]["valor_carteira"] == corpo["marcacao"]["totais"]["valor_marcado"]
