"""API do modulo de risco — Celula de Risco, Inteli Finance.

Tres VaRs (empirico, parametrico, EWMA) sobre a mesma carteira, backtest de
violacoes para cada um e a relacao risco-retorno contra a Selic.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import renda_fixa as rf
from . import risco_retorno as rr
from . import titulos_publicos as tp
from .analise import analisar
from .data import ErroDeDados, baixar_precos, buscar_nome
from .schemas import (
    PedidoAnaliseRendaFixa,
    PedidoConsolidado,
    PedidoRendaFixa,
    PedidoVaR,
)
from .selic import ErroSelic, alinha_com_carteira, serie_selic, taxa_anual_para_diaria
from .var_core import retorno_carteira, retornos_simples
from .var_empirico import calcular

SELIC_PADRAO_ANUAL = 0.15  # usada so se o BCB falhar e o pedido nao trouxer taxa

app = FastAPI(
    title="Risco | VaR e risco-retorno",
    description=(
        "VaR empirico, parametrico e EWMA sobre precos do yfinance, com "
        "backtest de violacoes e indices de risco-retorno contra a Selic "
        "(serie 11 do BCB). Modulo da celula de risco do Inteli Finance."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["infra"])
def health() -> dict:
    return {"status": "ok", "modulo": "risco", "data": date.today().isoformat()}


@app.get("/api/ativo", tags=["dados"])
def ativo(ticker: str = Query(..., min_length=1, max_length=20)) -> dict:
    """Valida um ticker no yfinance e devolve o nome do ativo."""
    ticker = ticker.strip().upper()
    hoje = date.today()
    try:
        precos = baixar_precos([ticker], inicio=str(hoje.replace(year=hoje.year - 1)))
    except ErroDeDados as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "ticker": ticker,
        "nome": buscar_nome(ticker),
        "ultimo_preco": round(float(precos[ticker].iloc[-1]), 4),
        "ultima_data": precos.index[-1].strftime("%Y-%m-%d"),
    }


def _historico_tesouro() -> tp.Historico:
    """Historico do Tesouro, ou 503 se nao ha download nem cache."""
    try:
        return tp.carregar()
    except tp.ErroTesouro as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/titulos-publicos/disponiveis", tags=["renda fixa"])
def titulos_publicos_disponiveis() -> dict:
    """Universo do Tesouro Direto no ultimo dia util publicado.

    Um papel esta disponivel se aparece na ultima `Data Base` do arquivo e
    ainda nao venceu. A `data_base` vem no payload de proposito: e a data da
    marcacao, normalmente D-1, e a interface precisa dizer isso.
    """
    historico = _historico_tesouro()
    disponiveis = tp.universo(historico.quadro)
    if disponiveis.empty:
        raise HTTPException(
            status_code=503,
            detail=(
                "O arquivo do Tesouro nao trouxe nenhum titulo disponivel na "
                f"data base de {historico.data_base_max:%d/%m/%Y}."
            ),
        )

    return {
        "data_base": historico.data_base_max.strftime("%Y-%m-%d"),
        "quantidade": int(len(disponiveis)),
        "titulos": tp.serializa_universo(disponiveis),
        "fonte": historico.meta(),
    }


@app.post("/api/renda-fixa/marcacao", tags=["renda fixa"])
def renda_fixa_marcacao(pedido: PedidoRendaFixa) -> dict:
    """Marca o book de renda fixa a mercado pelo PU de venda.

    Uma linha por posicao com PU de aquisicao, PU de marcacao, valor marcado,
    P&L em reais e em percentual, e a data base — tudo explicito, para a
    marcacao aparecer na interface em vez de ficar implicita no calculo.
    """
    historico = _historico_tesouro()
    try:
        marcacao = rf.marcar(historico.quadro, pedido.posicoes)
    except rf.ErroRendaFixa as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    marcacao["fonte"] = historico.meta()
    return marcacao


def _carrega_precos(pedido: PedidoVaR) -> pd.DataFrame:
    pesos = pedido.pesos_normalizados()
    try:
        precos = baixar_precos(
            tickers=list(pesos.keys()),
            inicio=pedido.inicio.isoformat(),
            fim=pedido.fim.isoformat() if pedido.fim else None,
        )
    except ErroDeDados as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if len(precos) <= pedido.janela + 10:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Ha {len(precos)} pregoes no periodo, insuficiente para uma janela "
                f"de {pedido.janela} dias. Amplie o periodo ou reduza a janela."
            ),
        )
    return precos


def _selic_alinhada(
    indice: pd.DatetimeIndex, selic_anual: float | None
) -> tuple[pd.Series, dict]:
    """Selic do BCB no calendario da serie, ou taxa fixa se o SGS falhar.

    Devolve tambem a procedencia, que sobe no payload para a interface poder
    dizer de onde saiu a taxa livre de risco.
    """
    try:
        selic = alinha_com_carteira(
            serie_selic(indice[0].date(), indice[-1].date()), indice
        )
        return selic, {
            "fonte_taxa": "bcb-sgs-11",
            "observacao_taxa": "Selic diária, série 11 do Banco Central.",
            "detalhe_taxa": None,
        }
    except ErroSelic as exc:
        taxa = selic_anual or SELIC_PADRAO_ANUAL
        selic = pd.Series(taxa_anual_para_diaria(taxa), index=indice, name="selic")
        return selic, {
            "fonte_taxa": "taxa-fixa",
            "observacao_taxa": f"BCB indisponível — taxa fixa de {taxa * 100:.2f}% a.a.",
            "detalhe_taxa": str(exc),
        }


def _bloco_risco_retorno(
    ret_carteira: pd.Series, janela: int, selic_anual: float | None
) -> tuple[dict, pd.Series]:
    """Sharpe/Sortino contra a Selic, com queda para taxa fixa se o BCB falhar.

    Devolve o bloco e a serie da Selic, que as metricas por titulo reaproveitam
    em vez de consultar o BCB de novo.
    """
    selic, procedencia = _selic_alinhada(ret_carteira.index, selic_anual)
    saida = rr.calcular(ret_carteira, selic, janela_rolling=janela)
    saida.update(procedencia)
    return saida, selic


@app.post("/api/analise", tags=["analise"])
def analise(pedido: PedidoVaR) -> dict:
    """Payload completo: os tres VaRs, o book e a relacao risco-retorno."""
    precos = _carrega_precos(pedido)
    ret_carteira = retorno_carteira(retornos_simples(precos), pedido.pesos_normalizados())
    bloco, _ = _bloco_risco_retorno(ret_carteira, pedido.janela, pedido.selic_anual)
    try:
        return analisar(
            precos=precos,
            pesos=pedido.pesos_normalizados(),
            confianca=pedido.confianca,
            horizonte=pedido.horizonte,
            janela=pedido.janela,
            valor_carteira=pedido.valor_carteira,
            risco_retorno=bloco,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Falha no calculo: {exc}") from exc


@app.post("/api/analise/renda-fixa", tags=["renda fixa"])
def analise_renda_fixa(pedido: PedidoAnaliseRendaFixa) -> dict:
    """Os tres VaRs, Sharpe e Sortino sobre o book de renda fixa.

    Mesmo contrato de `/api/analise`, para as abas de metricas nao precisarem
    saber de que classe de ativo vieram os numeros. Acrescenta tres blocos:
    `marcacao` (a marcacao a mercado do passo anterior), `por_titulo`
    (metricas de cada papel isolado) e `avisos` (amostra curta e afins).
    """
    historico = _historico_tesouro()
    try:
        preparado = rf.preparar(
            historico.quadro,
            pedido.posicoes,
            confianca=pedido.confianca,
            janela=pedido.janela,
            inicio=pedido.inicio,
            fim=pedido.fim,
        )
    except rf.ErroRendaFixa as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    matriz, pesos = preparado["matriz"], preparado["pesos"]
    valor = preparado["valor_marcado"]

    ret_carteira = retorno_carteira(retornos_simples(matriz), pesos)
    bloco, selic = _bloco_risco_retorno(ret_carteira, pedido.janela, pedido.selic_anual)

    try:
        saida = analisar(
            precos=matriz.dropna(how="any"),
            pesos=pesos,
            confianca=pedido.confianca,
            horizonte=pedido.horizonte,
            janela=pedido.janela,
            valor_carteira=valor,
            risco_retorno=bloco,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Falha no calculo: {exc}") from exc

    por_titulo, avisos_titulos = rf.metricas_por_titulo(
        matriz, preparado["marcacao"], selic, pedido.confianca,
        pedido.horizonte, pedido.janela,
    )
    # com um papel só, o book É o papel: o aviso agregado repetiria o do titulo
    avisos_book = (
        rf.avisos_do_backtest(
            saida["metodos"]["empirico"]["backtest"]["resumo"],
            pedido.confianca,
            pedido.janela,
            len(ret_carteira),
        )
        if len(pedido.posicoes) > 1
        else []
    )
    avisos = preparado["avisos"] + avisos_titulos + avisos_book

    saida["classe"] = "renda-fixa"
    saida["marcacao"] = preparado["marcacao"]
    saida["por_titulo"] = por_titulo
    saida["avisos"] = avisos
    saida["fonte"] = historico.meta()
    return saida


@app.post("/api/analise/consolidado", tags=["renda fixa"])
def analise_consolidada(pedido: PedidoConsolidado) -> dict:
    """Book inteiro: acoes e renda fixa ponderadas por valor de mercado.

    O motor e o mesmo — basta uma matriz de precos com as duas classes lado a
    lado. So entram as datas em que a bolsa e o Tesouro publicaram, entao a
    defasagem do arquivo do Tesouro encurta a ponta recente; isso vem
    sinalizado em `avisos`.
    """
    historico = _historico_tesouro()

    try:
        precos_acoes = baixar_precos(
            tickers=list(pedido.pesos_acoes().keys()),
            inicio=(pedido.inicio or date.today().replace(year=date.today().year - 3)).isoformat(),
            fim=pedido.fim.isoformat() if pedido.fim else None,
        )
    except ErroDeDados as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        preparado = rf.preparar(
            historico.quadro,
            pedido.renda_fixa,
            confianca=pedido.confianca,
            janela=pedido.janela,
            inicio=pedido.inicio,
            fim=pedido.fim,
        )
        junto = rf.consolidar(
            precos_acoes=precos_acoes,
            pesos_acoes=pedido.pesos_acoes(),
            valor_acoes=pedido.valor_carteira,
            matriz_rf=preparado["matriz"],
            valores_rf=rf.valores_marcados(preparado["marcacao"]),
        )
    except rf.ErroRendaFixa as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    matriz = junto["matriz"].dropna(how="any")
    ret_carteira = retorno_carteira(retornos_simples(matriz), junto["pesos"])
    bloco, _ = _bloco_risco_retorno(ret_carteira, pedido.janela, pedido.selic_anual)

    try:
        saida = analisar(
            precos=matriz,
            pesos=junto["pesos"],
            confianca=pedido.confianca,
            horizonte=pedido.horizonte,
            janela=pedido.janela,
            valor_carteira=junto["valor_total"],
            risco_retorno=bloco,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Falha no calculo: {exc}") from exc

    saida["classe"] = "consolidado"
    saida["marcacao"] = preparado["marcacao"]
    saida["composicao"] = {
        "valor_acoes": junto["valor_acoes"],
        "valor_renda_fixa": junto["valor_renda_fixa"],
        "valor_total": junto["valor_total"],
        "peso_acoes": round(junto["valor_acoes"] / junto["valor_total"], 6),
        "peso_renda_fixa": round(junto["valor_renda_fixa"] / junto["valor_total"], 6),
    }
    saida["avisos"] = junto["avisos"] + rf.avisos_do_backtest(
        saida["metodos"]["empirico"]["backtest"]["resumo"],
        pedido.confianca,
        pedido.janela,
        len(ret_carteira),
    )
    saida["fonte"] = historico.meta()
    return saida


@app.post("/api/var/empirico", tags=["var"])
def var_empirico_endpoint(pedido: PedidoVaR) -> dict:
    """Somente o VaR empirico — mantido para quem ja consome este contrato."""
    precos = _carrega_precos(pedido)
    try:
        saida = calcular(
            precos=precos,
            pesos=pedido.pesos_normalizados(),
            confianca=pedido.confianca,
            horizonte=pedido.horizonte,
            janela=pedido.janela,
            valor_carteira=pedido.valor_carteira,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Falha no calculo: {exc}") from exc
    saida["metodo"] = "empirico"
    return saida
