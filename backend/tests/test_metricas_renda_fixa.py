"""Testes das metricas de risco sobre o book de renda fixa.

O ponto central destes testes e provar que NAO ha motor novo: o VaR que sai
pelo caminho da renda fixa tem que ser identicamente o mesmo numero que os
modulos `var_*` produzem sobre a mesma serie.

Tudo com CSV sintetico, sem rede.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app import var_empirico, var_ewma, var_parametrico
from app.analise import analisar
from app.renda_fixa import (
    ErroRendaFixa,
    avisos_da_matriz,
    avisos_do_backtest,
    consolidar,
    marcar,
    matriz_pu,
    metricas_por_titulo,
    preparar,
    valores_marcados,
)
from app.schemas import PosicaoRendaFixa
from app.titulos_publicos import parse_csv
from app.var_core import resumo_violacoes, retorno_carteira, retornos_simples

CABECALHO = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;"
    "Taxa Venda Manha;PU Compra Manha;PU Venda Manha;PU Base Manha"
)

HOJE = date(2026, 9, 12)
LONGO = "tesouro_ipca_2035-05-15"
CURTO = "tesouro_prefixado_2029-01-01"


def _linhas(tipo, vencimento, datas, pus):
    return [
        f"{tipo};{vencimento};{d:%d/%m/%Y};7,00;7,10;"
        f"{pu + 10:.2f};{pu:.2f};{pu:.2f}".replace(".", ",")
        for d, pu in zip(datas, pus)
    ]


def _passeio(n, inicial, sigma, semente):
    rng = np.random.default_rng(semente)
    return inicial * np.cumprod(1.0 + rng.normal(0.0002, sigma, n))


@pytest.fixture
def quadro():
    """Dois papeis: um com 600 dias de historico, outro com 120."""
    datas = pd.bdate_range(end="2026-09-10", periods=600)
    longo = _linhas("Tesouro IPCA+", "15/05/2035", datas, _passeio(600, 3000, 0.004, 1))
    curto = _linhas(
        "Tesouro Prefixado", "01/01/2029", datas[-120:], _passeio(120, 750, 0.003, 2)
    )
    return parse_csv("\n".join([CABECALHO, *longo, *curto]).encode("latin1"))


def posicao(titulo_id, quantidade=10, **kwargs):
    return PosicaoRendaFixa(titulo_id=titulo_id, quantidade=quantidade, **kwargs)


@pytest.fixture
def book_longo(quadro):
    return preparar(quadro, [posicao(LONGO)], confianca=0.95, janela=252, hoje=HOJE)


def selic_constante(indice, anual=0.10):
    diaria = (1.0 + anual) ** (1.0 / 252) - 1.0
    return pd.Series(diaria, index=indice, name="selic")


# --------------------------------------------------------------------------- #
# Matriz de precos
# --------------------------------------------------------------------------- #

def test_matriz_tem_uma_coluna_por_papel(quadro):
    marcacao = marcar(quadro, [posicao(LONGO), posicao(CURTO)], hoje=HOJE)
    matriz = matriz_pu(quadro, marcacao)

    assert set(matriz.columns) == {LONGO, CURTO}
    assert isinstance(matriz.index, pd.DatetimeIndex)
    assert matriz.index.is_monotonic_increasing


def test_matriz_traz_o_pu_de_venda_e_nao_o_de_compra(quadro):
    marcacao = marcar(quadro, [posicao(LONGO)], hoje=HOJE)
    matriz = matriz_pu(quadro, marcacao)
    linha = marcacao["posicoes"][0]

    assert matriz[LONGO].iloc[-1] == pytest.approx(linha["pu_marcacao"], abs=0.01)


def test_matriz_respeita_o_recorte_de_periodo(quadro):
    marcacao = marcar(quadro, [posicao(LONGO)], hoje=HOJE)
    matriz = matriz_pu(quadro, marcacao, inicio=date(2026, 1, 1))

    assert matriz.index.min() >= pd.Timestamp("2026-01-01")


def test_papel_curto_entra_com_buraco_no_inicio(quadro):
    """A matriz alinha pela uniao das datas; o motor e que corta na intersecao."""
    marcacao = marcar(quadro, [posicao(LONGO), posicao(CURTO)], hoje=HOJE)
    matriz = matriz_pu(quadro, marcacao)

    assert matriz[CURTO].isna().sum() == 480
    assert len(matriz.dropna(how="any")) == 120


# --------------------------------------------------------------------------- #
# O motor e o mesmo — nenhum calculo novo
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "modulo", [var_empirico, var_parametrico, var_ewma], ids=lambda m: m.NOME
)
def test_var_por_titulo_e_identico_ao_do_modulo_original(quadro, modulo):
    """O numero tem que sair do mesmo codigo que atende as acoes."""
    marcacao = marcar(quadro, [posicao(LONGO)], hoje=HOJE)
    matriz = matriz_pu(quadro, marcacao)
    linhas, _ = metricas_por_titulo(
        matriz, marcacao, selic_constante(matriz.index), 0.95, 1, 252
    )

    retornos = retorno_carteira(retornos_simples(matriz[[LONGO]].dropna()), {LONGO: 1.0})
    esperado = modulo.pontual(retornos, 0.95, 1)

    saida = linhas[0]["metodos"][modulo.NOME]
    assert saida["var_percentual"] == pytest.approx(round(esperado["var"], 6))
    assert saida["es_percentual"] == pytest.approx(round(esperado["es"], 6))


def test_resumo_do_backtest_por_titulo_vem_do_rolling_original(quadro):
    marcacao = marcar(quadro, [posicao(LONGO)], hoje=HOJE)
    matriz = matriz_pu(quadro, marcacao)
    linhas, _ = metricas_por_titulo(
        matriz, marcacao, selic_constante(matriz.index), 0.95, 1, 252
    )

    retornos = retorno_carteira(retornos_simples(matriz[[LONGO]].dropna()), {LONGO: 1.0})
    esperado = resumo_violacoes(var_empirico.rolling(retornos, 0.95, 252), 0.95)

    assert linhas[0]["metodos"]["empirico"]["backtest_resumo"] == esperado


def test_book_agregado_passa_pelo_analisar_das_acoes(quadro, book_longo):
    """`analisar()` e literalmente a mesma funcao usada em /api/analise."""
    saida = analisar(
        precos=book_longo["matriz"].dropna(how="any"),
        pesos=book_longo["pesos"],
        confianca=0.95,
        horizonte=1,
        janela=252,
        valor_carteira=book_longo["valor_marcado"],
    )

    assert set(saida["metodos"]) == {"empirico", "parametrico", "ewma"}
    assert saida["metodos"]["empirico"]["backtest"]["resumo"]["kupiec"]["p_valor"] is not None


def test_var_monetario_usa_o_valor_marcado_do_papel(quadro):
    marcacao = marcar(quadro, [posicao(LONGO, quantidade=10)], hoje=HOJE)
    matriz = matriz_pu(quadro, marcacao)
    linha = metricas_por_titulo(
        matriz, marcacao, selic_constante(matriz.index), 0.95, 1, 252
    )[0][0]

    empirico = linha["metodos"]["empirico"]
    assert empirico["var_monetario"] == pytest.approx(
        empirico["var_percentual"] * linha["valor_marcado"], rel=1e-4
    )


def test_anualizacao_e_em_252_dias_uteis(quadro):
    """Renda fixa brasileira usa dia util; o projeto inteiro ja estava em 252."""
    marcacao = marcar(quadro, [posicao(LONGO)], hoje=HOJE)
    matriz = matriz_pu(quadro, marcacao)
    linha = metricas_por_titulo(
        matriz, marcacao, selic_constante(matriz.index), 0.95, 1, 252
    )[0][0]

    retornos = retorno_carteira(retornos_simples(matriz[[LONGO]].dropna()), {LONGO: 1.0})
    esperado = float(retornos.std(ddof=1)) * np.sqrt(252)

    assert linha["vol_anualizada"] == pytest.approx(round(esperado, 6))
    # e nao a anualizacao por ano corrido, que renda fixa brasileira nao usa
    assert linha["vol_anualizada"] != pytest.approx(
        round(float(retornos.std(ddof=1)) * np.sqrt(365), 6)
    )


# --------------------------------------------------------------------------- #
# Pesos
# --------------------------------------------------------------------------- #

def test_pesos_do_book_saem_do_valor_marcado(quadro):
    book = preparar(
        quadro, [posicao(LONGO, 10), posicao(CURTO, 4)], confianca=0.95, janela=60, hoje=HOJE
    )
    assert sum(book["pesos"].values()) == pytest.approx(1.0, abs=1e-6)

    marcado = {l["id"]: l["valor_marcado"] for l in book["marcacao"]["posicoes"]}
    total = sum(marcado.values())
    assert book["pesos"][LONGO] == pytest.approx(marcado[LONGO] / total, abs=1e-6)


# --------------------------------------------------------------------------- #
# Avisos estruturados
# --------------------------------------------------------------------------- #

def test_aviso_quando_a_janela_nao_cabe_no_historico(quadro):
    """152 retornos e janela de 252: o Kupiec nao tem amostra."""
    marcacao = marcar(quadro, [posicao(CURTO)], hoje=HOJE)
    matriz = matriz_pu(quadro, marcacao)
    _, avisos = metricas_por_titulo(
        matriz, marcacao, selic_constante(matriz.index), 0.95, 1, 252
    )

    assert [a["codigo"] for a in avisos] == ["kupiec_sem_amostra"]
    assert avisos[0]["severidade"] == "erro"
    assert avisos[0]["detalhe"]["minimo_necessario"] == 253


def test_kupiec_sem_amostra_devolve_nulo_e_nao_numero_sem_sentido(quadro):
    marcacao = marcar(quadro, [posicao(CURTO)], hoje=HOJE)
    matriz = matriz_pu(quadro, marcacao)
    linha = metricas_por_titulo(
        matriz, marcacao, selic_constante(matriz.index), 0.95, 1, 252
    )[0][0]

    kupiec = linha["metodos"]["empirico"]["backtest_resumo"]["kupiec"]
    assert kupiec["p_valor"] is None
    assert kupiec["rejeita_5pct"] is None


def test_aviso_de_baixa_potencia_quando_ha_poucas_violacoes_esperadas():
    resumo = {"observacoes": 80}
    avisos = avisos_do_backtest(resumo, confianca=0.95, janela=30, n_retornos=110)

    assert avisos[0]["codigo"] == "kupiec_baixa_potencia"
    assert avisos[0]["severidade"] == "aviso"
    assert avisos[0]["detalhe"]["violacoes_esperadas"] == 4.0


def test_backtest_com_amostra_suficiente_nao_gera_aviso():
    avisos = avisos_do_backtest({"observacoes": 400}, confianca=0.95, janela=252, n_retornos=652)
    assert avisos == []


def test_aviso_de_intersecao_curta_aponta_o_papel_limitante(quadro):
    marcacao = marcar(quadro, [posicao(LONGO), posicao(CURTO)], hoje=HOJE)
    avisos = avisos_da_matriz(matriz_pu(quadro, marcacao))

    assert avisos[0]["codigo"] == "intersecao_curta"
    assert avisos[0]["detalhe"]["papel_limitante"] == CURTO
    assert avisos[0]["detalhe"]["datas_comuns"] == 120


def test_sem_aviso_de_intersecao_quando_os_papeis_estao_alinhados(quadro):
    marcacao = marcar(quadro, [posicao(LONGO)], hoje=HOJE)
    assert avisos_da_matriz(matriz_pu(quadro, marcacao)) == []


def test_papel_curto_demais_e_pulado_com_aviso(quadro):
    """Menos de 30 precos: nao ha o que estimar."""
    datas = pd.bdate_range(end="2026-09-10", periods=600)
    minusculo = _linhas("Tesouro Selic", "01/03/2031", datas[-10:], _passeio(10, 15000, 0.001, 3))
    ampliado = parse_csv(
        "\n".join(
            [
                CABECALHO,
                *_linhas("Tesouro IPCA+", "15/05/2035", datas, _passeio(600, 3000, 0.004, 1)),
                *minusculo,
            ]
        ).encode("latin1")
    )
    marcacao = marcar(
        ampliado, [posicao(LONGO), posicao("tesouro_selic_2031-03-01")], hoje=HOJE
    )
    matriz = matriz_pu(ampliado, marcacao)
    linhas, avisos = metricas_por_titulo(
        matriz, marcacao, selic_constante(matriz.index), 0.95, 1, 252
    )

    assert [l["id"] for l in linhas] == [LONGO]
    assert any(a["codigo"] == "historico_insuficiente" for a in avisos)


def test_book_sem_datas_comuns_suficientes_e_recusado(quadro):
    datas = pd.bdate_range(end="2026-09-10", periods=600)
    curtissimo = _linhas(
        "Tesouro Selic", "01/03/2031", datas[-10:], _passeio(10, 15000, 0.001, 3)
    )
    ampliado = parse_csv(
        "\n".join(
            [
                CABECALHO,
                *_linhas("Tesouro IPCA+", "15/05/2035", datas, _passeio(600, 3000, 0.004, 1)),
                *curtissimo,
            ]
        ).encode("latin1")
    )

    with pytest.raises(ErroRendaFixa, match="abaixo do mínimo"):
        preparar(
            ampliado,
            [posicao(LONGO), posicao("tesouro_selic_2031-03-01")],
            confianca=0.95,
            janela=252,
            hoje=HOJE,
        )


# --------------------------------------------------------------------------- #
# Consolidado: acoes + renda fixa
# --------------------------------------------------------------------------- #

def precos_acoes(indice, semente=9):
    rng = np.random.default_rng(semente)
    return pd.DataFrame(
        {
            "PETR4.SA": 30 * np.cumprod(1 + rng.normal(0.0004, 0.02, len(indice))),
            "ITUB4.SA": 25 * np.cumprod(1 + rng.normal(0.0003, 0.015, len(indice))),
        },
        index=indice,
    )


def test_consolidado_pondera_as_duas_pernas_por_valor(quadro, book_longo):
    matriz_rf = book_longo["matriz"]
    junto = consolidar(
        precos_acoes=precos_acoes(matriz_rf.index),
        pesos_acoes={"PETR4.SA": 0.6, "ITUB4.SA": 0.4},
        valor_acoes=100_000.0,
        matriz_rf=matriz_rf,
        valores_rf=valores_marcados(book_longo["marcacao"]),
    )

    assert sum(junto["pesos"].values()) == pytest.approx(1.0, abs=1e-6)
    assert junto["valor_total"] == pytest.approx(100_000.0 + junto["valor_renda_fixa"])
    # a acao pesa a fatia dela dentro da perna de acoes, reescalada pelo total
    assert junto["pesos"]["PETR4.SA"] == pytest.approx(
        0.6 * 100_000.0 / junto["valor_total"], abs=1e-6
    )


def test_consolidado_nao_colide_nomes_de_coluna(quadro, book_longo):
    junto = consolidar(
        precos_acoes=precos_acoes(book_longo["matriz"].index),
        pesos_acoes={"PETR4.SA": 0.5, "ITUB4.SA": 0.5},
        valor_acoes=50_000.0,
        matriz_rf=book_longo["matriz"],
        valores_rf=valores_marcados(book_longo["marcacao"]),
    )

    assert list(junto["matriz"].columns) == ["PETR4.SA", "ITUB4.SA", LONGO]
    assert set(junto["pesos"]) == {"PETR4.SA", "ITUB4.SA", LONGO}
    # ticker de acao e maiusculo, id de titulo e slug minusculo: nao ha como colidir
    assert not set(book_longo["matriz"].columns) & set(precos_acoes(book_longo["matriz"].index).columns)


def test_consolidado_avisa_quando_os_calendarios_divergem(quadro, book_longo):
    matriz_rf = book_longo["matriz"]
    # bolsa negocia um dia a mais que a ultima data base publicada pelo Tesouro
    indice_bolsa = matriz_rf.index.append(
        pd.DatetimeIndex([matriz_rf.index[-1] + pd.Timedelta(days=1)])
    )
    junto = consolidar(
        precos_acoes=precos_acoes(indice_bolsa),
        pesos_acoes={"PETR4.SA": 1.0},
        valor_acoes=50_000.0,
        matriz_rf=matriz_rf,
        valores_rf=valores_marcados(book_longo["marcacao"]),
    )

    codigos = [a["codigo"] for a in junto["avisos"]]
    assert "calendarios_defasados" in codigos


def test_consolidado_roda_no_motor_das_acoes(quadro, book_longo):
    junto = consolidar(
        precos_acoes=precos_acoes(book_longo["matriz"].index),
        pesos_acoes={"PETR4.SA": 0.6, "ITUB4.SA": 0.4},
        valor_acoes=100_000.0,
        matriz_rf=book_longo["matriz"],
        valores_rf=valores_marcados(book_longo["marcacao"]),
    )
    saida = analisar(
        precos=junto["matriz"].dropna(how="any"),
        pesos=junto["pesos"],
        confianca=0.95,
        horizonte=1,
        janela=252,
        valor_carteira=junto["valor_total"],
    )

    assert saida["metodos"]["empirico"]["var_percentual"] > 0
    assert len(saida["book"]) == 3


def test_consolidado_sem_datas_em_comum_e_recusado(quadro, book_longo):
    outro_periodo = pd.bdate_range(start="2010-01-04", periods=100)

    with pytest.raises(ErroRendaFixa, match="datas em comum"):
        consolidar(
            precos_acoes=precos_acoes(outro_periodo),
            pesos_acoes={"PETR4.SA": 1.0},
            valor_acoes=50_000.0,
            matriz_rf=book_longo["matriz"],
            valores_rf=valores_marcados(book_longo["marcacao"]),
        )
