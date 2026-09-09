"""Endpoints do modulo Fundos - busca, ranking e analise de fundos CVM.

Mesmo padrao dos endpoints de VaR em app/main.py: funcoes `def` sincronas
(FastAPI roda em threadpool automaticamente, entao o ThreadPoolExecutor
interno de `cvm_data` nao bloqueia o event loop) e excecoes de negocio viram
HTTPException com o motivo em texto simples.
"""

from __future__ import annotations

import requests
from fastapi import APIRouter, HTTPException, Query

from . import cvm_data as cvm
from .metrics import metrics_mensais

router = APIRouter(prefix="/api/fundos", tags=["fundos"])

JANELAS_PADRAO = (6, 12, 24, 36)
MIN_MESES_COMPARATIVO = 12

CVM_INDISPONIVEL = (
    "Nao foi possivel obter o registro de fundos da CVM (servico fora do ar ou rede "
    "indisponivel). Tente novamente em alguns instantes."
)


def _load_registry():
    try:
        return cvm.load_registry()
    except requests.RequestException:
        raise HTTPException(status_code=503, detail=CVM_INDISPONIVEL)


@router.get("/status")
def status() -> dict:
    return {"ultima_atualizacao": cvm.ultima_atualizacao()}


@router.get("/buscar")
def buscar(q: str = Query(..., min_length=2, max_length=120)) -> list[dict]:
    """Busca fundos ativos pelo nome (case-insensitive)."""
    registry = _load_registry()
    resultado = cvm.search_funds(q, registry, limit=40)
    return [
        {"cnpj": row["cnpj_fmt"], "nome": row["Denominacao_Social"]}
        for row in resultado.to_dict(orient="records")
    ]


@router.get("/top10")
def top10(anos: int = Query(1, ge=1, le=3)) -> list[dict]:
    """Top 10 fundos por retorno acumulado nos ultimos `anos` anos, entre
    os com pelo menos 100 cotistas e sem saltos mensais suspeitos."""
    try:
        resultado = cvm.top_funds_by_return(anos, top_n=10)
    except requests.RequestException:
        raise HTTPException(status_code=503, detail=CVM_INDISPONIVEL)
    if resultado.empty:
        return []
    return [
        {
            "cnpj": row["cnpj_fmt"],
            "nome": row["Denominacao_Social"],
            "retorno_%": round(float(row["retorno_%"]), 2),
            "patrimonio_mi": round(float(row["patrimonio_mi"]), 1),
            "cotistas": int(row["cotistas"]),
        }
        for row in resultado.to_dict(orient="records")
    ]


@router.get("/analise")
def analise(
    cnpj: str = Query(..., min_length=14, max_length=20),
    meses: int = Query(24, ge=2, le=120, description="Janela de analise, em meses fechados"),
) -> dict:
    """Payload completo de um fundo: metricas por janela, serie mensal
    (fundo/CDI/Ibovespa) e resumo do periodo pedido."""
    registry = _load_registry()
    nome = cvm.fund_by_cnpj(cnpj, registry)
    if nome is None:
        raise HTTPException(
            status_code=404,
            detail="CNPJ nao encontrado entre os fundos ativos com dados recentes na CVM.",
        )

    months, fund_list = cvm.fetch_fund_monthly_returns(cnpj, meses)
    if not fund_list:
        raise HTTPException(
            status_code=400,
            detail=(
                "Nao foi possivel obter historico de cotas para esse fundo no periodo "
                "selecionado. O fundo pode ser novo demais ou os dados ainda nao foram "
                "publicados pela CVM - tente reduzir a janela de analise."
            ),
        )

    n_disp = len(fund_list)
    if n_disp < 2:
        raise HTTPException(
            status_code=400,
            detail="Historico curto demais para calcular metricas (minimo de 2 meses fechados).",
        )

    try:
        cdi_list = cvm.fetch_cdi_monthly(months)
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Nao foi possivel obter a serie do CDI no Banco Central. Tente novamente em "
            "alguns instantes.",
        )

    comparativo_disponivel = n_disp >= MIN_MESES_COMPARATIVO
    ibov_list = cvm.fetch_ibovespa_monthly(months) if comparativo_disponivel else []

    janelas = [
        metrics_mensais(w, fund_list, cdi_list, months) for w in JANELAS_PADRAO if w <= n_disp
    ]
    resumo = metrics_mensais(n_disp, fund_list, cdi_list, months)

    serie_mensal = [
        {
            "ano": y,
            "mes": m,
            "fundo_%": fv,
            "cdi_%": cv,
            "ibov_%": (ibov_list[i] if comparativo_disponivel else None),
        }
        for i, ((y, m), fv, cv) in enumerate(zip(months, fund_list, cdi_list))
    ]

    return {
        "fundo": {"cnpj": cnpj, "nome": nome},
        "meses_pedidos": meses,
        "meses_disponiveis": n_disp,
        "comparativo_disponivel": comparativo_disponivel,
        "serie_mensal": serie_mensal,
        "resumo": resumo,
        "janelas": janelas,
    }


@router.post("/atualizar")
def atualizar() -> dict:
    """Forca a proxima consulta a rebaixar/reprocessar o que pode ter
    mudado (registro + os meses ainda sujeitos a revisao da CVM)."""
    cvm.limpar_cache()
    return {
        "status": "ok",
        "mensagem": "Cache de fundos limpo - a proxima consulta rebaixa o que puder ter mudado.",
    }
