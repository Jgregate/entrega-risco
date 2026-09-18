"""Testes da rota GET /api/titulos-publicos/disponiveis.

O download e sempre substituido: nenhum teste toca a rede.
"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import titulos_publicos as tp
from app.main import app
from app.titulos_publicos import ErroTesouro
from tests.test_titulos_publicos import csv_bytes

ROTA = "/api/titulos-publicos/disponiveis"


@pytest.fixture(autouse=True)
def cache_isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "DIRETORIO_CACHE", tmp_path)
    tp.limpar_cache(memoria=True)
    yield
    tp.limpar_cache(memoria=True)


@pytest.fixture
def cliente():
    return TestClient(app)


@pytest.fixture
def com_arquivo(monkeypatch):
    monkeypatch.setattr(tp, "_baixa_bytes", lambda: csv_bytes())


def test_rota_responde_o_universo_do_ultimo_dia_util(cliente, com_arquivo):
    corpo = cliente.get(ROTA).json()

    assert corpo["data_base"] == "2026-09-10"
    assert corpo["quantidade"] == 3
    assert len(corpo["titulos"]) == 3


def test_rota_devolve_os_campos_do_contrato(cliente, com_arquivo):
    titulos = cliente.get(ROTA).json()["titulos"]

    assert all(
        set(t) == {
            "id", "tipo", "tipo_slug", "codigo", "rotulo",
            "vencimento", "taxa_venda", "pu_venda",
        }
        for t in titulos
    )
    ipca = next(t for t in titulos if t["id"] == "tesouro_ipca_2035-05-15")
    assert ipca["tipo"] == "Tesouro IPCA+"
    assert ipca["taxa_venda"] == 0.0724
    assert ipca["pu_venda"] == 3398.71
    assert ipca["codigo"] == "NTN-B Principal"
    assert ipca["rotulo"] == "NTN-B Principal 35"

    prefixado = next(t for t in titulos if t["id"] == "tesouro_prefixado_2029-01-01")
    assert prefixado["rotulo"] == "LTN 29"


def test_rota_expoe_a_procedencia_do_arquivo(cliente, com_arquivo):
    """A UI precisa saber se esta olhando cache degradado."""
    fonte = cliente.get(ROTA).json()["fonte"]

    assert fonte["origem"] == "download"
    assert fonte["degradado"] is False
    assert fonte["data_base"] == "2026-09-10"


def test_rota_sinaliza_quando_esta_servindo_cache_vencido(cliente, monkeypatch):
    monkeypatch.setattr(tp, "_baixa_bytes", lambda: csv_bytes())
    cliente.get(ROTA)

    def falha():
        raise ErroTesouro("Tesouro Transparente fora do ar")

    monkeypatch.setattr(tp, "_baixa_bytes", falha)
    monkeypatch.setattr(tp, "TTL_SEGUNDOS", 0)
    resposta = cliente.get(ROTA)

    assert resposta.status_code == 200
    assert resposta.json()["fonte"]["degradado"] is True
    assert resposta.json()["fonte"]["origem"] == "cache-vencido"


def test_rota_nao_cai_quando_a_fonte_esta_fora_mas_ha_cache(cliente, monkeypatch):
    """Degradar e o comportamento pedido: a rota continua de pe."""
    monkeypatch.setattr(tp, "_baixa_bytes", lambda: csv_bytes())
    cliente.get(ROTA)

    monkeypatch.setattr(tp, "TTL_SEGUNDOS", 0)
    monkeypatch.setattr(
        tp, "_baixa_bytes", lambda: (_ for _ in ()).throw(ErroTesouro("sem rede"))
    )

    assert cliente.get(ROTA).status_code == 200


def test_rota_responde_503_sem_download_e_sem_cache(cliente, monkeypatch):
    def falha():
        raise ErroTesouro("Tesouro Transparente fora do ar")

    monkeypatch.setattr(tp, "_baixa_bytes", falha)
    resposta = cliente.get(ROTA)

    assert resposta.status_code == 503
    assert "fora do ar" in resposta.json()["detail"]


def test_rota_responde_503_quando_o_universo_esta_vazio(cliente, com_arquivo, monkeypatch):
    monkeypatch.setattr(tp, "universo", lambda quadro, hoje=None: quadro.iloc[0:0])
    resposta = cliente.get(ROTA)

    assert resposta.status_code == 503
    assert "nenhum titulo disponivel" in resposta.json()["detail"]


def test_rota_entrega_a_lista_ordenada_por_tipo_e_vencimento(cliente, com_arquivo):
    titulos = cliente.get(ROTA).json()["titulos"]
    chaves = [(t["tipo"], t["vencimento"]) for t in titulos]

    assert chaves == sorted(chaves)


def test_rota_reaproveita_o_cache_entre_chamadas(cliente, monkeypatch):
    chamadas = []

    def baixa():
        chamadas.append(1)
        return csv_bytes()

    monkeypatch.setattr(tp, "_baixa_bytes", baixa)
    cliente.get(ROTA)
    cliente.get(ROTA)

    assert len(chamadas) == 1
