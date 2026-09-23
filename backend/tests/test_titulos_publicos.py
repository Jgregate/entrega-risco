"""Testes da ingestao do Tesouro Direto: parsing do CSV e cache.

Nenhum teste toca a rede — `_baixa_bytes` e sempre substituido, e o cache em
disco e redirecionado para o tmp_path do pytest.
"""

from datetime import date

import pandas as pd
import pytest

from app import titulos_publicos as tp
from app.titulos_publicos import ErroTesouro, parse_csv

CABECALHO = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;"
    "Taxa Venda Manha;PU Compra Manha;PU Venda Manha;PU Base Manha"
)

LINHAS = [
    "Tesouro Selic;01/03/2027;10/09/2026;0,00;0,01;19854,30;19843,06;19843,06",
    "Tesouro Selic;01/03/2027;09/09/2026;0,02;0,03;19840,11;19828,90;19828,90",
    "Tesouro IPCA+;15/05/2035;10/09/2026;7,12;7,24;3421,55;3398,71;3398,71",
    "Tesouro Prefixado;01/01/2029;10/09/2026;13,40;13,52;7712,08;7695,44;7695,44",
]


def csv_bytes(linhas=None) -> bytes:
    """Monta o arquivo como o Tesouro publica: latin1, ';' e decimal ','."""
    corpo = "\n".join([CABECALHO, *(LINHAS if linhas is None else linhas)])
    return corpo.encode("latin1")


@pytest.fixture(autouse=True)
def cache_isolado(tmp_path, monkeypatch):
    """Cada teste comeca sem cache de memoria e com disco proprio."""
    monkeypatch.setattr(tp, "DIRETORIO_CACHE", tmp_path)
    tp.limpar_cache(memoria=True)
    yield
    tp.limpar_cache(memoria=True)


def download_falso(conteudo=None, contador=None):
    """Substituto de `_baixa_bytes` que conta quantas vezes foi chamado."""

    def _baixa():
        if contador is not None:
            contador.append(1)
        return csv_bytes() if conteudo is None else conteudo

    return _baixa


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

def test_parse_normaliza_as_colunas_do_projeto():
    quadro = parse_csv(csv_bytes())
    assert list(quadro.columns) == [
        "tipo",
        "vencimento",
        "data_base",
        "taxa_compra",
        "taxa_venda",
        "pu_compra",
        "pu_venda",
    ]
    assert len(quadro) == 4


def test_parse_ignora_a_coluna_pu_base_manha():
    """Oitava coluna do arquivo, sem uso no projeto."""
    assert "PU Base Manha" not in parse_csv(csv_bytes()).columns


def test_parse_le_decimal_com_virgula():
    quadro = parse_csv(csv_bytes())
    selic = quadro[quadro["vencimento"] == pd.Timestamp("2027-03-01")]
    assert selic["pu_venda"].max() == pytest.approx(19843.06)


def test_parse_usa_data_no_formato_brasileiro():
    """03/01 tem que virar 3 de janeiro, nao 1 de marco."""
    linha = "Tesouro Selic;03/01/2030;10/09/2026;0,00;0,01;100,00;99,50;99,50"
    quadro = parse_csv(csv_bytes([linha]))
    assert quadro.loc[0, "vencimento"] == pd.Timestamp("2030-01-03")


def test_parse_converte_taxa_percentual_em_fracao():
    """13,52% ao ano sai como 0,1352 — mesma unidade da Selic em selic.py."""
    quadro = parse_csv(csv_bytes())
    prefixado = quadro[quadro["tipo"] == "Tesouro Prefixado"].iloc[0]
    assert prefixado["taxa_venda"] == pytest.approx(0.1352)
    assert prefixado["taxa_compra"] == pytest.approx(0.1340)


def test_parse_mantem_pu_em_reais():
    """PU nao e taxa: nao pode ter sido dividido por 100 junto."""
    quadro = parse_csv(csv_bytes())
    assert quadro["pu_venda"].max() > 1000


def test_parse_decodifica_latin1():
    """UTF-8 quebraria o arquivo; o Tesouro publica em latin1."""
    linha = "Tesouro Prefixado Índice;01/01/2029;10/09/2026;1,00;1,10;500,00;499,00;499,00"
    quadro = parse_csv(csv_bytes([linha]))
    assert quadro.loc[0, "tipo"] == "Tesouro Prefixado Índice"


def test_parse_exige_as_colunas_esperadas():
    ruim = b"Coluna A;Coluna B\n1;2"
    with pytest.raises(ErroTesouro, match="colunas esperadas"):
        parse_csv(ruim)


