"""Endpoints do modulo Fundos.

Dois modulos de produto, um roteador:

  /api/fundos/*   analise individual - cadastro, performance, risco, carteira
  /api/book/*     consolidacao de uma carteira de fundos

Mesmo padrao dos endpoints de VaR em app/main.py: funcoes `def` sincronas
(FastAPI as roda em threadpool, entao o ThreadPoolExecutor interno de
`cvm_data` nao bloqueia o event loop) e excecoes de negocio viram
HTTPException com o motivo em texto simples.

Uma nota sobre CNPJ na URL: ele vai sempre como query string, nunca como path
param - CNPJ formatado tem barra (`00.000.000/0001-00`) e quebraria a rota.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import requests
from fastapi import APIRouter, HTTPException, Query

from . import analytics, book as book_mod, carteira, cvm_data as cvm, indices, sobre
from . import cadastro as cadastro_mod
from .cadastro import cnpj_formatado
from .schemas import PedidoBook

router = APIRouter(prefix="/api/fundos", tags=["fundos"])
router_book = APIRouter(prefix="/api/book", tags=["book"])

# Historico minimo carregado em qualquer analise. Cobre todas as janelas
# rapidas ate 5 anos de uma vez so; "Desde o inicio" e o unico periodo que
# pode pedir mais que isso, e so quando o fundo for mais velho.
MESES_BASE = 60

CVM_INDISPONIVEL = (
    "Não foi possível obter os dados da CVM (serviço fora do ar ou rede "
    "indisponível). Tente novamente em alguns instantes."
)


def _load_registry():
    try:
        return cvm.load_registry()
    except requests.RequestException:
        raise HTTPException(status_code=503, detail=CVM_INDISPONIVEL)


def _cadastro(cnpj: str) -> dict:
    try:
        dados = cvm.cadastro_fundo(cnpj)
    except requests.RequestException:
        raise HTTPException(status_code=503, detail=CVM_INDISPONIVEL)
    if dados is None:
        raise HTTPException(
            status_code=404,
            detail="CNPJ não encontrado no cadastro de classes de fundos da CVM.",
        )
    return dados


def _meses_do_periodo(periodo: str) -> int | None:
    spec = analytics.PERIODOS_POR_CHAVE.get(periodo)
    if spec is None:
        raise HTTPException(
            status_code=400,
            detail=f"Período inválido. Use um de: "
                   f"{', '.join(analytics.PERIODOS_POR_CHAVE)}.",
        )
    return spec["meses"]


def _carrega_cotas(
    cnpj: str, cadastro: dict, periodo: str, inicio: date | None = None
) -> pd.DataFrame:
    """Serie diaria do fundo, com historico suficiente para o periodo pedido.

    Carrega sempre pelo menos MESES_BASE para as janelas rapidas da tela nao
    ficarem vazias so porque o usuario abriu o fundo em "1 mês". Um `inicio`
    explicito (intervalo personalizado) so amplia a janela, nunca encurta.

    `cadastro` fica no parametro por compatibilidade de chamada, mas
    deliberadamente NAO define o inicio da busca — ver o docstring de
    `cvm.serie_diaria` para o porque de nao confiar na data de registro da
    classe como piso do historico.
    """
    meses = _meses_do_periodo(periodo)

    if meses is None:
        quadro = cvm.serie_diaria(cnpj, inicio=None)
    else:
        # +1 mes de folga para o primeiro retorno da janela ter pregao anterior
        alvo = max(meses + 1, MESES_BASE)
        ano, mes = cvm._mes_n_atras(alvo - 1)
        piso = date(ano, mes, 1)
        if inicio is not None and inicio < piso:
            piso = date(inicio.year, inicio.month, 1)
        quadro = cvm.serie_diaria(cnpj, inicio=piso)

    if quadro.empty:
        raise HTTPException(
            status_code=400,
            detail=(
                "Não há histórico de cotas publicado pela CVM para esse fundo no "
                "período. O fundo pode ser novo demais, estar em fase pré-operacional "
                "ou não ter reportado informes diários."
            ),
        )
    return quadro.set_index("data").sort_index()


def _benchmark_do_fundo(cadastro: dict, pedido: str | None) -> tuple[str | None, bool]:
    """(chave do benchmark, veio do cadastro?)."""
    if pedido:
        if pedido not in indices.BENCHMARKS:
            raise HTTPException(status_code=400, detail=f"Benchmark desconhecido: {pedido}.")
        return pedido, False
    do_cadastro = indices.chave_do_cadastro(cadastro.get("benchmark"))
    return (do_cadastro, True) if do_cadastro else ("cdi", False)


# --------------------------------------------------------------------------- #
# Descoberta
# --------------------------------------------------------------------------- #

@router.get("/status")
def status() -> dict:
    return {
        "ultima_atualizacao": cvm.ultima_atualizacao(),
        "max_meses_historico": cvm.MAX_MESES_HISTORICO,
    }


@router.get("/periodos")
def periodos(escopo: str = Query("analise")) -> list[dict]:
    """Periodos rapidos da interface - a lista vive no backend para as telas
    nunca divergirem.

    `escopo=ranking` devolve o subconjunto que o ranking consegue calcular:
    ele le cotas mensais do mercado inteiro, entao nao oferece "desde o
    inicio" (cada fundo comecou numa data diferente).
    """
    fonte = analytics.PERIODOS_RANKING if escopo == "ranking" else analytics.PERIODOS
    return [dict(p) for p in fonte]


@router.get("/categorias")
def categorias() -> list[dict]:
    """Categorias de fundo oferecidas como filtro do ranking."""
    return [dict(c) for c in cadastro_mod.CATEGORIAS]


@router.get("/benchmarks")
def benchmarks() -> list[dict]:
    return indices.catalogo()


@router.get("/buscar")
def buscar(q: str = Query(..., min_length=2, max_length=120)) -> list[dict]:
    """Busca por nome, CNPJ, código CVM ou gestora."""
    registry = _load_registry()
    resultado = cvm.search_funds(q, registry, limit=40)
    return [
        {
            "cnpj": row["cnpj_fmt"],
            "nome": row["Denominacao_Social"],
            "gestora": row.get("gestora"),
            "codigo_cvm": row.get("codigo_cvm"),
        }
        for row in resultado.to_dict(orient="records")
    ]


@router.get("/top10")
def top10(
    periodo: str = Query("12m"),
    categoria: str | None = Query(None),
) -> list[dict]:
    """Top 10 por retorno acumulado na janela escolhida, entre fundos com pelo
    menos 100 cotistas e sem saltos mensais suspeitos.

    Volatilidade, drawdown e Sharpe sao calculados na MESMA janela do retorno,
    a partir das cotas mensais - trocar o periodo recalcula tudo.
    """
    if periodo not in analytics.CHAVES_RANKING:
        raise HTTPException(
            status_code=400,
            detail=f"Período inválido para o ranking. Use um de: "
                   f"{', '.join(analytics.CHAVES_RANKING)}.",
        )
    if categoria is not None and categoria not in cadastro_mod.CATEGORIAS_POR_CHAVE:
        raise HTTPException(
            status_code=400,
            detail=f"Categoria desconhecida: {categoria}.",
        )

    meses = analytics.PERIODOS_POR_CHAVE[periodo]["meses"]
    try:
        resultado = cvm.top_funds_by_return(meses, top_n=10, categoria=categoria)
    except requests.RequestException:
        raise HTTPException(status_code=503, detail=CVM_INDISPONIVEL)
    if resultado.empty:
        return []
    return [
        {
            "cnpj": row["cnpj_fmt"],
            "nome": row["Denominacao_Social"],
            "gestora": row.get("gestora"),
            "categoria": cadastro_mod.rotulo_categoria(row.get("categoria")),
            "retorno_%": round(float(row["retorno_%"]), 2),
            "volatilidade_%": analytics._limpa(row.get("volatilidade_%")),
            "drawdown_%": analytics._limpa(row.get("drawdown_%")),
            "sharpe": analytics._limpa(row.get("sharpe")),
            "patrimonio_mi": round(float(row["patrimonio_mi"]), 1),
            "cotistas": int(row["cotistas"]),
        }
        for row in resultado.to_dict(orient="records")
    ]


@router.get("/cadastro")
def cadastro_endpoint(cnpj: str = Query(..., min_length=14, max_length=20)) -> dict:
    """Informacoes institucionais da classe. Campo ausente vem como null - a
    interface mostra a lacuna, nao um valor inventado."""
    return _cadastro(cnpj_formatado(cnpj))


# --------------------------------------------------------------------------- #
# Analise individual
# --------------------------------------------------------------------------- #

@router.get("/analise")
def analise(
    cnpj: str = Query(..., min_length=14, max_length=20),
    periodo: str = Query("12m"),
    benchmark: str | None = Query(None),
    inicio: date | None = Query(None, description="Início de um intervalo personalizado"),
    fim: date | None = Query(None, description="Fim de um intervalo personalizado"),
) -> dict:
    """Payload completo da tela de analise individual.

    O recorte sai de `periodo` (janela rapida) ou de `inicio`/`fim` (intervalo
    personalizado); informar os dois faz o intervalo prevalecer.
    """
    cnpj = cnpj_formatado(cnpj)
    if inicio and fim and inicio >= fim:
        raise HTTPException(status_code=400, detail="A data inicial tem que ser anterior à final.")

    cadastro = _cadastro(cnpj)
    personalizado = bool(inicio or fim)
    quadro = _carrega_cotas(cnpj, cadastro, periodo, inicio)

    cotas_todas = quadro["vl_quota"]
    meses = _meses_do_periodo(periodo)
    cotas = (
        analytics.recorta_datas(cotas_todas, inicio, fim)
        if personalizado
        else analytics.recorta(cotas_todas, meses)
    )
    retornos = analytics.retornos_diarios(cotas)

    if retornos.empty:
        raise HTTPException(
            status_code=400,
            detail="Período curto demais: o fundo não tem dois pregões publicados nessa janela.",
        )

    chave_bench, do_cadastro = _benchmark_do_fundo(cadastro, benchmark)
    serie_bench = indices.retornos_benchmark(chave_bench, retornos.index)
    serie_cdi = (
        serie_bench if chave_bench == "cdi"
        else indices.retornos_benchmark("cdi", retornos.index)
    )

    bench_ok = not serie_bench.empty
    avisos = []
    if not bench_ok:
        avisos.append(
            f"A série do benchmark ({indices.rotulo(chave_bench)}) não pôde ser obtida "
            f"agora; os indicadores relativos ao benchmark ficam indisponíveis."
        )
    if serie_cdi.empty:
        avisos.append("A série do CDI não pôde ser obtida; Sharpe e Sortino ficam indisponíveis.")

    # as janelas rapidas usam TODO o historico carregado, nao o recorte -
    # senao "12 meses" mudaria de valor conforme o periodo selecionado
    janelas = analytics.retornos_por_janela(
        cotas_todas,
        indices.retornos_benchmark(chave_bench, analytics.retornos_diarios(cotas_todas).index),
        indices.retornos_benchmark("cdi", analytics.retornos_diarios(cotas_todas).index),
    )

    quadro_periodo = quadro.loc[cotas.index]
    extras = {}
    if bench_ok:
        extras["benchmark"] = serie_bench
    if not serie_cdi.empty and chave_bench != "cdi":
        extras["cdi"] = serie_cdi

    metricas = analytics.metricas(
        retornos,
        serie_bench if bench_ok else None,
        serie_cdi if not serie_cdi.empty else None,
    )
    pl_atual = quadro["vl_patrim_liq"].dropna()
    cotistas = quadro["nr_cotst"].dropna()

    return {
        "fundo": cadastro,
        "sobre": sobre.perfil(cadastro),
        "periodo": {
            "chave": "personalizado" if personalizado else periodo,
            "rotulo": (
                "Intervalo personalizado"
                if personalizado
                else analytics.PERIODOS_POR_CHAVE[periodo]["rotulo"]
            ),
            "personalizado": personalizado,
            "inicio": retornos.index[0].strftime("%Y-%m-%d"),
            "fim": retornos.index[-1].strftime("%Y-%m-%d"),
            "pregoes": int(len(retornos)),
            "historico_desde": quadro.index[0].strftime("%Y-%m-%d"),
        },
        "benchmark": {
            "chave": chave_bench,
            "rotulo": indices.rotulo(chave_bench),
            "do_cadastro": do_cadastro,
            "indicador_cvm": cadastro.get("benchmark"),
            "disponivel": bench_ok,
        },
        "metricas": metricas,
        "janelas": janelas,
        "serie": analytics.serie_para_json(retornos, extras),
        "tabela_mensal": analytics.tabela_mensal(retornos, serie_bench if bench_ok else None),
        "consistencia": analytics.consistencia(retornos, serie_bench if bench_ok else None),
        "drawdown": analytics.resumo_drawdown(retornos),
        "patrimonio": {
            "serie": analytics.serie_patrimonio(quadro_periodo),
            "atual": analytics._limpa(pl_atual.iloc[-1]) if len(pl_atual) else None,
            "medio_12m": analytics.patrimonio_medio(quadro),
            "cotistas": int(cotistas.iloc[-1]) if len(cotistas) else None,
            "data": quadro.index[-1].strftime("%Y-%m-%d"),
        },
        "variacao_anterior": {
            "retorno_12m": analytics.variacao_periodo_anterior(cotas_todas, 12),
        },
        "avisos": avisos,
    }


@router.get("/composicao")
def composicao(cnpj: str = Query(..., min_length=14, max_length=20)) -> dict:
    """Composicao da carteira do fundo no mes mais recente do CDA.

    A primeira chamada apos o cache vencer processa o ZIP mensal inteiro (uns
    300 MB de CSV) para TODOS os fundos; as seguintes sao instantaneas. Ver
    `carteira.py` para o porque dessa escolha.
    """
    cnpj = cnpj_formatado(cnpj)
    conn = cvm._connect()
    try:
        if carteira.precisa_rebaixar(conn, cvm.ATUALIZACAO_HORAS):
            # o CDA sai com defasagem maior e variavel que o informe diario
            candidatos = [cvm._mes_n_atras(n) for n in range(0, 6)]
            carteira.ingere(conn, candidatos)
        dados = carteira.composicao(conn, cnpj)
    finally:
        conn.close()

    if dados is None:
        return {
            "disponivel": False,
            "motivo": (
                "A CVM ainda não publicou a composição de carteira (CDA) desse fundo "
                "para o mês mais recente disponível."
            ),
        }
    return {"disponivel": True, **dados}


@router.post("/atualizar")
def atualizar() -> dict:
    """Forca a proxima consulta a rebaixar/reprocessar o que pode ter mudado
    (cadastro, carteiras e os meses ainda sujeitos a revisao da CVM)."""
    cvm.limpar_cache()
    return {
        "status": "ok",
        "mensagem": "Cache limpo — a próxima consulta rebaixa o que puder ter mudado.",
    }


# --------------------------------------------------------------------------- #
# Book
# --------------------------------------------------------------------------- #

def _series_do_book(cnpjs: list[str], meses: int | None) -> dict[str, pd.Series]:
    """Serie de cotas de todos os fundos do book, numa leitura so por mes."""
    if meses is None:
        quadro = cvm.serie_diaria(cnpjs, inicio=None)
    else:
        ano, mes = cvm._mes_n_atras(max(meses + 1, 13) - 1)
        quadro = cvm.serie_diaria(cnpjs, inicio=date(ano, mes, 1))

    if quadro.empty:
        return {}
    return {
        cnpj: grupo.set_index("data")["vl_quota"].sort_index()
        for cnpj, grupo in quadro.groupby("cnpj_fmt")
    }


@router_book.post("/analise")
def analise_book(pedido: PedidoBook) -> dict:
    """Consolida as posicoes informadas numa carteira unica."""
    meses = _meses_do_periodo(pedido.periodo)
    cnpjs = [p.cnpj for p in pedido.posicoes]
    if len(set(cnpjs)) != len(cnpjs):
        raise HTTPException(status_code=400, detail="Há CNPJs repetidos no book.")

    series = _series_do_book(cnpjs, meses)
    if not series:
        raise HTTPException(
            status_code=400,
            detail="Nenhum dos fundos informados tem histórico de cotas publicado na CVM.",
        )

    itens: list[dict] = []
    posicoes_calculo: list[dict] = []
    ignorados: list[dict] = []

    for entrada in pedido.posicoes:
        serie_completa = series.get(entrada.cnpj)
        if serie_completa is None or serie_completa.empty:
            ignorados.append({"cnpj": entrada.cnpj, "motivo": "sem histórico de cotas na CVM"})
            continue

        serie = analytics.recorta(serie_completa, meses)
        dados = entrada.model_dump()
        dados["data_entrada"] = (
            entrada.data_entrada.isoformat() if entrada.data_entrada else None
        )
        resolvida = book_mod.resolve_posicao(dados, serie)
        if resolvida is None:
            ignorados.append({
                "cnpj": entrada.cnpj,
                "motivo": "informe a quantidade de cotas ou o valor investido",
            })
            continue

        cad = cvm.cadastro_fundo(entrada.cnpj) or {}
        # taxa informada pelo usuario manda; o cadastro so entra como pista
        # quando o fundo legado da CVM ainda a publica
        taxa_adm = entrada.taxa_administracao
        if taxa_adm is None:
            taxa_adm = cad.get("taxa_administracao")
        taxa_perf = entrada.taxa_performance
        if taxa_perf is None:
            taxa_perf = cad.get("taxa_performance")

        item = {
            "cnpj": entrada.cnpj,
            "nome": cad.get("nome"),
            "gestora": cad.get("gestora"),
            "classe": book_mod.classe_do_fundo(cad),
            "classificacao_anbima": cad.get("classificacao_anbima"),
            "benchmark": cad.get("benchmark"),
            "tributacao_longo_prazo": cad.get("tributacao_longo_prazo"),
            "liquidez_dias": entrada.liquidez_dias,
            "taxa_administracao": taxa_adm,
            "taxa_performance": taxa_perf,
            **resolvida,
        }
        itens.append(item)
        posicoes_calculo.append({
            "cnpj": entrada.cnpj,
            "quantidade_cotas": resolvida["quantidade_cotas"],
            "data_entrada": resolvida["data_entrada"],
        })

    if not itens:
        raise HTTPException(
            status_code=400,
            detail="Nenhuma posição pôde ser calculada com os dados informados.",
        )

    series_recortadas = {
        p["cnpj"]: analytics.recorta(series[p["cnpj"]], meses) for p in posicoes_calculo
    }
    retornos, pesos = book_mod.curva_do_book(posicoes_calculo, series_recortadas)
    if retornos.empty:
        raise HTTPException(
            status_code=400,
            detail="Não há pregões suficientes no período para consolidar o book.",
        )

    retornos_fundos = pd.DataFrame({
        cnpj: analytics.retornos_diarios(serie).reindex(retornos.index)
        for cnpj, serie in series_recortadas.items()
    })

    total = sum(i["valor_atual"] for i in itens)
    for item in itens:
        item["percentual"] = analytics._limpa(item["valor_atual"] / total) if total else None
        item["metricas"] = analytics.metricas(
            retornos_fundos[item["cnpj"]].dropna()
        )

    escolhidos = [b for b in pedido.benchmarks if b in indices.BENCHMARKS] or ["cdi"]
    series_bench = {
        chave: indices.retornos_benchmark(chave, retornos.index) for chave in escolhidos
    }
    cdi = series_bench.get("cdi")
    if cdi is None:
        cdi = indices.retornos_benchmark("cdi", retornos.index)

    metricas = analytics.metricas(
        retornos, None, cdi if not cdi.empty else None
    )
    contrib_retorno = book_mod.contribuicao_retorno(
        pesos, retornos_fundos, metricas.get("retorno_acumulado")
    )
    pesos_finais = pd.Series(
        {i["cnpj"]: (i["valor_atual"] / total if total else 0.0) for i in itens}
    )
    risco = book_mod.contribuicao_risco(pesos_finais, retornos_fundos)

    investido = sum(i["valor_investido"] for i in itens if i["valor_investido"] is not None)
    com_custo = [i for i in itens if i["valor_investido"] is not None]

    return {
        "periodo": {
            "chave": pedido.periodo,
            "rotulo": analytics.PERIODOS_POR_CHAVE[pedido.periodo]["rotulo"],
            "inicio": retornos.index[0].strftime("%Y-%m-%d"),
            "fim": retornos.index[-1].strftime("%Y-%m-%d"),
            "pregoes": int(len(retornos)),
        },
        "resumo": {
            "patrimonio": analytics._limpa(total),
            "valor_investido": analytics._limpa(investido) if com_custo else None,
            "resultado": (
                analytics._limpa(sum(i["resultado"] for i in com_custo)) if com_custo else None
            ),
            "cobertura_custo": analytics._limpa(
                sum(i["valor_atual"] for i in com_custo) / total
            ) if total else None,
            "fundos": len(itens),
            "gestoras": len({i["gestora"] for i in itens if i["gestora"]}),
        },
        "metricas": metricas,
        "janelas": analytics.retornos_por_janela(
            (1.0 + retornos).cumprod(), None, cdi if not cdi.empty else None
        ),
        "serie": analytics.serie_para_json(
            retornos, {k: v for k, v in series_bench.items() if not v.empty}
        ),
        # curvas individuais para a comparacao lado a lado. Menos pontos que a
        # serie principal de proposito: sao N curvas no mesmo eixo, e o payload
        # cresce com o tamanho do book.
        "serie_fundos": analytics.serie_para_json(
            retornos,
            {i["cnpj"]: retornos_fundos[i["cnpj"]].fillna(0.0) for i in itens},
            maximo_pontos=400,
        ),
        "benchmarks": [
            {"chave": k, "rotulo": indices.rotulo(k), "disponivel": not v.empty}
            for k, v in series_bench.items()
        ],
        "alocacao": {
            "por_classe": book_mod.agrupa(itens, "classe", total),
            "por_gestora": book_mod.agrupa(itens, "gestora", total),
        },
        "liquidez": book_mod.liquidez(itens, total),
        "risco": {
            **risco,
            "concentracao_fundo": book_mod.concentracao(
                [i["valor_atual"] for i in itens], total
            ),
            "concentracao_gestora": book_mod.concentracao(
                [g["valor"] for g in book_mod.agrupa(itens, "gestora", total)], total
            ),
            "concentracao_classe": book_mod.concentracao(
                [g["valor"] for g in book_mod.agrupa(itens, "classe", total)], total
            ),
        },
        "contribuicao_retorno": contrib_retorno,
        "custos": book_mod.custos(itens, total),
        "tributacao": book_mod.tributacao(itens, date.today()),
        "fundos": itens,
        "ignorados": ignorados,
    }
