"""Consolidacao do book: de uma lista de posicoes para a carteira inteira.

Tres decisoes valem ser explicadas, porque definem o que os numeros da tela
significam:

1. **Rentabilidade e time-weighted (TWR).** O retorno do dia e
   `(V_t - aporte_t) / V_{t-1} - 1`: o dinheiro que ENTRA num dia nao conta
   como valorizacao daquele dia. Sem isso, adicionar um fundo ao book
   apareceria como um salto de rentabilidade, que e exatamente o erro que
   essa tela existe para evitar.

2. **Contribuicao para o retorno e aritmetica**
   (`Σ_t peso_{i,t-1} · retorno_{i,t}`). A soma das contribuicoes fica
   proxima do retorno da carteira, mas nao identica - a diferenca e o efeito
   de capitalizacao, e o payload devolve essa diferenca em vez de esconde-la
   distribuindo o residuo entre os fundos.

3. **Contribuicao para o risco e a marginal (MCTR)**: `w_i·(Σw)_i / σ_p`.
   Essa soma FECHA exatamente na volatilidade da carteira, e e o unico jeito
   de responder "quem esta trazendo o risco" levando correlacao em conta - um
   fundo volatil que anda na contramao dos outros contribui pouco.

O que o usuario informa e o que o sistema calcula tambem tem fronteira firme:
prazo de resgate e taxas nao existem nos dados abertos da CVM (ver
`cadastro.py`), entao vem da posicao informada pelo usuario. Quando nao vem,
o campo fica nulo e a tela mostra lacuna - nunca um numero plausivel.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

from . import analytics
from .analytics import _limpa

# Faixas de liquidez da tela consolidada. Cada posicao cai na primeira faixa
# cujo teto ela nao ultrapassa.
FAIXAS_LIQUIDEZ = (
    (0, "D+0"),
    (1, "D+1"),
    (5, "D+5"),
    (15, "D+15"),
    (30, "D+30"),
    (60, "D+60"),
    (90, "D+90"),
)
FAIXA_ACIMA = "Acima de D+90"
FAIXA_SEM_DADO = "Não informado"

# Classes da alocacao consolidada, na ordem em que aparecem no grafico.
ORDEM_CLASSES = (
    "Renda Fixa",
    "Multimercado",
    "Renda Variável",
    "Internacional",
    "Cambial",
    "Previdência",
    "Outros",
)

# Aliquota de IR por tipo de fundo. Sao as tabelas legais vigentes, aplicadas
# ao prazo que o usuario informou - nao uma estimativa inventada. Quando falta
# a data de entrada ou a classificacao, o calculo simplesmente nao acontece.
TABELA_LONGO_PRAZO = ((180, 0.225), (360, 0.20), (720, 0.175), (math.inf, 0.15))
TABELA_CURTO_PRAZO = ((180, 0.225), (math.inf, 0.20))
ALIQUOTA_ACOES = 0.15


def classe_do_fundo(cadastro: dict | None) -> str:
    """Classe macro usada na alocacao, a partir do cadastro da CVM."""
    if not cadastro:
        return "Outros"

    if (cadastro.get("previdenciario") or "").strip().lower() == "sim":
        return "Previdência"

    anbima = (cadastro.get("classificacao_anbima") or "").strip()
    if anbima.lower().startswith("previd"):
        return "Previdência"
    if "exterior" in anbima.lower():
        return "Internacional"

    cvm = (cadastro.get("classificacao_cvm") or "").strip().lower()
    if cvm.startswith("ações") or cvm.startswith("acoes"):
        return "Renda Variável"
    if cvm.startswith("renda fixa"):
        return "Renda Fixa"
    if cvm.startswith("multimercado"):
        return "Multimercado"
    if cvm.startswith("cambial"):
        return "Cambial"

    # o cadastro pode nao ter Classificacao (comum em FIDC/FIP); nesse caso a
    # ANBIMA ainda resolve boa parte
    baixo = anbima.lower()
    for prefixo, classe in (
        ("ações", "Renda Variável"), ("renda fixa", "Renda Fixa"),
        ("multimercado", "Multimercado"), ("cambial", "Cambial"),
    ):
        if baixo.startswith(prefixo):
            return classe
    return "Outros"


def faixa_liquidez(dias: int | None) -> str:
    if dias is None:
        return FAIXA_SEM_DADO
    for teto, rotulo in FAIXAS_LIQUIDEZ:
        if dias <= teto:
            return rotulo
    return FAIXA_ACIMA


# --------------------------------------------------------------------------- #
# Posicao
# --------------------------------------------------------------------------- #

def resolve_posicao(pos: dict, cotas: pd.Series) -> dict | None:
    """Converte o que o usuario informou numa quantidade de cotas e num preco
    medio, deixando registrado DE ONDE cada um saiu.

    Tres caminhos, em ordem de precisao:
      1. quantidade de cotas informada         -> preco medio informado, ou a
                                                   cota da data de entrada;
      2. valor investido + data de entrada     -> cotas = valor / cota do dia;
      3. so valor investido                    -> o valor e tratado como a
                                                   posicao de HOJE, e sem preco
                                                   medio nao ha resultado
                                                   financeiro (fica nulo).
    """
    cotas = cotas.dropna().sort_index()
    if cotas.empty:
        return None

    cota_atual = float(cotas.iloc[-1])
    if cota_atual <= 0:
        return None

    entrada = pos.get("data_entrada")
    data_entrada = None
    cota_entrada = None
    if entrada:
        try:
            alvo = pd.Timestamp(entrada)
        except (ValueError, TypeError):
            alvo = None
        if alvo is not None:
            ate = cotas.loc[:alvo]
            # a partir da entrada, se aquele dia nao teve cota reportada
            serie = ate if len(ate) else cotas.loc[alvo:]
            if len(serie):
                data_entrada = serie.index[-1] if len(ate) else serie.index[0]
                cota_entrada = float(cotas.loc[data_entrada])

    quantidade = pos.get("quantidade_cotas")
    valor = pos.get("valor_investido")
    preco_medio = pos.get("preco_medio")
    origem = None

    if quantidade:
        quantidade = float(quantidade)
        origem = "cotas informadas"
        if not preco_medio:
            preco_medio = cota_entrada
    elif valor and cota_entrada:
        quantidade = float(valor) / cota_entrada
        preco_medio = preco_medio or cota_entrada
        origem = "valor investido na data de entrada"
    elif valor:
        quantidade = float(valor) / cota_atual
        origem = "valor atual (sem data de entrada)"
    else:
        return None

    preco_medio = float(preco_medio) if preco_medio else None
    valor_atual = quantidade * cota_atual
    custo = quantidade * preco_medio if preco_medio else None

    return {
        "quantidade_cotas": quantidade,
        "preco_medio": preco_medio,
        "cota_atual": cota_atual,
        "valor_atual": valor_atual,
        "valor_investido": custo,
        "resultado": (valor_atual - custo) if custo is not None else None,
        "rentabilidade": (cota_atual / preco_medio - 1.0) if preco_medio else None,
        "data_entrada": data_entrada.strftime("%Y-%m-%d") if data_entrada is not None else None,
        "origem_quantidade": origem,
    }


# --------------------------------------------------------------------------- #
# Curva consolidada
# --------------------------------------------------------------------------- #

def curva_do_book(posicoes: list[dict], series: dict[str, pd.Series]) -> tuple[pd.Series, pd.DataFrame]:
    """Retorno diario time-weighted do book e a matriz de pesos diarios.

    Devolve `(retornos, pesos)`, ambos indexados pelos pregoes em que pelo
    menos um fundo do book reportou cota.
    """
    if not posicoes:
        return pd.Series(dtype=float), pd.DataFrame()

    # calendario comum: uniao dos pregoes de todos os fundos, com a ultima
    # cota conhecida preenchida para frente (fundo que nao reportou naquele
    # dia nao "perdeu valor", so nao publicou)
    datas = pd.DatetimeIndex(sorted(set().union(*(s.index for s in series.values()))))
    if len(datas) < 2:
        return pd.Series(dtype=float), pd.DataFrame()

    valores = {}
    aportes = {}
    for pos in posicoes:
        cnpj = pos["cnpj"]
        serie = series[cnpj].reindex(datas).ffill()
        quantidade = pos["quantidade_cotas"]
        entrada = pd.Timestamp(pos["data_entrada"]) if pos.get("data_entrada") else datas[0]

        valor = serie * quantidade
        valor[valor.index < entrada] = 0.0       # antes da entrada a posicao nao existe
        valores[cnpj] = valor.fillna(0.0)

        # o aporte entra no dia da entrada e so nele
        aporte = pd.Series(0.0, index=datas)
        dia = datas[datas >= entrada]
        if len(dia):
            aporte.loc[dia[0]] = float(valor.loc[dia[0]])
        aportes[cnpj] = aporte

    matriz = pd.DataFrame(valores)
    total = matriz.sum(axis=1)
    fluxo = pd.DataFrame(aportes).sum(axis=1)

    anterior = total.shift(1)
    retornos = (total - fluxo) / anterior - 1.0
    retornos = retornos.replace([np.inf, -np.inf], np.nan)
    # dia sem patrimonio anterior (book ainda vazio) nao tem retorno
    retornos = retornos[anterior.notna() & (anterior > 0)].fillna(0.0)

    pesos = matriz.div(total.replace(0.0, np.nan), axis=0).fillna(0.0)
    return retornos, pesos.loc[retornos.index]


def contribuicao_retorno(
    pesos: pd.DataFrame, retornos_fundos: pd.DataFrame, retorno_book: float | None
) -> dict:
    """Quanto de todo o retorno do periodo veio de cada fundo."""
    if pesos.empty or retornos_fundos.empty:
        return {"itens": [], "soma": None, "residuo_capitalizacao": None}

    pesos_ontem = pesos.shift(1).reindex(retornos_fundos.index).fillna(0.0)
    contrib = (pesos_ontem * retornos_fundos.reindex(pesos.index).fillna(0.0)).sum()
    soma = float(contrib.sum())

    return {
        "itens": [
            {
                "cnpj": cnpj,
                "contribuicao": _limpa(valor),
                "participacao": _limpa(valor / soma) if soma else None,
            }
            for cnpj, valor in contrib.sort_values(ascending=False).items()
        ],
        "soma": _limpa(soma),
        "residuo_capitalizacao": (
            _limpa(retorno_book - soma) if retorno_book is not None else None
        ),
    }


def contribuicao_risco(pesos_finais: pd.Series, retornos_fundos: pd.DataFrame) -> dict:
    """Decomposicao da volatilidade da carteira por fundo (MCTR).

    Usa os pesos ATUAIS: a pergunta e "se eu mantiver esta carteira, de onde
    vem meu risco", nao "de onde veio o risco de uma carteira que ja mudou".
    """
    fundos = [c for c in retornos_fundos.columns if pesos_finais.get(c, 0.0) > 0]
    if len(fundos) < 1:
        return {"volatilidade": None, "itens": [], "correlacao": None}

    quadro = retornos_fundos[fundos].dropna(how="all").fillna(0.0)
    if len(quadro) < 3:
        return {"volatilidade": None, "itens": [], "correlacao": None}

    w = pesos_finais[fundos].to_numpy(dtype=float)
    soma = w.sum()
    if soma <= 0:
        return {"volatilidade": None, "itens": [], "correlacao": None}
    w = w / soma

    cov = quadro.cov().to_numpy() * analytics.DIAS_UTEIS_ANO
    variancia = float(w @ cov @ w)
    vol = math.sqrt(variancia) if variancia > 0 else 0.0

    itens = []
    if vol > 0:
        marginal = cov @ w / vol       # dσ/dw_i
        for i, cnpj in enumerate(fundos):
            aporte = float(w[i] * marginal[i])
            itens.append({
                "cnpj": cnpj,
                "peso": _limpa(w[i]),
                "volatilidade_individual": _limpa(
                    float(quadro[cnpj].std(ddof=1)) * math.sqrt(analytics.DIAS_UTEIS_ANO)
                ),
                "contribuicao": _limpa(aporte),
                "participacao": _limpa(aporte / vol),
            })
        itens.sort(key=lambda d: -(d["contribuicao"] or 0))

    correlacao = None
    if len(fundos) > 1:
        matriz = quadro.corr()
        correlacao = {
            "fundos": fundos,
            "valores": [[_limpa(v) for v in linha] for linha in matriz.to_numpy()],
        }

    return {"volatilidade": _limpa(vol), "itens": itens, "correlacao": correlacao}


# --------------------------------------------------------------------------- #
# Agregacoes
# --------------------------------------------------------------------------- #

def agrupa(itens: list[dict], chave: str, total: float) -> list[dict]:
    grupos: dict[str, dict] = {}
    for item in itens:
        nome = item[chave] or "Não informado"
        grupo = grupos.setdefault(nome, {"nome": nome, "valor": 0.0, "fundos": 0})
        grupo["valor"] += item["valor_atual"]
        grupo["fundos"] += 1
    return [
        {**g, "valor": _limpa(g["valor"]), "percentual": _limpa(g["valor"] / total) if total else None}
        for g in sorted(grupos.values(), key=lambda g: -g["valor"])
    ]


def concentracao(valores: list[float], total: float) -> dict:
    """Indice de Herfindahl e peso do maior item - as duas leituras de
    concentracao que cabem num cartao."""
    if not valores or total <= 0:
        return {"hhi": None, "maior": None, "itens": 0}
    pesos = [v / total for v in valores]
    return {
        "hhi": _limpa(sum(p * p for p in pesos)),
        "maior": _limpa(max(pesos)),
        "itens": len(pesos),
    }


def custos(itens: list[dict], total: float) -> dict:
    """Custo anual estimado a partir das taxas informadas.

    So entram no total os fundos com taxa conhecida; `cobertura` diz que
    fracao do book isso representa, para a tela nao apresentar um custo
    parcial como se fosse o custo inteiro.
    """
    com_taxa = [i for i in itens if i.get("taxa_administracao") is not None]
    valor_coberto = sum(i["valor_atual"] for i in com_taxa)
    custo_adm = sum(i["valor_atual"] * (i["taxa_administracao"] / 100.0) for i in com_taxa)

    return {
        "custo_administracao_ano": _limpa(custo_adm) if com_taxa else None,
        "taxa_media_ponderada": (
            _limpa(custo_adm / valor_coberto) if valor_coberto else None
        ),
        "percentual_do_book": _limpa(custo_adm / total) if total and com_taxa else None,
        "cobertura": _limpa(valor_coberto / total) if total else None,
        "fundos_com_taxa": len(com_taxa),
        "fundos_sem_taxa": len(itens) - len(com_taxa),
        "por_fundo": [
            {
                "cnpj": i["cnpj"],
                "taxa_administracao": i["taxa_administracao"],
                "taxa_performance": i.get("taxa_performance"),
                "custo_ano": _limpa(i["valor_atual"] * (i["taxa_administracao"] / 100.0)),
            }
            for i in sorted(com_taxa, key=lambda i: -i["valor_atual"])
        ],
    }


def _aliquota(item: dict, dias: int) -> float | None:
    """Aliquota de IR sobre o ganho, pela tabela legal do tipo de fundo."""
    if item["classe"] == "Renda Variável":
        return ALIQUOTA_ACOES
    if item["classe"] == "Previdência":
        return None  # depende do regime escolhido pelo cotista; nao da para supor

    longo = (item.get("tributacao_longo_prazo") or "").strip().lower()
    tabela = TABELA_CURTO_PRAZO if longo in ("não", "nao", "n") else TABELA_LONGO_PRAZO
    for limite, aliquota in tabela:
        if dias <= limite:
            return aliquota
    return tabela[-1][1]


def tributacao(itens: list[dict], hoje: date) -> dict:
    """IR estimado sobre o ganho nao realizado de cada posicao.

    E estimativa de verdade, e a tela diz isso: aplica a tabela regressiva
    legal ao prazo desde a entrada, mas nao conhece come-cotas ja recolhido,
    prejuizo a compensar nem o custo real de aquisicao quando o usuario nao
    informou preco medio. Posicao sem ganho apurado ou sem data de entrada
    fica de fora do total, e `cobertura` mostra o tamanho dessa lacuna.
    """
    bruto = 0.0
    imposto = 0.0
    cobertos = []
    detalhe = []

    for item in itens:
        ganho = item.get("resultado")
        entrada = item.get("data_entrada")
        if ganho is None or entrada is None:
            detalhe.append({"cnpj": item["cnpj"], "ir_estimado": None, "aliquota": None})
            continue

        dias = (hoje - date.fromisoformat(entrada)).days
        aliquota = _aliquota(item, dias)
        if aliquota is None:
            detalhe.append({"cnpj": item["cnpj"], "ir_estimado": None, "aliquota": None})
            continue

        ir = max(ganho, 0.0) * aliquota
        bruto += item["valor_atual"]
        imposto += ir
        cobertos.append(item)
        detalhe.append({
            "cnpj": item["cnpj"],
            "dias_aplicado": dias,
            "aliquota": _limpa(aliquota),
            "ganho": _limpa(ganho),
            "ir_estimado": _limpa(ir),
        })

    total = sum(i["valor_atual"] for i in itens)
    return {
        "saldo_bruto": _limpa(total),
        "ir_estimado": _limpa(imposto) if cobertos else None,
        "saldo_liquido_estimado": _limpa(total - imposto) if cobertos else None,
        "impacto": _limpa(imposto / total) if total and cobertos else None,
        "cobertura": _limpa(bruto / total) if total else None,
        "fundos_estimados": len(cobertos),
        "fundos_sem_estimativa": len(itens) - len(cobertos),
        "por_fundo": detalhe,
        "observacao": (
            "Estimativa: aplica a tabela regressiva de IR ao prazo desde a data de "
            "entrada informada. Não considera come-cotas já recolhido, prejuízos a "
            "compensar nem eventos societários."
        ),
    }


def liquidez(itens: list[dict], total: float) -> list[dict]:
    """Patrimonio por faixa de prazo de resgate."""
    ordem = [r for _, r in FAIXAS_LIQUIDEZ] + [FAIXA_ACIMA, FAIXA_SEM_DADO]
    acumulado: dict[str, float] = {}
    contagem: dict[str, int] = {}
    for item in itens:
        faixa = faixa_liquidez(item.get("liquidez_dias"))
        acumulado[faixa] = acumulado.get(faixa, 0.0) + item["valor_atual"]
        contagem[faixa] = contagem.get(faixa, 0) + 1

    return [
        {
            "faixa": faixa,
            "valor": _limpa(acumulado[faixa]),
            "percentual": _limpa(acumulado[faixa] / total) if total else None,
            "fundos": contagem[faixa],
        }
        for faixa in ordem
        if faixa in acumulado
    ]