def test_parse_descarta_linha_sem_pu_venda():
    """Sem PU de venda a linha nao serve nem para marcacao nem para a serie."""
    linha = "Tesouro Selic;01/03/2027;08/09/2026;0,00;0,01;19800,00;;19800,00"
    quadro = parse_csv(csv_bytes([*LINHAS, linha]))
    assert len(quadro) == 4
    assert quadro["pu_venda"].notna().all()


def test_parse_descarta_linha_com_pu_venda_zerado():
    """O arquivo traz PU zero na vespera do vencimento de papeis com cupom.

    Um zero no meio da serie vira -100% e depois +inf no pct_change(), entao
    a linha nao pode passar da ingestao.
    """
    linha = "Tesouro Prefixado com Juros Semestrais;01/01/2029;08/09/2026;0,13;0,13;0,00;0,00;0,00"
    quadro = parse_csv(csv_bytes([*LINHAS, linha]))
    assert len(quadro) == 4
    assert (quadro["pu_venda"] > 0).all()


def test_parse_anula_pu_compra_zerado_sem_perder_a_linha():
    """PU de compra e informativo: zerado vira nulo, mas nao descarta a marcacao."""
    linha = "Tesouro Selic;01/03/2027;08/09/2026;0,00;0,01;0,00;19800,00;19800,00"
    quadro = parse_csv(csv_bytes([linha]))
    assert len(quadro) == 1
    assert pd.isna(quadro.loc[0, "pu_compra"])
    assert quadro.loc[0, "pu_venda"] == pytest.approx(19800.0)


def test_parse_recusa_arquivo_sem_nenhuma_linha_aproveitavel():
    linha = "Tesouro Selic;01/03/2027;10/09/2026;0,00;0,01;19800,00;;19800,00"
    with pytest.raises(ErroTesouro, match="aproveitavel"):
        parse_csv(csv_bytes([linha]))


def test_parse_ordena_por_tipo_vencimento_e_data_base():
    quadro = parse_csv(csv_bytes())
    esperado = quadro.sort_values(["tipo", "vencimento", "data_base"])
    assert quadro.equals(esperado.reset_index(drop=True))


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #

def test_carregar_baixa_uma_vez_e_reusa_a_memoria(monkeypatch):
    chamadas = []
    monkeypatch.setattr(tp, "_baixa_bytes", download_falso(contador=chamadas))

    primeiro = tp.carregar()
    segundo = tp.carregar()

    assert len(chamadas) == 1
    assert primeiro.origem == "download"
    assert segundo.origem == "cache-memoria"
    assert not segundo.degradado


def test_carregar_rebaixa_quando_o_ttl_vence(monkeypatch):
    chamadas = []
    monkeypatch.setattr(tp, "_baixa_bytes", download_falso(contador=chamadas))
    tp.carregar()

    monkeypatch.setattr(tp, "TTL_SEGUNDOS", 0)
    tp.carregar()

    assert len(chamadas) == 2


def test_carregar_le_do_disco_quando_a_memoria_esvazia(monkeypatch):
    """O pickle e o que faz o historico sobreviver ao reload do uvicorn."""
    monkeypatch.setattr(tp, "_baixa_bytes", download_falso())
    tp.carregar()

    tp.limpar_cache(memoria=True)

    def nao_deveria_baixar():
        raise AssertionError("deveria ter lido do disco, sem baixar de novo")

    monkeypatch.setattr(tp, "_baixa_bytes", nao_deveria_baixar)
    do_disco = tp.carregar()

    assert do_disco.origem == "cache-disco"
    assert len(do_disco.quadro) == 4


def test_carregar_degrada_para_o_cache_quando_o_download_falha(monkeypatch):
    """Falha de rede nao pode derrubar a rota: devolve o cache anterior."""
    monkeypatch.setattr(tp, "_baixa_bytes", download_falso())
    tp.carregar()

    def falha():
        raise ErroTesouro("Tesouro Transparente fora do ar")

    monkeypatch.setattr(tp, "_baixa_bytes", falha)
    monkeypatch.setattr(tp, "TTL_SEGUNDOS", 0)
    degradado = tp.carregar()

    assert degradado.degradado
    assert degradado.origem == "cache-vencido"
    assert len(degradado.quadro) == 4


def test_carregar_propaga_o_erro_quando_nao_ha_cache_algum(monkeypatch):
    def falha():
        raise ErroTesouro("Tesouro Transparente fora do ar")

    monkeypatch.setattr(tp, "_baixa_bytes", falha)
    with pytest.raises(ErroTesouro, match="fora do ar"):
        tp.carregar()


def test_cache_de_disco_corrompido_nao_derruba_a_ingestao(monkeypatch):
    caminho = tp._caminho_cache()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"isto nao e um pickle")

    monkeypatch.setattr(tp, "_baixa_bytes", download_falso())
    assert tp.carregar().origem == "download"


