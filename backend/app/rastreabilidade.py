"""Rastreabilidade do book: da compra ate hoje, e da projecao ate o horizonte.

Responde duas perguntas que o resto do sistema nao responde. As metricas de
risco existentes (VaR, ES, Sharpe) descrevem a carteira como se ela tivesse
sido montada no comeco da serie e rebalanceada todo dia. Aqui o ponto de
partida e outro: a DATA EM QUE A POSICAO FOI COMPRADA.

    1. "Comprei ha X dias — quanto valorizou ou desvalorizou?"
       Preco/PU de aquisicao contra o preco/PU de hoje, em reais, em
       percentual e anualizado, com o pico, o fundo e a queda desde o pico do
       periodo de posse.

    2. "E qual a projecao?"
       Deriva da janela de estimacao para o valor esperado, e os tres VaRs
       (empirico, parametrico, EWMA) para o piso do intervalo. Projecao nao e
       previsao: e a distribuicao dos retornos passados levada ao horizonte.

Duas regras herdadas do playground de carteira e que valem repetir:

    - A JANELA NUNCA VE O DIA QUE ESTA SENDO PREVISTO. `janela_para_prever` e
      o unico lugar que decide isso, e recebe o dia alvo, nao um "modo". E o
      que impede look-ahead na projecao.

    - O NUMERO SAI SEMPRE, COM A CONFIABILIDADE DECLARADA. Em vez de esconder
      a projecao quando a amostra e curta, ela aparece com o nivel e o motivo
      (`confiabilidade`). Aviso permanente vira papel de parede; por isso o
      nivel SAUDAVEL nao emite motivo nenhum.

O modulo e puro: DataFrame e Series entram, dicionario serializavel sai.
Nenhum I/O, nenhuma dependencia de FastAPI.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from . import var_empirico, var_ewma, var_parametrico
from .var_core import DIAS_UTEIS_ANO, retorno_carteira, retornos_simples

METODOS = (var_empirico, var_parametrico, var_ewma)

# abaixo disso, anualizar um retorno de posse amplifica ruido em vez de
# informar: um mes de posse virando "X% ao ano" e numerologia
MINIMO_PREGOES_ANUALIZAR = 21

# a projecao precisa de amostra para estimar deriva e volatilidade
MINIMO_OBSERVACOES_PROJETAR = 30

# pontos da trajetoria projetada: o cone e desenhado com no maximo isto,
# amostrado uniformemente, para o payload nao crescer com o horizonte
MAXIMO_PONTOS_TRAJETORIA = 60

# --------------------------------------------------------------------------- #
# Confiabilidade da projecao
# --------------------------------------------------------------------------- #

JANELA_SAUDAVEL = 252
VOL_ANUAL_MINIMA = 0.01
DEFASAGEM_ACEITAVEL_DIAS = 5

NIVEIS = ("CRITICA", "BAIXA", "REDUZIDA", "SAUDAVEL")
ROTULO_NIVEL = {
    "CRITICA": "Crítica",
    "BAIXA": "Baixa",
    "REDUZIDA": "Reduzida",
    "SAUDAVEL": "Saudável",
}


def _nivel_pela_janela(observacoes: int) -> str:
    if observacoes >= JANELA_SAUDAVEL:
        return "SAUDAVEL"
    if observacoes >= 120:
        return "REDUZIDA"
    if observacoes >= 60:
        return "BAIXA"
    return "CRITICA"


def _rebaixar(nivel: str) -> str:
    """Um degrau para baixo, qualquer que seja o numero de gatilhos."""
    return NIVEIS[max(NIVEIS.index(nivel) - 1, 0)]


def confiabilidade(
    janela: pd.Series, hoje: date | None = None, rotulo: str | None = None
) -> dict:
    """Quanto confiar na projecao, e por que.

    O nivel sai do tamanho da janela efetiva e e rebaixado UM degrau se algum
    sinal de serie problematica aparecer — volatilidade perto de zero (serie
    suavizada, marcacao na curva) ou ultima observacao defasada. Os motivos se
    acumulam; o rebaixamento e um so.
    """
    onde = f"{rotulo}: " if rotulo else ""
    observacoes = int(janela.notna().sum())
    nivel = _nivel_pela_janela(observacoes)
    motivos: list[str] = []

    if nivel != "SAUDAVEL":
        motivos.append(
            f"{onde}janela efetiva de {observacoes} observações, abaixo das "
            f"{JANELA_SAUDAVEL} de um ano de pregões."
        )

    piorou = False
    obs = janela.dropna()
    if len(obs) >= 2:
        vol = float(obs.std(ddof=1)) * np.sqrt(DIAS_UTEIS_ANO)
        if vol < VOL_ANUAL_MINIMA:
            motivos.append(
                f"{onde}volatilidade anualizada de {vol * 100:.2f}%, abaixo de 1% — "
                "sinal de série suavizada ou marcação na curva, e não de preço "
                "negociado. O intervalo da projeção sai artificialmente estreito."
            )
            piorou = True

    if len(obs) and hoje is not None:
        defasagem = (hoje - obs.index[-1].date()).days
        if defasagem > DEFASAGEM_ACEITAVEL_DIAS:
            motivos.append(
                f"{onde}a última observação é de {obs.index[-1]:%d/%m/%Y}, "
                f"{defasagem} dias atrás. A projeção parte de um preço velho."
            )
            piorou = True

    if piorou:
        nivel = _rebaixar(nivel)

    return {
        "nivel": nivel,
        "rotulo": ROTULO_NIVEL[nivel],
        "observacoes": observacoes,
        "motivos": motivos,
    }


# --------------------------------------------------------------------------- #
# Janela de estimacao
# --------------------------------------------------------------------------- #

def janela_para_prever(dia_alvo, retornos: pd.Series, janela: int) -> pd.Series:
    """Os ultimos `janela` retornos ESTRITAMENTE ANTERIORES a `dia_alvo`.

    Unico ponto do modulo que decide o que a estimacao pode ver. Pede-se o dia
    que esta sendo previsto, e nao um modo: a projecao de producao usa
    `dia_alvo` = o primeiro dia projetado, entao a janela termina na ultima
    observacao conhecida. Mascara por data, e nao `.iloc[:-1]`, porque
    `dia_alvo` pode nao existir no indice — e um dia futuro.
    """
    return retornos.loc[retornos.index < pd.Timestamp(dia_alvo)].tail(janela)


# --------------------------------------------------------------------------- #
# Helpers de serializacao
# --------------------------------------------------------------------------- #

def _num(valor, casas: int = 6) -> float | None:
    if valor is None:
        return None
    valor = float(valor)
    return round(valor, casas) if np.isfinite(valor) else None


def _reais(valor) -> float | None:
    return _num(valor, 2)


def _iso(data) -> str:
    return pd.Timestamp(data).strftime("%Y-%m-%d")


def _asof(serie: pd.Series, quando) -> tuple[pd.Timestamp | None, float]:
    """(data efetiva, valor) da ultima observacao ate `quando`.

    `asof` em vez de busca exata: a data de compra informada pelo usuario cai
    com frequencia em fim de semana, feriado ou dia sem publicacao. A data
    efetivamente usada sobe no payload para a interface poder mostrar qual foi.
    """
    limpa = serie.dropna()
    anteriores = limpa.index[limpa.index <= pd.Timestamp(quando)]
    if len(anteriores) == 0:
        return None, float("nan")
    data = anteriores[-1]
    return data, float(limpa.loc[data])


# --------------------------------------------------------------------------- #
# Projecao
# --------------------------------------------------------------------------- #

def _passos_do_cone(passos: int) -> list[int]:
    """Quais passos entram na trajetoria, sem deixar o payload crescer a toa."""
    if passos <= MAXIMO_PONTOS_TRAJETORIA:
        return list(range(1, passos + 1))
    salto = passos / MAXIMO_PONTOS_TRAJETORIA
    indices = sorted(
        {min(max(int(round(i * salto)), 1), passos) for i in range(1, MAXIMO_PONTOS_TRAJETORIA + 1)}
    )
    if indices[-1] != passos:
        indices.append(passos)
    return indices


def _trajetoria(
    passos: int,
    valor_atual: float,
    deriva: float,
    var_horizonte: float,
    datas: list[pd.Timestamp],
) -> list[dict]:
    """O cone: esperado, piso e teto em cada passo ate o horizonte.

    O piso do passo k escala o VaR do horizonte pela raiz do tempo,
    `var_k = var_h * sqrt(k / h)`. E a hipotese que os metodos parametrico e
    EWMA ja fazem internamente; no empirico e aproximacao, e por isso a
    interface declara o metodo usado no desenho. O teto e o espelho do piso em
    torno do esperado — intervalo, nao previsao de alta.
    """
    if not np.isfinite(var_horizonte) or passos < 1:
        return []

    linhas = []
    for k in _passos_do_cone(passos):
        esperado = valor_atual * (1.0 + deriva) ** k
        banda = valor_atual * var_horizonte * np.sqrt(k / passos)
        # mesma ordenacao de `projetar`: com VaR negativo a banda inverte, e o
        # cone sairia desenhado ao contrario
        baixo, alto = sorted((esperado - banda, esperado + banda))
        linhas.append(
            {
                "passo": int(k),
                "data": _iso(datas[k - 1]) if k - 1 < len(datas) else None,
                "esperado": _reais(esperado),
                "piso": _reais(baixo),
                "teto": _reais(alto),
            }
        )
    return linhas


def _dias_uteis_a_frente(ultima: pd.Timestamp, passos: int) -> list[pd.Timestamp]:
    """Os proximos `passos` dias uteis depois de `ultima`.

    Seg-sex, sem feriado: a projecao nao precisa do calendario exato da bolsa,
    e datar o eixo com dias corridos deslocaria o cone em ~40%.
    """
    return list(pd.bdate_range(pd.Timestamp(ultima) + pd.Timedelta(days=1), periods=passos))


def projetar(
    retornos: pd.Series,
    valor_atual: float,
    confianca: float,
    horizonte: int,
    janela: int,
    hoje: date | None = None,
    rotulo: str | None = None,
    com_trajetoria: bool = True,
) -> dict | None:
    """Valor projetado no horizonte, com o intervalo dos tres metodos de VaR.

    A deriva e a media simples da janela. Nao e previsao de retorno: e o que a
    amostra fez, levado adiante, e e exatamente por isso que o piso aparece ao
    lado — o intervalo e a informacao, o ponto central e a referencia.
    """
    if retornos is None or retornos.empty:
        return None

    ultima = retornos.index[-1]
    datas = _dias_uteis_a_frente(ultima, horizonte)
    # a janela termina na ultima observacao: o primeiro dia projetado e o alvo
    dia_alvo = datas[0] if datas else pd.Timestamp(ultima) + pd.Timedelta(days=1)
    amostra = janela_para_prever(dia_alvo, retornos, janela).dropna()

    if len(amostra) < MINIMO_OBSERVACOES_PROJETAR:
        return {
            "disponivel": False,
            "observacao": (
                f"Só há {len(amostra)} retornos na janela, abaixo do mínimo de "
                f"{MINIMO_OBSERVACOES_PROJETAR} para estimar deriva e volatilidade."
            ),
            "confiabilidade": confiabilidade(amostra, hoje=hoje, rotulo=rotulo),
        }

    deriva = float(amostra.mean())
    esperado = valor_atual * (1.0 + deriva) ** horizonte

    metodos = {}
    vars_brutos = {}
    for modulo in METODOS:
        pontual = modulo.pontual(amostra, confianca, horizonte)
        var, es = pontual["var"], pontual["es"]
        finito = np.isfinite(var)
        vars_brutos[modulo.NOME] = var
        # VaR negativo acontece de verdade: numa LFT, nem o percentil de 5% da
        # janela e perda. Ai o "piso" calculado fica ACIMA do teto, e ordenar os
        # dois e a unica saida que nao inventa risco nem mostra um intervalo de
        # cabeca para baixo. O flag deixa a interface dizer o que esta havendo.
        extremos = sorted(
            (esperado - valor_atual * var, esperado + valor_atual * var)
        ) if finito else (None, None)
        metodos[modulo.NOME] = {
            "rotulo": modulo.ROTULO,
            "var_percentual": _num(var),
            "var_monetario": _reais(var * valor_atual) if finito else None,
            "es_percentual": _num(es),
            "es_monetario": _reais(es * valor_atual) if np.isfinite(es) else None,
            "piso": _reais(extremos[0]) if finito else None,
            "teto": _reais(extremos[1]) if finito else None,
            "sem_perda_na_confianca": bool(finito and var < 0),
        }

    # o cone e desenhado com o empirico: e o metodo que nao impoe normalidade.
    # Usa o VaR BRUTO, nao o arredondado do payload, para o ultimo passo do cone
    # fechar exatamente no piso declarado em `metodos` — um numero, uma fonte.
    trajetoria = (
        _trajetoria(horizonte, valor_atual, deriva, vars_brutos[var_empirico.NOME], datas)
        if com_trajetoria
        else []
    )

    variacao = (1.0 + deriva) ** horizonte - 1.0
    return {
        "disponivel": True,
        "horizonte_pregoes": int(horizonte),
        "data_partida": _iso(ultima),
        "data_alvo": _iso(datas[-1]) if datas else None,
        "observacoes_janela": int(len(amostra)),
        "valor_atual": _reais(valor_atual),
        "deriva_diaria": _num(deriva),
        "valor_esperado": _reais(esperado),
        "variacao_esperada_reais": _reais(esperado - valor_atual),
        "variacao_esperada_percentual": _num(variacao),
        "metodos": metodos,
        "metodo_do_cone": var_empirico.NOME,
        "trajetoria": trajetoria,
        "confiabilidade": confiabilidade(amostra, hoje=hoje, rotulo=rotulo),
        "observacao": (
            f"Projeção de {horizonte} pregões a partir de {pd.Timestamp(ultima):%d/%m/%Y}, "
            f"com a deriva e a volatilidade dos últimos {len(amostra)} retornos. O piso "
            f"é o VaR a {confianca * 100:.0f}% levado ao horizonte pela raiz do tempo. "
            "Não é previsão: é a distribuição observada projetada adiante."
        ),
    }


# --------------------------------------------------------------------------- #
# Rastreabilidade de uma posicao
# --------------------------------------------------------------------------- #

def rastrear_posicao(
    serie: pd.Series,
    *,
    identificador: str,
    rotulo: str,
    classe: str,
    quantidade: float,
    valor_atual: float,
    preco_atual: float,
    data_preco_atual,
    data_compra=None,
    preco_compra: float | None = None,
    preco_compra_estimado: bool | None = None,
    peso: float | None = None,
    detalhe: dict | None = None,
) -> dict:
    """Uma linha de rastreabilidade: da compra ate hoje.

    `serie` e a serie de precos do ativo (fechamento ajustado para acoes, PU de
    venda para titulo publico) — o motor trata as duas do mesmo jeito, que e o
    que permite uma unica funcao servir aos dois books.

    Sem `data_compra`, a posicao e tratada como comprada na primeira data da
    serie: a rastreabilidade degrada para o periodo inteiro da analise em vez
    de inventar uma referencia. Sem `preco_compra`, usa-se o preco da serie na
    data de compra, e a linha sai marcada como estimada.

    `preco_compra_estimado` existe para quem JA resolveu essa estimativa antes
    de chamar aqui — e o caso da renda fixa, onde a marcacao a mercado ja
    preencheu o PU de aquisicao a partir da serie e sabe se ele foi informado
    ou nao. Sem o repasse, o PU chegaria preenchido e a linha mentiria dizendo
    que o usuario informou o preco.
    """
    limpa = serie.dropna()
    referencia = pd.Timestamp(data_preco_atual)

    alvo = pd.Timestamp(data_compra) if data_compra else limpa.index[0]
    if alvo > referencia:
        alvo = referencia

    data_efetiva, preco_na_serie = _asof(limpa, alvo)
    if data_efetiva is None:
        # compra anterior ao inicio da serie: a primeira observacao e o melhor
        # ancoradouro honesto, e a interface mostra que a data recuou
        data_efetiva = limpa.index[0]
        preco_na_serie = float(limpa.iloc[0])

    if preco_compra is not None and float(preco_compra) > 0:
        preco = float(preco_compra)
        estimado = False
    else:
        preco = float(preco_na_serie)
        estimado = True
    if preco_compra_estimado is not None:
        estimado = bool(preco_compra_estimado)

    posse = limpa.loc[(limpa.index >= data_efetiva) & (limpa.index <= referencia)]
    pregoes = int(max(len(posse) - 1, 0))
    dias_corridos = int((referencia - data_efetiva).days)

    valor_compra = quantidade * preco
    valorizacao = valor_atual - valor_compra
    retorno = (preco_atual / preco - 1.0) if preco else float("nan")

    anualizado = None
    if pregoes >= MINIMO_PREGOES_ANUALIZAR and preco and (1.0 + retorno) > 0:
        anualizado = (1.0 + retorno) ** (DIAS_UTEIS_ANO / pregoes) - 1.0

    # pico, fundo e a queda desde o pico que a posicao viveu desde a compra:
    # dois papeis com o mesmo P&L de hoje podem ter tido trajetos bem diferentes
    pico = fundo = None
    queda_do_pico = None
    if not posse.empty:
        i_pico, i_fundo = posse.idxmax(), posse.idxmin()
        pico = {"data": _iso(i_pico), "preco": _num(posse.loc[i_pico], 4)}
        fundo = {"data": _iso(i_fundo), "preco": _num(posse.loc[i_fundo], 4)}
        maximo = float(posse.max())
        queda_do_pico = (preco_atual / maximo - 1.0) if maximo else None

    informada = _iso(data_compra) if data_compra else None
    linha = {
        "id": identificador,
        "rotulo": rotulo,
        "classe": classe,
        "quantidade": _num(quantidade, 4),
        "peso": _num(peso),
        "data_compra": _iso(data_efetiva),
        "data_compra_informada": informada,
        "data_compra_recuada": bool(informada) and _iso(data_efetiva) != informada,
        "preco_compra": _num(preco, 4),
        "preco_compra_estimado": estimado,
        "preco_atual": _num(preco_atual, 4),
        "data_preco_atual": _iso(referencia),
        "dias_corridos": dias_corridos,
        "pregoes": pregoes,
        "valor_compra": _reais(valor_compra),
        "valor_atual": _reais(valor_atual),
        "valorizacao_reais": _reais(valorizacao),
        "valorizacao_percentual": _num(retorno),
        "retorno_anualizado": _num(anualizado),
        "pico": pico,
        "fundo": fundo,
        "queda_desde_o_pico": _num(queda_do_pico),
        "evolucao": [
            {"data": _iso(i), "valor": _reais(quantidade * float(v))}
            for i, v in posse.items()
        ],
    }
    if detalhe:
        linha["detalhe"] = detalhe
    return linha


# --------------------------------------------------------------------------- #
# Montagem das posicoes a partir de cada book
# --------------------------------------------------------------------------- #
#
# Regra unica para os dois books: PRECO ATUAL E VALOR ATUAL SAEM SEMPRE DA
# MATRIZ DE PRECOS, na data de referencia dela. E o que mantem o book de acoes,
# o de renda fixa e o consolidado coerentes entre si — no consolidado a matriz
# so tem as datas em comum entre a bolsa e o Tesouro, e a rastreabilidade
# declara essa data em vez de misturar duas referencias diferentes.
#
# A diferenca entre as duas classes esta em qual lado e o dado primario:
#   - acoes: o PESO e informado, o valor sai da fatia do valor da carteira e a
#     quantidade e derivada (valor / preco), como ja faz `analise._book`;
#   - renda fixa: a QUANTIDADE e informada e o valor e derivado (qtde x PU).

def posicoes_de_acoes(
    precos: pd.DataFrame,
    posicoes,
    pesos: dict[str, float],
    valor_carteira: float,
) -> list[dict]:
    """Posicoes do book de acoes prontas para `rastrear_book`."""
    itens = []
    for posicao in posicoes:
        ticker = posicao.ticker
        if ticker not in precos.columns:
            continue
        serie = precos[ticker].dropna()
        if serie.empty:
            continue
        preco_atual = float(serie.iloc[-1])
        peso = pesos[ticker]
        valor_atual = peso * valor_carteira
        itens.append(
            {
                "id": ticker,
                "rotulo": ticker,
                "classe": "acoes",
                "peso": peso,
                "preco_atual": preco_atual,
                "valor_atual": valor_atual,
                "quantidade": valor_atual / preco_atual if preco_atual else 0.0,
                "data_compra": posicao.data_compra,
                "preco_compra": posicao.preco_compra,
            }
        )
    return itens


def posicoes_de_renda_fixa(precos: pd.DataFrame, marcacao: dict) -> list[dict]:
    """Posicoes do book de renda fixa prontas para `rastrear_book`.

    A marcacao a mercado ja fez o trabalho de casar posicao com papel e achar o
    PU de aquisicao; aqui so se traduz aquele dicionario para o contrato de
    rastreabilidade, com o PU virando "preco" e o papel virando "ativo".
    """
    itens = []
    for linha in marcacao["posicoes"]:
        papel = linha["id"]
        if papel not in precos.columns:
            continue
        serie = precos[papel].dropna()
        if serie.empty:
            continue
        pu_atual = float(serie.iloc[-1])
        quantidade = linha["quantidade"]
        itens.append(
            {
                "id": papel,
                "rotulo": f"{linha['tipo']} {linha['vencimento'][:4]}",
                "classe": "renda-fixa",
                "peso": linha["peso"],
                "preco_atual": pu_atual,
                "valor_atual": quantidade * pu_atual,
                "quantidade": quantidade,
                "data_compra": linha["data_aquisicao"],
                "preco_compra": linha["pu_aquisicao"],
                # a marcacao ja sabe se o PU foi informado ou estimado por ela
                "preco_compra_estimado": linha["pu_estimado"],
                "detalhe": {
                    "tipo": linha["tipo"],
                    "tipo_slug": linha["tipo_slug"],
                    "vencimento": linha["vencimento"],
                    "pu_marcacao": linha["pu_marcacao"],
                    "data_base": linha["data_base"],
                },
            }
        )
    return itens


# --------------------------------------------------------------------------- #
# Rastreabilidade do book
# --------------------------------------------------------------------------- #

def _avisos(linhas: list[dict], referencia) -> list[dict]:
    """Avisos estruturados, no mesmo formato dos de renda fixa.

    Dois casos merecem aviso porque mudam a leitura do numero sem aparecer
    nele: a data de compra que recuou (a serie comeca depois da compra, e o
    "valorizou X%" mede menos tempo do que o usuario pediu) e o preco de compra
    estimado (nao foi informado, saiu da serie).
    """
    avisos = []

    recuadas = [l for l in linhas if l["data_compra_recuada"]]
    if recuadas:
        nomes = ", ".join(f"{l['rotulo']} ({l['data_compra_informada']})" for l in recuadas)
        avisos.append(
            {
                "codigo": "compra_fora_do_periodo",
                "severidade": "aviso",
                "mensagem": (
                    f"A data de compra informada não existe na série de {nomes}. "
                    "A rastreabilidade ancorou na primeira data disponível, então a "
                    "valorização cobre menos tempo do que o pedido. Amplie o período "
                    "da análise para cobrir a data da compra."
                ),
                "detalhe": {
                    "posicoes": [l["id"] for l in recuadas],
                    "data_referencia": _iso(referencia),
                },
            }
        )

    # so avisa quando a estimativa MUDA algum numero: posicao montada na propria
    # data de referencia tem P&L zero por construcao, e avisar ali seria papel de
    # parede — o aviso perderia o valor justamente quando importa
    estimados = [l for l in linhas if l["preco_compra_estimado"] and l["pregoes"] > 0]
    if estimados:
        avisos.append(
            {
                "codigo": "preco_compra_estimado",
                "severidade": "aviso",
                "mensagem": (
                    f"{len(estimados)} de {len(linhas)} posições tiveram o preço de "
                    "compra estimado pelo preço de fechamento da data de compra, por "
                    "não ter sido informado. O P&L é do papel no período, não do que "
                    "foi efetivamente pago."
                ),
                "detalhe": {"posicoes": [l["id"] for l in estimados]},
            }
        )

    return avisos


def _totais(linhas: list[dict], referencia) -> dict:
    valor_compra = sum(l["valor_compra"] or 0.0 for l in linhas)
    valor_atual = sum(l["valor_atual"] or 0.0 for l in linhas)
    retorno = (valor_atual / valor_compra - 1.0) if valor_compra else None

    pregoes = max((l["pregoes"] for l in linhas), default=0)
    anualizado = None
    if retorno is not None and pregoes >= MINIMO_PREGOES_ANUALIZAR and (1.0 + retorno) > 0:
        anualizado = (1.0 + retorno) ** (DIAS_UTEIS_ANO / pregoes) - 1.0

    datas = [l["data_compra"] for l in linhas]
    return {
        "posicoes": len(linhas),
        "valor_compra": _reais(valor_compra),
        "valor_atual": _reais(valor_atual),
        "valorizacao_reais": _reais(valor_atual - valor_compra),
        "valorizacao_percentual": _num(retorno),
        "retorno_anualizado": _num(anualizado),
        "compra_mais_antiga": min(datas) if datas else None,
        "compra_mais_recente": max(datas) if datas else None,
        "dias_corridos": max((l["dias_corridos"] for l in linhas), default=0),
        "pregoes": pregoes,
        "data_referencia": _iso(referencia),
        "algum_preco_estimado": any(l["preco_compra_estimado"] for l in linhas),
        "ganhadoras": sum(1 for l in linhas if (l["valorizacao_reais"] or 0.0) > 0),
        "perdedoras": sum(1 for l in linhas if (l["valorizacao_reais"] or 0.0) < 0),
    }


def _evolucao_do_book(linhas: list[dict]) -> list[dict]:
    """Valor do book somando as posicoes, cada uma a partir da sua compra.

    Posicao comprada depois entra na curva na data da compra; antes disso ela
    simplesmente nao existia, e somar zero seria mentir sobre o patrimonio.
    Por isso a curva tambem devolve quantas posicoes estavam vivas em cada
    data: um salto na curva e entrada de posicao, nao valorizacao.
    """
    por_data: dict[str, list[float]] = {}
    for linha in linhas:
        for ponto in linha["evolucao"]:
            por_data.setdefault(ponto["data"], []).append(ponto["valor"] or 0.0)
    return [
        {"data": data, "valor": round(sum(vals), 2), "posicoes": len(vals)}
        for data, vals in sorted(por_data.items())
    ]


def rastrear_book(
    precos: pd.DataFrame,
    posicoes: list[dict],
    *,
    confianca: float,
    horizonte_projecao: int,
    janela: int,
    hoje: date | None = None,
    pesos: dict[str, float] | None = None,
) -> dict:
    """Rastreabilidade do book inteiro mais a projecao agregada.

    `posicoes` traz, por ativo, o que so a camada de cima sabe: quantidade,
    valor atual, data e preco de compra. Aqui se junta isso a serie de precos
    e se calcula o resto.

    A projecao do book roda sobre o retorno da carteira nos pesos informados —
    o mesmo vetor que alimenta o VaR das outras abas — entao o piso projetado
    e consistente com o VaR exibido, e nao um segundo numero concorrente.
    """
    hoje = hoje or date.today()
    referencia = precos.index[-1]

    linhas = []
    for item in posicoes:
        coluna = item["id"]
        if coluna not in precos.columns:
            continue
        serie = precos[coluna].dropna()
        if serie.empty:
            continue
        linha = rastrear_posicao(
            serie,
            identificador=coluna,
            rotulo=item.get("rotulo", coluna),
            classe=item.get("classe", "acoes"),
            quantidade=item["quantidade"],
            valor_atual=item["valor_atual"],
            preco_atual=item.get("preco_atual") or float(serie.iloc[-1]),
            data_preco_atual=referencia,
            data_compra=item.get("data_compra"),
            preco_compra=item.get("preco_compra"),
            preco_compra_estimado=item.get("preco_compra_estimado"),
            peso=item.get("peso"),
            detalhe=item.get("detalhe"),
        )
        # projecao por posicao: compacta de proposito, sem trajetoria — o cone
        # so faz sentido no agregado, e um por linha inflaria o payload
        linha["projecao"] = projetar(
            serie.pct_change().dropna(),
            valor_atual=item["valor_atual"],
            confianca=confianca,
            horizonte=horizonte_projecao,
            janela=janela,
            hoje=hoje,
            rotulo=linha["rotulo"],
            com_trajetoria=False,
        )
        linhas.append(linha)

    linhas.sort(key=lambda l: -(l["valor_atual"] or 0.0))

    projecao_book = None
    if pesos:
        presentes = {k: v for k, v in pesos.items() if k in precos.columns}
        if presentes:
            ret_book = retorno_carteira(
                retornos_simples(precos[list(presentes)]), presentes
            )
            projecao_book = projetar(
                ret_book,
                valor_atual=sum(l["valor_atual"] or 0.0 for l in linhas),
                confianca=confianca,
                horizonte=horizonte_projecao,
                janela=janela,
                hoje=hoje,
            )

    return {
        "hoje": _iso(hoje),
        "data_referencia": _iso(referencia),
        "confianca": confianca,
        "horizonte_projecao": int(horizonte_projecao),
        "posicoes": linhas,
        "totais": _totais(linhas, referencia),
        "evolucao": _evolucao_do_book(linhas),
        "projecao": projecao_book,
        "avisos": _avisos(linhas, referencia),
    }
