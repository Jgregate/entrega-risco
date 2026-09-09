"""Testes do modulo Fundos: metricas mensais, formatacao de CNPJ e o filtro
de ranking (salto suspeito / minimo de cotistas) - tudo sem rede, com
DataFrames e listas sinteticas, no mesmo espirito de test_risco_retorno.py.
"""

import pandas as pd
import pytest

from app.fundos.cvm_data import _cnpj_fmt, _ranking_a_partir_de
from app.fundos.metrics import metrics_mensais


def test_cnpj_fmt_formata_14_digitos():
    assert _cnpj_fmt(40212883000118) == "40.212.883/0001-18"
    assert _cnpj_fmt("40212883000118") == "40.212.883/0001-18"


def test_metrics_mensais_retorno_acumulado_e_juros_compostos():
    months = [(2025, 1), (2025, 2), (2025, 3)]
    fund_list = [10.0, 10.0, 10.0]  # 10% ao mes
    cdi_list = [1.0, 1.0, 1.0]

    saida = metrics_mensais(3, fund_list, cdi_list, months)

    esperado = ((1.10 ** 3) - 1) * 100
    assert saida["retorno_acumulado_%"] == pytest.approx(esperado, abs=1e-2)
    assert saida["janela_meses"] == 3
    assert saida["periodo"] == "01/2025 a 03/2025"


def test_metrics_mensais_usa_so_os_ultimos_n_meses():
    months = [(2024, 1), (2024, 2), (2024, 3), (2024, 4)]
    fund_list = [50.0, 0.0, 1.0, 1.0]  # o salto de 50% fica fora da janela de 2
    cdi_list = [0.0, 0.0, 0.5, 0.5]

    saida = metrics_mensais(2, fund_list, cdi_list, months)

    esperado = ((1.01 ** 2) - 1) * 100
    assert saida["retorno_acumulado_%"] == pytest.approx(esperado, abs=1e-2)
    assert saida["periodo"] == "03/2024 a 04/2024"


def test_metrics_mensais_sharpe_positivo_quando_fundo_bate_cdi_de_forma_consistente():
    months = [(2025, m) for m in range(1, 13)]
    fund_list = [1.2] * 12
    cdi_list = [0.9] * 12

    saida = metrics_mensais(12, fund_list, cdi_list, months)

    assert saida["sharpe"] is not None
    assert saida["sharpe"] > 0


def _quotas(dados: dict[str, list[float]], months) -> pd.DataFrame:
    """dados: {cnpj_fmt: [cota_mes0, cota_mes1, ...]} -> DataFrame no
    formato que `_ranking_a_partir_de` espera (colunas = (ano, mes))."""
    return pd.DataFrame(dados, index=months).T[months]


def test_ranking_exclui_fundo_com_salto_mensal_suspeito():
    months = [(2024, 1), (2024, 2), (2024, 3)]
    quotas = _quotas(
        {
            "11.111.111/0001-11": [100.0, 110.0, 121.0],  # +10%/mes, sem salto -> 21%
            "22.222.222/0001-22": [100.0, 250.0, 260.0],  # +150% no 1o mes -> excluido
        },
        months,
    )
    snap_final = pd.DataFrame(
        {"VL_PATRIM_LIQ": [1e8, 1e8], "NR_COTST": [500, 500]},
        index=["11.111.111/0001-11", "22.222.222/0001-22"],
    )
    registry = pd.DataFrame(
        {
            "cnpj_fmt": ["11.111.111/0001-11", "22.222.222/0001-22"],
            "Denominacao_Social": ["Fundo Normal", "Fundo Com Salto"],
        }
    )

    resultado = _ranking_a_partir_de(quotas, snap_final, registry, 100, 80.0, 10)

    assert list(resultado["cnpj_fmt"]) == ["11.111.111/0001-11"]
    assert resultado.iloc[0]["retorno_%"] == pytest.approx(21.0, abs=1e-6)


def test_ranking_exclui_fundo_com_poucos_cotistas():
    months = [(2024, 1), (2024, 2)]
    quotas = _quotas(
        {
            "11.111.111/0001-11": [100.0, 130.0],  # +30%, mas so 50 cotistas
            "22.222.222/0001-22": [100.0, 105.0],  # +5%, 300 cotistas
        },
        months,
    )
    snap_final = pd.DataFrame(
        {"VL_PATRIM_LIQ": [1e6, 5e7], "NR_COTST": [50, 300]},
        index=["11.111.111/0001-11", "22.222.222/0001-22"],
    )
    registry = pd.DataFrame(
        {
            "cnpj_fmt": ["11.111.111/0001-11", "22.222.222/0001-22"],
            "Denominacao_Social": ["Fundo Exclusivo", "Fundo Aberto"],
        }
    )

    resultado = _ranking_a_partir_de(quotas, snap_final, registry, 100, 80.0, 10)

    assert list(resultado["cnpj_fmt"]) == ["22.222.222/0001-22"]


def test_ranking_ordena_por_retorno_decrescente_e_respeita_top_n():
    months = [(2024, 1), (2024, 2)]
    quotas = _quotas(
        {
            "11.111.111/0001-11": [100.0, 105.0],  # +5%
            "22.222.222/0001-22": [100.0, 120.0],  # +20%
            "33.333.333/0001-33": [100.0, 110.0],  # +10%
        },
        months,
    )
    snap_final = pd.DataFrame(
        {"VL_PATRIM_LIQ": [1e8] * 3, "NR_COTST": [500] * 3},
        index=quotas.index,
    )
    registry = pd.DataFrame(
        {
            "cnpj_fmt": list(quotas.index),
            "Denominacao_Social": ["A", "B", "C"],
        }
    )

    resultado = _ranking_a_partir_de(quotas, snap_final, registry, 100, 80.0, top_n=2)

    assert list(resultado["cnpj_fmt"]) == ["22.222.222/0001-22", "33.333.333/0001-33"]
    assert len(resultado) == 2
