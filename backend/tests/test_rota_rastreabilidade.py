"""Testes das rotas de analise com o bloco de rastreabilidade.

As tres classes — acoes, renda fixa e ambos — tem que devolver o MESMO
contrato de rastreabilidade, para o front nao precisar saber de que book o
payload veio. E o que estes testes fixam.

Nenhum teste toca a rede: o yfinance, o BCB e o arquivo do Tesouro sao todos
substituidos.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import main
from app import titulos_publicos as tp
from app.main import app

DATAS = pd.bdate_range(end="2026-09-10", periods=600)
IPCA = "tesouro_ipca_2035-05-15"
PREFIXADO = "tesouro_prefixado_2029-01-01"

CABECALHO = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;"
    "Taxa Venda Manha;PU Compra Manha;PU Venda Manha;PU Base Manha"
)


def _passeio(n, inicial, sigma, semente):
    rng = np.random.default_rng(semente)
    return inicial * np.cumprod(1.0 + rng.normal(0.0002, sigma, n))


def _linhas(tipo, vencimento, datas, pus):
    return [
        f"{tipo};{vencimento};{d:%d/%m/%Y};7,00;7,10;"
        f"{pu + 10:.2f};{pu:.2f};{pu:.2f}".replace(".", ",")
        for d, pu in zip(datas, pus)
    ]


def csv_bytes() -> bytes:
    linhas = [
        *_linhas("Tesouro IPCA+", "15/05/2035", DATAS, _passeio(600, 3000, 0.004, 1)),
        *_linhas("Tesouro Prefixado", "01/01/2029", DATAS, _passeio(600, 750, 0.003, 2)),
    ]
    return "\n".join([CABECALHO, *linhas]).encode("latin1")


PRECOS = pd.DataFrame(
    {
        "PETR4.SA": _passeio(600, 30.0, 0.02, 3),
        "VALE3.SA": _passeio(600, 60.0, 0.018, 4),
    },
    index=DATAS,
)


@pytest.fixture(autouse=True)
def sem_rede(tmp_path, monkeypatch):
    """Tesouro, yfinance e BCB substituidos por dados sinteticos."""
    monkeypatch.setattr(tp, "DIRETORIO_CACHE", tmp_path)
    monkeypatch.setattr(tp, "_baixa_bytes", csv_bytes)
    tp.limpar_cache(memoria=True)

    def precos(tickers, inicio=None, fim=None):
        return PRECOS[list(tickers)].copy()

    monkeypatch.setattr(main, "baixar_precos", precos)
    monkeypatch.setattr(
        main,
        "serie_selic",
        lambda inicio, fim: pd.Series(0.0004, index=DATAS, name="selic"),
    )
    yield
    tp.limpar_cache(memoria=True)


@pytest.fixture
def cliente():
    return TestClient(app)


CAMPOS_DA_POSICAO = {
    "id", "rotulo", "classe", "quantidade", "peso", "data_compra",
    "data_compra_informada", "data_compra_recuada", "preco_compra",
    "preco_compra_estimado", "preco_atual", "data_preco_atual", "dias_corridos",
    "pregoes", "valor_compra", "valor_atual", "valorizacao_reais",
    "valorizacao_percentual", "retorno_anualizado", "pico", "fundo",
    "queda_desde_o_pico", "evolucao", "projecao",
}


def pedido_acoes(**extra):
    base = {
        "posicoes": [
            {"ticker": "PETR4.SA", "peso": 60, "data_compra": "2025-09-10"},
            {"ticker": "VALE3.SA", "peso": 40, "data_compra": "2026-03-10",
             "preco_compra": 55.0},
        ],
        "inicio": "2024-06-01",
        "fim": "2026-09-10",
        "valor_carteira": 100_000,
    }
    base.update(extra)
    return base


def pedido_renda_fixa(**extra):
    base = {
        "posicoes": [
            {"titulo_id": IPCA, "quantidade": 10, "data_aquisicao": "2025-09-10",
             "pu_aquisicao": 3000.0},
            {"titulo_id": PREFIXADO, "quantidade": 5, "data_aquisicao": "2026-03-10"},
        ]
    }
    base.update(extra)
    return base


def pedido_consolidado(**extra):
    base = {
        "acoes": [{"ticker": "PETR4.SA", "peso": 100, "data_compra": "2025-09-10"}],
        "renda_fixa": [
            {"titulo_id": IPCA, "quantidade": 10, "data_aquisicao": "2025-09-10",
             "pu_aquisicao": 3000.0}
        ],
        "valor_carteira": 50_000,
    }
    base.update(extra)
    return base


# --------------------------------------------------------------------------- #
# O contrato e o mesmo nas tres classes
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "rota, corpo",
    [
        ("/api/analise", pedido_acoes()),
        ("/api/analise/renda-fixa", pedido_renda_fixa()),
        ("/api/analise/consolidado", pedido_consolidado()),
    ],
    ids=["acoes", "renda-fixa", "ambos"],
)
def test_as_tres_rotas_devolvem_o_mesmo_contrato(cliente, rota, corpo):
    resposta = cliente.post(rota, json=corpo)
    assert resposta.status_code == 200, resposta.text

    rast = resposta.json()["rastreabilidade"]
    assert set(rast) == {
        "hoje", "data_referencia", "confianca", "horizonte_projecao",
        "posicoes", "totais", "evolucao", "projecao", "avisos",
    }
    assert rast["posicoes"]
    for posicao in rast["posicoes"]:
        # `detalhe` e opcional: so a renda fixa tem papel e vencimento a declarar
        assert set(posicao) - {"detalhe"} == CAMPOS_DA_POSICAO


@pytest.mark.parametrize(
    "rota, corpo",
    [
        ("/api/analise", pedido_acoes()),
        ("/api/analise/renda-fixa", pedido_renda_fixa()),
        ("/api/analise/consolidado", pedido_consolidado()),
    ],
    ids=["acoes", "renda-fixa", "ambos"],
)
def test_as_tres_rotas_projetam_o_book(cliente, rota, corpo):
    projecao = cliente.post(rota, json=corpo).json()["rastreabilidade"]["projecao"]

    assert projecao["disponivel"] is True
    assert projecao["horizonte_pregoes"] == 21
    assert set(projecao["metodos"]) == {"empirico", "parametrico", "ewma"}
    assert projecao["trajetoria"]
    assert projecao["confiabilidade"]["nivel"] in {
        "CRITICA", "BAIXA", "REDUZIDA", "SAUDAVEL"
    }


def test_horizonte_de_projecao_e_configuravel(cliente):
    corpo = cliente.post(
        "/api/analise", json=pedido_acoes(horizonte_projecao=63)
    ).json()

    projecao = corpo["rastreabilidade"]["projecao"]
    assert projecao["horizonte_pregoes"] == 63
    assert corpo["rastreabilidade"]["horizonte_projecao"] == 63


def test_horizonte_de_projecao_e_independente_do_horizonte_do_var(cliente):
    corpo = cliente.post(
        "/api/analise", json=pedido_acoes(horizonte=1, horizonte_projecao=42)
    ).json()

    assert corpo["parametros"]["horizonte_dias"] == 1
    assert corpo["rastreabilidade"]["projecao"]["horizonte_pregoes"] == 42


# --------------------------------------------------------------------------- #
# Acoes
# --------------------------------------------------------------------------- #

def test_acoes_rastreiam_a_data_de_compra_informada(cliente):
    rast = cliente.post("/api/analise", json=pedido_acoes()).json()["rastreabilidade"]
    por_id = {p["id"]: p for p in rast["posicoes"]}

    assert por_id["PETR4.SA"]["data_compra"] == "2025-09-10"
    assert por_id["PETR4.SA"]["dias_corridos"] > 300
    assert por_id["VALE3.SA"]["data_compra"] == "2026-03-10"
    assert por_id["VALE3.SA"]["dias_corridos"] < por_id["PETR4.SA"]["dias_corridos"]


def test_acoes_respeitam_o_preco_de_compra_informado(cliente):
    rast = cliente.post("/api/analise", json=pedido_acoes()).json()["rastreabilidade"]
    por_id = {p["id"]: p for p in rast["posicoes"]}

    assert por_id["VALE3.SA"]["preco_compra"] == 55.0
    assert por_id["VALE3.SA"]["preco_compra_estimado"] is False
    assert por_id["PETR4.SA"]["preco_compra_estimado"] is True


def test_valor_atual_das_acoes_sai_do_peso_sobre_a_carteira(cliente):
    rast = cliente.post("/api/analise", json=pedido_acoes()).json()["rastreabilidade"]
    por_id = {p["id"]: p for p in rast["posicoes"]}

    assert por_id["PETR4.SA"]["valor_atual"] == pytest.approx(60_000.0, abs=0.01)
    assert por_id["VALE3.SA"]["valor_atual"] == pytest.approx(40_000.0, abs=0.01)
    assert rast["totais"]["valor_atual"] == pytest.approx(100_000.0, abs=0.02)


def test_acoes_sem_data_de_compra_continuam_funcionando(cliente):
    """Contrato antigo: quem nao manda data de compra nao quebra."""
    corpo = cliente.post(
        "/api/analise",
        json={
            "posicoes": [{"ticker": "PETR4.SA", "peso": 100}],
            "inicio": "2024-06-01",
            "fim": "2026-09-10",
        },
    )

    assert corpo.status_code == 200
    posicao = corpo.json()["rastreabilidade"]["posicoes"][0]
    assert posicao["data_compra_informada"] is None
    assert posicao["valorizacao_percentual"] is not None


def test_data_de_compra_no_futuro_e_recusada(cliente):
    resposta = cliente.post(
        "/api/analise",
        json=pedido_acoes(
            posicoes=[{"ticker": "PETR4.SA", "peso": 100, "data_compra": "2030-01-01"}]
        ),
    )

    assert resposta.status_code == 422


# --------------------------------------------------------------------------- #
# Renda fixa
# --------------------------------------------------------------------------- #

def test_renda_fixa_rastreia_o_pu_de_aquisicao_como_preco_de_compra(cliente):
    rast = cliente.post(
        "/api/analise/renda-fixa", json=pedido_renda_fixa()
    ).json()["rastreabilidade"]
    por_id = {p["id"]: p for p in rast["posicoes"]}

    assert por_id[IPCA]["preco_compra"] == 3000.0
    assert por_id[IPCA]["preco_compra_estimado"] is False
    assert por_id[IPCA]["classe"] == "renda-fixa"


def test_renda_fixa_estima_o_pu_quando_nao_informado(cliente):
    rast = cliente.post(
        "/api/analise/renda-fixa", json=pedido_renda_fixa()
    ).json()["rastreabilidade"]
    por_id = {p["id"]: p for p in rast["posicoes"]}

    assert por_id[PREFIXADO]["preco_compra_estimado"] is True
    assert por_id[PREFIXADO]["data_compra"] == "2026-03-10"


def test_valor_da_posicao_em_renda_fixa_e_quantidade_vezes_pu(cliente):
    rast = cliente.post(
        "/api/analise/renda-fixa", json=pedido_renda_fixa()
    ).json()["rastreabilidade"]
    por_id = {p["id"]: p for p in rast["posicoes"]}

    linha = por_id[IPCA]
    assert linha["quantidade"] == 10.0
    assert linha["valor_atual"] == pytest.approx(10.0 * linha["preco_atual"], abs=0.02)
    assert linha["valor_compra"] == pytest.approx(10.0 * 3000.0, abs=0.02)


def test_rotulo_do_titulo_e_o_codigo_oficial_e_nao_o_nome_comercial(cliente):
    """Na mesa o papel e 'LTN 29', nao 'Tesouro Prefixado' nem o slug."""
    rast = cliente.post(
        "/api/analise/renda-fixa", json=pedido_renda_fixa()
    ).json()["rastreabilidade"]
    por_id = {p["id"]: p for p in rast["posicoes"]}

    assert por_id[PREFIXADO]["rotulo"] == "LTN 29"
    assert por_id[IPCA]["rotulo"] == "NTN-B Principal 35"
    assert all("tesouro" not in p["rotulo"].lower() for p in rast["posicoes"])


def test_marcacao_expoe_codigo_e_rotulo_do_papel(cliente):
    linhas = cliente.post(
        "/api/analise/renda-fixa", json=pedido_renda_fixa()
    ).json()["marcacao"]["posicoes"]
    por_id = {l["id"]: l for l in linhas}

    assert por_id[PREFIXADO]["codigo"] == "LTN"
    assert por_id[PREFIXADO]["rotulo"] == "LTN 29"
    # o nome comercial continua no payload, em campo proprio
    assert por_id[PREFIXADO]["tipo"] == "Tesouro Prefixado"


def test_renda_fixa_traz_o_papel_no_detalhe(cliente):
    rast = cliente.post(
        "/api/analise/renda-fixa", json=pedido_renda_fixa()
    ).json()["rastreabilidade"]

    # `detalhe` so aparece em renda fixa; por isso nao esta em CAMPOS_DA_POSICAO
    assert all("tipo" in p.get("detalhe", {}) for p in rast["posicoes"])


def test_renda_fixa_mantem_marcacao_e_por_titulo(cliente):
    """A rastreabilidade entra SEM tirar nada do que ja existia."""
    corpo = cliente.post("/api/analise/renda-fixa", json=pedido_renda_fixa()).json()

    assert corpo["classe"] == "renda-fixa"
    assert corpo["marcacao"]["posicoes"]
    assert corpo["por_titulo"]
    assert corpo["metodos"]["empirico"]["var_percentual"] is not None


# --------------------------------------------------------------------------- #
# Ambos
# --------------------------------------------------------------------------- #

def test_consolidado_rastreia_as_duas_classes_na_mesma_lista(cliente):
    rast = cliente.post(
        "/api/analise/consolidado", json=pedido_consolidado()
    ).json()["rastreabilidade"]

    classes = {p["classe"] for p in rast["posicoes"]}
    assert classes == {"acoes", "renda-fixa"}
    assert rast["totais"]["posicoes"] == 2


def test_consolidado_ganha_as_metricas_da_marcacao_por_titulo(cliente):
    """Pedido explicito: a metrificacao da marcacao tambem no book de ambos."""
    corpo = cliente.post("/api/analise/consolidado", json=pedido_consolidado()).json()

    assert corpo["por_titulo"]
    linha = corpo["por_titulo"][0]
    assert linha["id"] == IPCA
    assert set(linha["metodos"]) == {"empirico", "parametrico", "ewma"}
    assert linha["sharpe"] is not None


def test_consolidado_mantem_marcacao_e_composicao(cliente):
    corpo = cliente.post("/api/analise/consolidado", json=pedido_consolidado()).json()

    assert corpo["classe"] == "consolidado"
    assert corpo["marcacao"]["posicoes"]
    assert corpo["composicao"]["valor_total"] > 0
    assert corpo["composicao"]["peso_acoes"] + corpo["composicao"][
        "peso_renda_fixa"
    ] == pytest.approx(1.0, abs=1e-6)


def test_consolidado_referencia_as_datas_em_comum(cliente):
    """O book de ambos so existe onde a bolsa e o Tesouro publicaram no mesmo dia."""
    corpo = cliente.post("/api/analise/consolidado", json=pedido_consolidado()).json()
    rast = corpo["rastreabilidade"]

    assert rast["data_referencia"] == corpo["parametros"]["fim"]
    assert all(p["data_preco_atual"] == rast["data_referencia"] for p in rast["posicoes"])


def test_avisos_da_rastreabilidade_sobem_junto_com_os_demais(cliente):
    corpo = cliente.post("/api/analise/renda-fixa", json=pedido_renda_fixa()).json()

    codigos = {a["codigo"] for a in corpo["avisos"]}
    assert "preco_compra_estimado" in codigos
