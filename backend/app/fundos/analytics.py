"""Metricas de performance e risco de um fundo, a partir da serie de cotas.

Modulo puro: recebe Series do pandas, devolve numeros. Nao conhece CVM, nem
HTTP, nem banco - o que o torna testavel com series sinteticas e reaproveitavel
tanto para um fundo isolado quanto para a curva consolidada de um book.

Convencoes, todas seguidas sem excecao no resto do sistema:

- A serie base e a COTA, nao o patrimonio. Cota ja e liquida de taxas e imune
  a captacao e resgate; patrimonio sobe quando entra dinheiro novo, o que nao
  e rentabilidade.
- Retorno diario simples entre pregoes consecutivos REPORTADOS. O informe da
  CVM nao tem todos os dias uteis para todos os fundos, e tapar esses buracos
  com zero criaria dias de retorno nulo que nunca existiram - o que derrubaria
  a volatilidade artificialmente.
- Volatilidade anualizada por raiz de 252 dias uteis, igual ao resto do
  projeto. Retorno anualizado, ao contrario, usa o tempo de CALENDARIO
  decorrido - ver `anualizado` para o porque.
- Sharpe no padrao usado no mercado brasileiro de fundos: excesso ANUALIZADO
  sobre o CDI dividido pela volatilidade anualizada. E o mesmo numero que a
  lamina do fundo publica, entao e o que da para conferir.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

DIAS_UTEIS_ANO = 252
DIAS_ANO = 365.25
MESES_ANO = 12

# Piso de calendario para anualizar. Uma janela de "12 meses" fecha em ~364
# dias corridos; 330 aceita isso com folga e ainda barra 6 meses (~182).
MINIMO_DIAS_ANUALIZAR = 330

# Janela padrao da volatilidade movel: 21 pregoes ~ 1 mes. Curta o bastante
# para mostrar mudanca de regime, longa o bastante para nao virar ruido.
JANELA_VOL_MOVEL = 21

# Periodos rapidos oferecidos na interface. `meses=None` = desde o inicio.
PERIODOS = (
    {"chave": "1m", "rotulo": "1 mês", "meses": 1},
    {"chave": "3m", "rotulo": "3 meses", "meses": 3},
    {"chave": "6m", "rotulo": "6 meses", "meses": 6},
    {"chave": "12m", "rotulo": "12 meses", "meses": 12},
    {"chave": "24m", "rotulo": "24 meses", "meses": 24},
    {"chave": "36m", "rotulo": "36 meses", "meses": 36},
    {"chave": "60m", "rotulo": "5 anos", "meses": 60},
    {"chave": "inicio", "rotulo": "Desde o início", "meses": None},
)

PERIODOS_POR_CHAVE = {p["chave"]: p for p in PERIODOS}

# Janelas do ranking. Subconjunto das de cima - o ranking le cotas MENSAIS
# (uma varredura do mercado inteiro em serie diaria custaria minutos), entao
# nao faz sentido oferecer nele um recorte que a fonte nao resolve: "desde o
# inicio" nao existe para um universo de fundos com idades diferentes.
CHAVES_RANKING = ("1m", "6m", "12m", "24m", "36m")

PERIODOS_RANKING = tuple(p for p in PERIODOS if p["chave"] in CHAVES_RANKING)


def _limpa(valor) -> float | None:
    """float arredondado, ou None se nao for finito - JSON nao tem NaN."""
    if valor is None:
        return None
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    return round(v, 8) if math.isfinite(v) else None


# --------------------------------------------------------------------------- #
# Series basicas
# --------------------------------------------------------------------------- #

def retornos_diarios(cotas: pd.Series) -> pd.Series:
    """Retorno simples entre pregoes reportados consecutivos."""
    cotas = cotas.dropna().sort_index()
    cotas = cotas[cotas > 0]
    if len(cotas) < 2:
        return pd.Series(dtype=float)
    return cotas.pct_change().dropna()


def curva_acumulada(retornos: pd.Series) -> pd.Series:
    """Rentabilidade acumulada ponto a ponto (0 = inicio do periodo)."""
    if retornos.empty:
        return pd.Series(dtype=float)
    return (1.0 + retornos).cumprod() - 1.0


def serie_drawdown(retornos: pd.Series) -> pd.Series:
    """Queda percentual sobre o topo anterior, dia a dia (sempre <= 0).

    O topo inicial e a cota do dia ANTERIOR ao primeiro retorno (nivel 1,0),
    nao o primeiro ponto da curva. Sem esse piso, um fundo que so cai desde o
    inicio da janela apareceria com drawdown zero no primeiro dia - o topo
    seria a propria queda.
    """
    if retornos.empty:
        return pd.Series(dtype=float)
    curva = (1.0 + retornos).cumprod()
    return curva / curva.cummax().clip(lower=1.0) - 1.0


def volatilidade_movel(retornos: pd.Series, janela: int = JANELA_VOL_MOVEL) -> pd.Series:
    """Volatilidade anualizada numa janela movel."""
    if len(retornos) < janela:
        return pd.Series(dtype=float)
    return retornos.rolling(janela).std(ddof=1) * math.sqrt(DIAS_UTEIS_ANO)


def acumulado(retornos: pd.Series) -> float:
    if retornos.empty:
        return float("nan")
    return float(np.prod(1.0 + retornos.to_numpy())) - 1.0


def anualizado(retornos: pd.Series) -> float:
    """CAGR pelo tempo de CALENDARIO decorrido, nao pela contagem de pregoes.

    A contagem seria a conta errada por dois motivos. Primeiro porque fundo
    nao reporta todo dia util: uma janela de 12 meses costuma trazer 245-251
    pregoes, e um corte em 252 apagaria o Sharpe justamente da janela mais
    usada da tela. Segundo porque a base real do retorno composto e o tempo
    que o dinheiro ficou aplicado, e nao quantas vezes a cota foi publicada.

    Periodos claramente menores que um ano NAO sao extrapolados: anualizar
    20 dias de alta forte produz um numero que nao significa nada e que o
    usuario leria como projecao.
    """
    if len(retornos) < 2:
        return float("nan")
    dias = (retornos.index[-1] - retornos.index[0]).days
    if dias < MINIMO_DIAS_ANUALIZAR:
        return float("nan")
    total = 1.0 + acumulado(retornos)
    if total <= 0:
        return -1.0
    return total ** (DIAS_ANO / dias) - 1.0


def volatilidade(retornos: pd.Series) -> float:
    if len(retornos) < 2:
        return float("nan")
    return float(retornos.std(ddof=1)) * math.sqrt(DIAS_UTEIS_ANO)


# --------------------------------------------------------------------------- #
# Drawdown
# --------------------------------------------------------------------------- #

def resumo_drawdown(retornos: pd.Series) -> dict:
    """Drawdown atual, maximo, quando aconteceu e quanto levou para voltar."""
    dd = serie_drawdown(retornos)
    if dd.empty:
        return {
            "atual": None, "maximo": None, "data_maximo": None,
            "inicio_maximo": None, "data_recuperacao": None,
            "dias_recuperacao": None, "em_recuperacao": None,
        }

    atual = float(dd.iloc[-1])
    data_fundo = dd.idxmin()
    maximo = float(dd.loc[data_fundo])

    # o topo que originou a queda: ultimo dia com drawdown zerado antes do fundo
    antes = dd.loc[:data_fundo]
    zerados = antes[antes >= -1e-12]
    inicio = zerados.index[-1] if len(zerados) else antes.index[0]

    # recuperacao: primeiro dia DEPOIS do fundo em que a cota volta ao topo
    depois = dd.loc[data_fundo:]
    recuperados = depois[depois >= -1e-12]
    recuperacao = recuperados.index[0] if len(recuperados) else None

    return {
        "atual": _limpa(atual),
        "maximo": _limpa(maximo),
        "data_maximo": data_fundo.strftime("%Y-%m-%d"),
        "inicio_maximo": inicio.strftime("%Y-%m-%d"),
        "data_recuperacao": recuperacao.strftime("%Y-%m-%d") if recuperacao is not None else None,
        "dias_recuperacao": int((recuperacao - data_fundo).days) if recuperacao is not None else None,
        "em_recuperacao": bool(recuperacao is None),
    }


# --------------------------------------------------------------------------- #
# Serie mensal e consistencia
# --------------------------------------------------------------------------- #

def retornos_mensais(retornos: pd.Series) -> pd.Series:
    """Retorno composto de cada mes-calendario, indexado pelo periodo."""
    if retornos.empty:
        return pd.Series(dtype=float)
    return retornos.groupby(retornos.index.to_period("M")).apply(
        lambda r: float(np.prod(1.0 + r.to_numpy())) - 1.0
    )


def tabela_mensal(retornos: pd.Series, retornos_bench: pd.Series | None = None) -> list[dict]:
    """Grade ano x mes com o acumulado de cada ano, no formato que a tabela
    de rentabilidade historica consome."""
    mensal = retornos_mensais(retornos)
    if mensal.empty:
        return []

    bench_mensal = (
        retornos_mensais(retornos_bench)
        if retornos_bench is not None and not retornos_bench.empty
        else pd.Series(dtype=float)
    )

    linhas = []
    for ano in sorted({p.year for p in mensal.index}):
        do_ano = mensal[[p.year == ano for p in mensal.index]]
        meses = [None] * MESES_ANO
        for periodo, valor in do_ano.items():
            meses[periodo.month - 1] = _limpa(valor)

        bench_do_ano = (
            bench_mensal[[p.year == ano for p in bench_mensal.index]]
            if not bench_mensal.empty else pd.Series(dtype=float)
        )
        meses_bench = [None] * MESES_ANO
        for periodo, valor in bench_do_ano.items():
            meses_bench[periodo.month - 1] = _limpa(valor)

        linhas.append({
            "ano": int(ano),
            "meses": meses,
            "acumulado": _limpa(float(np.prod(1.0 + do_ano.to_numpy())) - 1.0),
            "meses_benchmark": meses_bench if not bench_mensal.empty else None,
            "acumulado_benchmark": (
                _limpa(float(np.prod(1.0 + bench_do_ano.to_numpy())) - 1.0)
                if len(bench_do_ano) else None
            ),
        })
    return linhas


def _maior_sequencia(valores: np.ndarray, positivo: bool) -> int:
    maior = atual = 0
    for v in valores:
        bate = v > 0 if positivo else v < 0
        atual = atual + 1 if bate else 0
        maior = max(maior, atual)
    return int(maior)


def consistencia(retornos: pd.Series, retornos_bench: pd.Series | None = None) -> dict:
    """Quantos meses o fundo entregou resultado - e com que regularidade."""
    mensal = retornos_mensais(retornos)
    if mensal.empty:
        return {
            "meses": 0, "positivos": 0, "negativos": 0,
            "percentual_positivos": None, "acima_benchmark": None,
            "percentual_acima_benchmark": None,
            "maior_sequencia_positiva": 0, "maior_sequencia_negativa": 0,
            "serie": [],
        }

    valores = mensal.to_numpy()
    positivos = int((valores > 0).sum())
    negativos = int((valores < 0).sum())
    total = len(valores)

    bench_mensal = (
        retornos_mensais(retornos_bench)
        if retornos_bench is not None and not retornos_bench.empty
        else pd.Series(dtype=float)
    )
    acima = None
    if not bench_mensal.empty:
        alinhado = bench_mensal.reindex(mensal.index)
        comparaveis = alinhado.notna()
        acima = int((mensal[comparaveis] > alinhado[comparaveis]).sum())
        comparaveis_n = int(comparaveis.sum())
    else:
        comparaveis_n = 0

    serie = [
        {
            "ano": p.year,
            "mes": p.month,
            "retorno": _limpa(v),
            "benchmark": (
                _limpa(bench_mensal.get(p)) if not bench_mensal.empty else None
            ),
        }
        for p, v in mensal.items()
    ]

    return {
        "meses": total,
        "positivos": positivos,
        "negativos": negativos,
        "percentual_positivos": _limpa(positivos / total) if total else None,
        "acima_benchmark": acima,
        "meses_comparaveis": comparaveis_n,
        "percentual_acima_benchmark": (
            _limpa(acima / comparaveis_n) if acima is not None and comparaveis_n else None
        ),
        "maior_sequencia_positiva": _maior_sequencia(valores, True),
        "maior_sequencia_negativa": _maior_sequencia(valores, False),
        "serie": serie,
    }


def consistencia_movel(retornos: pd.Series, retornos_bench: pd.Series, janela: int = 12) -> float:
    """Em que fracao das janelas moveis de 12 meses o fundo bateu o benchmark.

    E o numero que o mercado chama simplesmente de "consistencia": bater o
    benchmark em um mes e sorte, bater na maioria das janelas de um ano e
    processo.
    """
    mensal = retornos_mensais(retornos)
    bench = retornos_mensais(retornos_bench) if retornos_bench is not None else pd.Series(dtype=float)
    if mensal.empty or bench.empty or len(mensal) < janela:
        return float("nan")

    bench = bench.reindex(mensal.index)
    acum = lambda s: (1.0 + s).rolling(janela).apply(np.prod, raw=True) - 1.0  # noqa: E731
    fundo_movel = acum(mensal)
    bench_movel = acum(bench)
    validos = fundo_movel.notna() & bench_movel.notna()
    if not validos.any():
        return float("nan")
    return float((fundo_movel[validos] > bench_movel[validos]).mean())


# --------------------------------------------------------------------------- #
# Bloco completo de metricas
# --------------------------------------------------------------------------- #

def metricas(
    retornos: pd.Series,
    retornos_bench: pd.Series | None = None,
    retornos_livre_risco: pd.Series | None = None,
) -> dict:
    """Todos os indicadores de performance e risco de uma serie de retornos.

    `retornos_bench` e o benchmark do fundo (para excesso e consistencia);
    `retornos_livre_risco` e o CDI (para Sharpe e Sortino). Costumam ser a
    mesma serie em fundo de renda fixa, e series diferentes num fundo de
    acoes - por isso entram separados.
    """
    if retornos.empty:
        return {"observacoes": 0}

    vol = volatilidade(retornos)
    acum = acumulado(retornos)
    ann = anualizado(retornos)

    rf = (
        retornos_livre_risco.reindex(retornos.index).fillna(0.0)
        if retornos_livre_risco is not None and not retornos_livre_risco.empty
        else None
    )
    bench = (
        retornos_bench.reindex(retornos.index).fillna(0.0)
        if retornos_bench is not None and not retornos_bench.empty
        else None
    )

    sharpe = float("nan")
    sortino = float("nan")
    rf_acum = rf_ann = float("nan")
    if rf is not None:
        rf_acum = acumulado(rf)
        rf_ann = anualizado(rf)
        if math.isfinite(ann) and math.isfinite(rf_ann) and vol and math.isfinite(vol):
            sharpe = (ann - rf_ann) / vol

        excesso = (retornos - rf).to_numpy()
        quedas = np.minimum(excesso, 0.0)
        downside = math.sqrt(float((quedas ** 2).mean())) * math.sqrt(DIAS_UTEIS_ANO)
        if downside > 0 and math.isfinite(ann) and math.isfinite(rf_ann):
            sortino = (ann - rf_ann) / downside

    bench_acum = bench_ann = float("nan")
    excesso_acum = percentual_bench = float("nan")
    if bench is not None:
        bench_acum = acumulado(bench)
        bench_ann = anualizado(bench)
        excesso_acum = acum - bench_acum
        if bench_acum not in (0.0, None) and math.isfinite(bench_acum) and bench_acum > 0:
            percentual_bench = acum / bench_acum

    dd = resumo_drawdown(retornos)
    cons = consistencia(retornos, retornos_bench)

    return {
        "observacoes": int(len(retornos)),
        "inicio": retornos.index[0].strftime("%Y-%m-%d"),
        "fim": retornos.index[-1].strftime("%Y-%m-%d"),
        "retorno_acumulado": _limpa(acum),
        "retorno_anualizado": _limpa(ann),
        "volatilidade_anualizada": _limpa(vol),
        "volatilidade_12m": _limpa(volatilidade(retornos.iloc[-DIAS_UTEIS_ANO:])),
        "sharpe": _limpa(sharpe),
        "sortino": _limpa(sortino),
        "drawdown_atual": dd["atual"],
        "drawdown_maximo": dd["maximo"],
        "data_drawdown_maximo": dd["data_maximo"],
        "dias_recuperacao": dd["dias_recuperacao"],
        "benchmark_acumulado": _limpa(bench_acum),
        "benchmark_anualizado": _limpa(bench_ann),
        "excesso_acumulado": _limpa(excesso_acum),
        "percentual_do_benchmark": _limpa(percentual_bench),
        "cdi_acumulado": _limpa(rf_acum),
        "cdi_anualizado": _limpa(rf_ann),
        "meses_positivos": cons["positivos"],
        "meses_negativos": cons["negativos"],
        "percentual_meses_positivos": cons["percentual_positivos"],
        "percentual_meses_acima_benchmark": cons["percentual_acima_benchmark"],
        "consistencia_12m": _limpa(
            consistencia_movel(retornos, retornos_bench)
            if retornos_bench is not None else float("nan")
        ),
        "dias_positivos": int((retornos > 0).sum()),
        "dias_negativos": int((retornos < 0).sum()),
    }


# --------------------------------------------------------------------------- #
# Recortes de periodo
# --------------------------------------------------------------------------- #

def corte_do_periodo(ultima_data: pd.Timestamp, meses: int | None) -> pd.Timestamp | None:
    """Data inicial de um periodo rapido contado para tras da ultima data."""
    if meses is None:
        return None
    return ultima_data - pd.DateOffset(months=meses)


def recorta(cotas: pd.Series, meses: int | None) -> pd.Series:
    """Recorta a serie de COTAS mantendo o pregao anterior ao inicio da
    janela - sem ele o primeiro retorno do periodo nao existiria e a janela
    de 1 mes perderia justamente o primeiro dia."""
    cotas = cotas.dropna().sort_index()
    if meses is None or cotas.empty:
        return cotas
    corte = corte_do_periodo(cotas.index[-1], meses)
    anteriores = cotas.loc[:corte]
    if len(anteriores):
        corte = anteriores.index[-1]
    return cotas.loc[corte:]


def recorta_datas(cotas: pd.Series, inicio: date | None, fim: date | None) -> pd.Series:
    """Recorte por intervalo livre, com a mesma regra de borda de `recorta`:
    mantem o ultimo pregao ANTERIOR a `inicio`, para o primeiro dia do
    intervalo ter retorno."""
    cotas = cotas.dropna().sort_index()
    if cotas.empty:
        return cotas
    if fim is not None:
        cotas = cotas.loc[: pd.Timestamp(fim)]
    if inicio is not None and len(cotas):
        alvo = pd.Timestamp(inicio)
        anteriores = cotas.loc[:alvo]
        piso = anteriores.index[-1] if len(anteriores) else alvo
        cotas = cotas.loc[piso:]
    return cotas


def retornos_por_janela(
    cotas: pd.Series,
    retornos_bench: pd.Series | None = None,
    retornos_livre_risco: pd.Series | None = None,
) -> list[dict]:
    """Retorno do fundo (e do benchmark) em cada periodo rapido.

    Periodo que nao cabe no historico disponivel sai com `disponivel: False`
    em vez de sumir - a tela precisa mostrar a lacuna, nao escondê-la.
    """
    saida = []
    for periodo in PERIODOS:
        recorte = recorta(cotas, periodo["meses"])
        r = retornos_diarios(recorte)
        if r.empty:
            saida.append({**periodo, "disponivel": False})
            continue

        # o periodo so e "completo" se o historico cobre a janela inteira
        completo = True
        if periodo["meses"] is not None:
            alvo = corte_do_periodo(cotas.index[-1], periodo["meses"])
            completo = bool(cotas.index[0] <= alvo)

        bench = (
            retornos_bench.reindex(r.index).fillna(0.0)
            if retornos_bench is not None and not retornos_bench.empty else None
        )
        rf = (
            retornos_livre_risco.reindex(r.index).fillna(0.0)
            if retornos_livre_risco is not None and not retornos_livre_risco.empty else None
        )
        saida.append({
            **periodo,
            "disponivel": True,
            "completo": completo,
            "inicio": r.index[0].strftime("%Y-%m-%d"),
            "fim": r.index[-1].strftime("%Y-%m-%d"),
            "retorno": _limpa(acumulado(r)),
            "benchmark": _limpa(acumulado(bench)) if bench is not None else None,
            "cdi": _limpa(acumulado(rf)) if rf is not None else None,
            "volatilidade": _limpa(volatilidade(r)),
        })
    return saida


def serie_para_json(
    retornos: pd.Series,
    series_extras: dict[str, pd.Series] | None = None,
    maximo_pontos: int = 900,
) -> list[dict]:
    """Curvas acumuladas (fundo + benchmarks) no formato do grafico.

    `maximo_pontos` reduz a serie por amostragem regular antes de serializar:
    10 anos de pregoes sao ~2.500 pontos, e nenhum grafico de 700px mostra
    isso. A reducao preserva o primeiro e o ULTIMO ponto, para o valor final
    exibido bater com o indicador do cartao.
    """
    if retornos.empty:
        return []

    quadro = pd.DataFrame({"fundo": curva_acumulada(retornos)})
    quadro["drawdown"] = serie_drawdown(retornos)
    vol = volatilidade_movel(retornos)
    quadro["volatilidade"] = vol if not vol.empty else np.nan

    for chave, serie in (series_extras or {}).items():
        if serie is None or serie.empty:
            continue
        quadro[chave] = curva_acumulada(serie.reindex(retornos.index).fillna(0.0))

    if len(quadro) > maximo_pontos:
        passo = math.ceil(len(quadro) / maximo_pontos)
        indices = list(range(0, len(quadro), passo))
        if indices[-1] != len(quadro) - 1:
            indices.append(len(quadro) - 1)
        quadro = quadro.iloc[indices]

    registros = []
    for data, linha in quadro.iterrows():
        ponto = {"data": data.strftime("%Y-%m-%d")}
        for coluna, valor in linha.items():
            ponto[coluna] = _limpa(valor)
        registros.append(ponto)
    return registros


def serie_patrimonio(quadro: pd.DataFrame, maximo_pontos: int = 900) -> list[dict]:
    """Evolucao de patrimonio liquido, patrimonio total e cotistas."""
    if quadro.empty:
        return []
    colunas = [c for c in ("vl_patrim_liq", "vl_total", "nr_cotst") if c in quadro.columns]
    if not colunas:
        return []

    reduzido = quadro[colunas]
    if len(reduzido) > maximo_pontos:
        passo = math.ceil(len(reduzido) / maximo_pontos)
        indices = list(range(0, len(reduzido), passo))
        if indices[-1] != len(reduzido) - 1:
            indices.append(len(reduzido) - 1)
        reduzido = reduzido.iloc[indices]

    return [
        {
            "data": data.strftime("%Y-%m-%d"),
            "patrimonio_liquido": _limpa(linha.get("vl_patrim_liq")),
            "patrimonio_total": _limpa(linha.get("vl_total")),
            "cotistas": (
                None if pd.isna(linha.get("nr_cotst")) else int(linha["nr_cotst"])
            ),
        }
        for data, linha in reduzido.iterrows()
    ]


def patrimonio_medio(quadro: pd.DataFrame, dias: int = DIAS_UTEIS_ANO) -> float | None:
    """PL medio dos ultimos `dias` pregoes reportados."""
    if quadro.empty or "vl_patrim_liq" not in quadro.columns:
        return None
    serie = quadro["vl_patrim_liq"].dropna()
    if serie.empty:
        return None
    return _limpa(float(serie.iloc[-dias:].mean()))


def variacao_periodo_anterior(cotas: pd.Series, meses: int) -> float | None:
    """Retorno do periodo IMEDIATAMENTE anterior a janela atual, para os
    cartoes mostrarem "vs. periodo anterior" sem inventar comparacao."""
    cotas = cotas.dropna().sort_index()
    if cotas.empty:
        return None
    fim_anterior = corte_do_periodo(cotas.index[-1], meses)
    anterior = cotas.loc[:fim_anterior]
    if len(anterior) < 2:
        return None
    return _limpa(acumulado(retornos_diarios(recorta(anterior, meses))))