def test_meta_expoe_a_procedencia_do_historico(monkeypatch):
    monkeypatch.setattr(tp, "_baixa_bytes", download_falso())
    meta = tp.carregar().meta()

    assert meta["origem"] == "download"
    assert meta["degradado"] is False
    assert meta["data_base"] == "2026-09-10"
    assert meta["linhas"] == 4


def test_data_base_max_e_o_ultimo_dia_util_publicado(monkeypatch):
    monkeypatch.setattr(tp, "_baixa_bytes", download_falso())
    assert tp.carregar().data_base_max == pd.Timestamp("2026-09-10")


# --------------------------------------------------------------------------- #
# Universo disponivel
# --------------------------------------------------------------------------- #

HOJE = date(2026, 9, 12)


def test_slug_derruba_o_mais_e_normaliza():
    assert tp.slug_tipo("Tesouro IPCA+") == "tesouro_ipca"
    assert tp.slug_tipo("Tesouro Selic") == "tesouro_selic"
    assert tp.slug_tipo("Tesouro Renda+ Aposentadoria Extra") == (
        "tesouro_renda_aposentadoria_extra"
    )


def test_slug_separa_o_papel_com_cupom_do_sem_cupom():
    """'IPCA+' e 'IPCA+ com Juros Semestrais' sao papeis distintos."""
    assert tp.slug_tipo("Tesouro IPCA+") != tp.slug_tipo("Tesouro IPCA+ com Juros Semestrais")


def test_slug_remove_acento():
    assert tp.slug_tipo("Tesouro Prefixado Índice") == "tesouro_prefixado_indice"


def test_identificador_segue_o_formato_combinado():
    assert tp.identificador("Tesouro IPCA+", pd.Timestamp("2035-05-15")) == (
        "tesouro_ipca_2035-05-15"
    )


def test_universo_fica_so_com_a_ultima_data_base():
    """A linha de 09/09 do mesmo papel nao pode aparecer junto com a de 10/09."""
    disponiveis = tp.universo(parse_csv(csv_bytes()), hoje=HOJE)
    assert (disponiveis["data_base"] == pd.Timestamp("2026-09-10")).all()
    assert len(disponiveis) == 3


def test_universo_descarta_papel_ja_vencido():
    """Vencimento de ontem ainda aparece na ultima data base, mas nao e compravel."""
    vencido = "Tesouro Prefixado;11/09/2026;10/09/2026;13,00;13,10;999,00;998,00;998,00"
    disponiveis = tp.universo(parse_csv(csv_bytes([*LINHAS, vencido])), hoje=HOJE)
    assert "tesouro_prefixado_2026-09-11" not in set(disponiveis["id"])
    assert len(disponiveis) == 3


def test_universo_compara_vencimento_com_hoje_e_nao_com_a_data_base():
    """Entre a publicacao (10/09) e hoje (12/09) passou o vencimento de 11/09."""
    vencido = "Tesouro Prefixado;11/09/2026;10/09/2026;13,00;13,10;999,00;998,00;998,00"
    quadro = parse_csv(csv_bytes([*LINHAS, vencido]))
    na_data_base = tp.universo(quadro, hoje=date(2026, 9, 10))
    assert "tesouro_prefixado_2026-09-11" in set(na_data_base["id"])


def test_universo_traz_id_unico_por_papel():
    disponiveis = tp.universo(parse_csv(csv_bytes()), hoje=HOJE)
    assert disponiveis["id"].is_unique
    assert set(disponiveis["id"]) == {
        "tesouro_ipca_2035-05-15",
        "tesouro_prefixado_2029-01-01",
        "tesouro_selic_2027-03-01",
    }


def test_universo_sai_ordenado_por_tipo_e_vencimento():
    disponiveis = tp.universo(parse_csv(csv_bytes()), hoje=HOJE)
    esperado = disponiveis.sort_values(["tipo", "vencimento"])
    assert disponiveis.equals(esperado.reset_index(drop=True))


def test_universo_vazio_quando_tudo_ja_venceu():
    disponiveis = tp.universo(parse_csv(csv_bytes()), hoje=date(2040, 1, 1))
    assert disponiveis.empty


def test_serializa_universo_entrega_os_campos_do_contrato():
    disponiveis = tp.universo(parse_csv(csv_bytes()), hoje=HOJE)
    ipca = next(t for t in tp.serializa_universo(disponiveis) if t["tipo"] == "Tesouro IPCA+")

    assert ipca == {
        "id": "tesouro_ipca_2035-05-15",
        "tipo": "Tesouro IPCA+",
        "tipo_slug": "tesouro_ipca",
        "codigo": "NTN-B Principal",
        "rotulo": "NTN-B Principal 35",
        "vencimento": "2035-05-15",
        "taxa_venda": 0.0724,
        "pu_venda": 3398.71,
    }
