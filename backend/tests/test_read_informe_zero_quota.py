"""Teste isolado: _read_informe descarta VL_QUOTA <= 0.

Escrito à parte porque monta um ZIP sintético no formato exato do informe
diário da CVM — mantém o teste do módulo principal enxuto.
"""
import io
import zipfile

import pandas as pd
import pytest

from app.fundos.cvm_data import _read_informe


def _zip_informe(tmp_path, linhas):
    csv = (
        "CNPJ_FUNDO_CLASSE;DT_COMPTC;VL_QUOTA;VL_PATRIM_LIQ;NR_COTST\n"
        + "\n".join(linhas)
    )
    path = tmp_path / "inf_diario_fi_202601.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("inf_diario_fi_202601.csv", csv)
    return path


def test_read_informe_descarta_cota_zero_e_negativa(tmp_path):
    path = _zip_informe(tmp_path, [
        "11.111.111/0001-11;2026-01-02;1.5;1000000;100",
        "11.111.111/0001-11;2026-01-05;0.0;0;0",       # artefato: cota zerada
        "11.111.111/0001-11;2026-01-06;-1.0;0;0",      # artefato: negativa
        "11.111.111/0001-11;2026-01-07;1.52;1010000;101",
    ])
    df = _read_informe(path, extra_cols=["VL_PATRIM_LIQ", "NR_COTST"])

    assert len(df) == 2
    assert set(df["DT_COMPTC"]) == {"2026-01-02", "2026-01-07"}
    assert (df["VL_QUOTA"] > 0).all()
