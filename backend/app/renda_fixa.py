"""Marcacao a mercado do book de renda fixa.

A marcacao usa `PU Venda Manha`, e isso e decisao, nao detalhe: e o preco
pelo qual o Tesouro recompra o papel, ou seja, quanto a posicao valeria se
fosse liquidada hoje. `PU Compra Manha` e preco de emissao — quanto custaria
comprar — e nao serve para marcar carteira.

A marcacao aqui e explicita de proposito: cada posicao devolve o PU de
aquisicao, o PU de marcacao, o valor marcado, o P&L em reais e em percentual
e a data base usada. Nada disso fica implicito dentro de um numero agregado.

Sobre a data base: o arquivo do Tesouro publica com defasagem, entao a
marcacao e sempre do ultimo dia util publicado — tipicamente D-1, as vezes
D-2 depois de fim de semana ou feriado. A data vai no payload para a
interface poder dizer isso ao usuario em vez de fingir que e o preco de agora.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from . import risco_retorno as rr
from .analise import METODOS
from .titulos_publicos import serie_pu, universo
from .var_core import resumo_violacoes, retorno_carteira, retornos_simples

# abaixo disso nao ha o que estimar: e o mesmo piso que `data.py` impoe as acoes
MINIMO_OBSERVACOES = 30

# o Kupiec compara violacoes observadas com esperadas; com menos de 5 esperadas
# o teste existe mas nao tem poder para rejeitar nada
MINIMO_VIOLACOES_ESPERADAS = 5.0

# abaixo desta fracao, a intersecao de datas esta jogando fora historico demais
FRACAO_INTERSECAO_ACEITAVEL = 0.5


class ErroRendaFixa(Exception):
    """Posicao que nao da para marcar."""


def _pu_na_data(serie: pd.Series, quando: pd.Timestamp) -> float:
    """Ultimo PU conhecido ate `quando`.

    `asof` em vez de busca exata porque a data de aquisicao informada pelo
    usuario pode cair em fim de semana, feriado ou num dia sem publicacao.
    """
    if serie.empty:
        return float("nan")
    return float(serie.asof(quando))


def _marca_posicao(
    posicao,
    papel: dict,
    serie: pd.Series,
    data_base: pd.Timestamp,
) -> dict:
    pu_marcacao = _pu_na_data(serie, data_base)
    if not pd.notna(pu_marcacao):
        raise ErroRendaFixa(
            f"Sem PU de venda para {papel['tipo']} {papel['vencimento']:%d/%m/%Y} "
            f"na data base de {data_base:%d/%m/%Y}."
        )

    # sem data de aquisicao, a posicao e tratada como montada na propria data
    # base: o P&L nasce zerado em vez de sair de uma referencia inventada
    data_aquisicao = pd.Timestamp(posicao.data_aquisicao or data_base.date())
    if data_aquisicao > data_base:
        data_aquisicao = data_base

    if posicao.pu_aquisicao is not None:
        pu_aquisicao = float(posicao.pu_aquisicao)
        pu_estimado = False
        data_pu = None
    else:
        pu_aquisicao = _pu_na_data(serie, data_aquisicao)
        if not pd.notna(pu_aquisicao):
            raise ErroRendaFixa(
                f"{papel['tipo']} {papel['vencimento']:%d/%m/%Y} so tem preco a "
                f"partir de {serie.index[0]:%d/%m/%Y}; informe o PU de aquisicao "
                f"para marcar uma compra de {data_aquisicao:%d/%m/%Y}."
            )
        pu_estimado = True
        # a data efetiva pode recuar em relacao a informada (fim de semana,
        # feriado, dia sem publicacao) — a interface mostra qual foi usada
        data_pu = serie.index[serie.index <= data_aquisicao][-1]

    quantidade = float(posicao.quantidade)
    valor_aquisicao = quantidade * pu_aquisicao
    valor_marcado = quantidade * pu_marcacao

    return {
        "id": papel["id"],
        "tipo": papel["tipo"],
        "tipo_slug": papel["tipo_slug"],
        "vencimento": papel["vencimento"].strftime("%Y-%m-%d"),
        "quantidade": round(quantidade, 4),
        "data_aquisicao": data_aquisicao.strftime("%Y-%m-%d"),
        "pu_aquisicao": round(pu_aquisicao, 2),
        "pu_estimado": pu_estimado,
        "data_pu_aquisicao": data_pu.strftime("%Y-%m-%d") if data_pu is not None else None,
        "pu_marcacao": round(pu_marcacao, 2),
        "data_base": data_base.strftime("%Y-%m-%d"),
        "valor_aquisicao": round(valor_aquisicao, 2),
        "valor_marcado": round(valor_marcado, 2),
        "pnl_reais": round(valor_marcado - valor_aquisicao, 2),
        "pnl_percentual": round(pu_marcacao / pu_aquisicao - 1.0, 6),
    }


def marcar(quadro: pd.DataFrame, posicoes: list, hoje: date | None = None) -> dict:
    """Marca o book inteiro a mercado no ultimo dia util publicado.

    Devolve uma linha por posicao mais os totais. O peso de cada posicao sai
    do valor marcado sobre o total marcado — no book de renda fixa a
    quantidade e o dado primario e o peso e derivado, ao contrario do book de
    acoes, onde o peso e informado e o valor e que e derivado.
    """
    hoje = hoje or date.today()
    disponiveis = universo(quadro, hoje)
    if disponiveis.empty:
        raise ErroRendaFixa(
            "Nao ha titulos disponiveis para marcar na data base do arquivo."
        )

    catalogo = {linha["id"]: linha for _, linha in disponiveis.iterrows()}
    data_base = pd.Timestamp(disponiveis["data_base"].iloc[0])

    linhas = []
    for posicao in posicoes:
        papel = catalogo.get(posicao.titulo_id)
        if papel is None:
            raise ErroRendaFixa(
                f"Titulo '{posicao.titulo_id}' nao esta disponivel na data base de "
                f"{data_base:%d/%m/%Y}. Consulte /api/titulos-publicos/disponiveis."
            )
        serie = serie_pu(quadro, papel["tipo"], papel["vencimento"])
        linhas.append(_marca_posicao(posicao, papel, serie, data_base))

    total_marcado = sum(l["valor_marcado"] for l in linhas)
    total_aquisicao = sum(l["valor_aquisicao"] for l in linhas)

    for linha in linhas:
        linha["peso"] = (
            round(linha["valor_marcado"] / total_marcado, 6) if total_marcado else None
        )

    linhas.sort(key=lambda l: (l["tipo"], l["vencimento"]))

    return {
        "data_base": data_base.strftime("%Y-%m-%d"),
        "defasagem_dias": (hoje - data_base.date()).days,
        "observacao": (
            f"Marcação pelo PU de venda de {data_base:%d/%m/%Y}, último dia útil "
            "publicado pelo Tesouro. Não é o preço de agora."
        ),
        "posicoes": linhas,
        "totais": {
            "posicoes": len(linhas),
            "valor_aquisicao": round(total_aquisicao, 2),
            "valor_marcado": round(total_marcado, 2),
            "pnl_reais": round(total_marcado - total_aquisicao, 2),
            "pnl_percentual": (
                round(total_marcado / total_aquisicao - 1.0, 6) if total_aquisicao else None
            ),
            "algum_pu_estimado": any(l["pu_estimado"] for l in linhas),
        },
    }


def pesos_por_valor_marcado(marcacao: dict) -> dict[str, float]:
    """Pesos do book de renda fixa, prontos para o motor de risco.

    Chave = id do papel, que e o nome da coluna na matriz de PUs.
    """
    return {l["id"]: l["peso"] for l in marcacao["posicoes"]}


# --------------------------------------------------------------------------- #
# Series de preco para o motor de risco
# --------------------------------------------------------------------------- #

def matriz_pu(
    quadro: pd.DataFrame,
    marcacao: dict,
    inicio: date | None = None,
    fim: date | None = None,
) -> pd.DataFrame:
    """Uma coluna de `PU Venda Manha` por papel, indexada por data base.

    E exatamente o formato que `analisar()` recebe para acoes — uma matriz de
    precos com uma coluna por ativo. A serie de PU de um titulo ao longo do
    tempo E uma serie de precos, entao nao ha calculo novo a escrever: o
    motor existente trata as duas do mesmo jeito.
    """
    colunas = {}
    for linha in marcacao["posicoes"]:
        serie = serie_pu(quadro, linha["tipo"], pd.Timestamp(linha["vencimento"]))
        colunas[linha["id"]] = serie

    matriz = pd.DataFrame(colunas)
    if inicio is not None:
        matriz = matriz[matriz.index >= pd.Timestamp(inicio)]
    if fim is not None:
        matriz = matriz[matriz.index <= pd.Timestamp(fim)]
    return matriz.sort_index()


# --------------------------------------------------------------------------- #
# Avisos estruturados
# --------------------------------------------------------------------------- #

def _aviso(codigo: str, severidade: str, mensagem: str, **detalhe) -> dict:
    return {
        "codigo": codigo,
        "severidade": severidade,
        "mensagem": mensagem,
        "detalhe": detalhe,
    }


def avisos_do_backtest(
    resumo: dict, confianca: float, janela: int, n_retornos: int, papel: str | None = None
) -> list[dict]:
    """Avisa quando o Kupiec nao tem amostra para dizer nada.

    Papel emitido ha pouco nao tem historico suficiente para o backtest
    rolling: em vez de devolver um p-valor sem significado, o aviso sai
    estruturado e o numero vem nulo.
    """
    onde = f"{papel}: " if papel else ""
    observacoes = resumo["observacoes"]

    if observacoes == 0:
        return [
            _aviso(
                "kupiec_sem_amostra",
                "erro",
                f"{onde}histórico de {n_retornos} retornos não cobre a janela de "
                f"{janela} pregões — o backtest não roda e o teste de Kupiec "
                "não tem amostra.",
                papel=papel,
                retornos=n_retornos,
                janela=janela,
                minimo_necessario=janela + 1,
            )
        ]

    esperadas = (1.0 - confianca) * observacoes
    if esperadas < MINIMO_VIOLACOES_ESPERADAS:
        return [
            _aviso(
                "kupiec_baixa_potencia",
                "aviso",
                f"{onde}o backtest tem {observacoes} observações e apenas "
                f"{esperadas:.1f} violações esperadas a {confianca * 100:.0f}% — "
                "o Kupiec sai, mas sem poder para rejeitar o modelo.",
                papel=papel,
                observacoes=observacoes,
                violacoes_esperadas=round(esperadas, 2),
                minimo_recomendado=MINIMO_VIOLACOES_ESPERADAS,
            )
        ]

    return []


def avisos_da_matriz(matriz: pd.DataFrame) -> list[dict]:
    """Avisa quando a intersecao de datas corta o historico do book.

    `retornos_simples` so mantem as datas em que TODOS os papeis tem preco,
    igual ao que ja acontece com acoes. Um papel emitido ha 152 dias trunca
    para 152 dias um book que tem outro papel com 20 anos de historico.
    """
    if matriz.empty or matriz.shape[1] < 2:
        return []

    comum = len(matriz.dropna(how="any"))
    por_papel = matriz.notna().sum()
    mais_longo = int(por_papel.max())
    if mais_longo == 0 or comum >= mais_longo * FRACAO_INTERSECAO_ACEITAVEL:
        return []

    limitante = str(por_papel.idxmin())
    return [
        _aviso(
            "intersecao_curta",
            "aviso",
            f"O book só tem {comum} datas em comum, contra {mais_longo} do papel "
            f"com histórico mais longo. '{limitante}', com "
            f"{int(por_papel.min())} observações, é quem limita a amostra.",
            datas_comuns=comum,
            maior_historico=mais_longo,
            papel_limitante=limitante,
            observacoes_do_limitante=int(por_papel.min()),
        )
    ]


# --------------------------------------------------------------------------- #
# Metricas por titulo
# --------------------------------------------------------------------------- #

def _num(valor) -> float | None:
    return round(float(valor), 6) if valor is not None and np.isfinite(valor) else None


def _dinheiro(valor, base: float) -> float | None:
    return round(float(valor) * base, 2) if valor is not None and np.isfinite(valor) else None


def metricas_por_titulo(
    matriz: pd.DataFrame,
    marcacao: dict,
    selic: pd.Series,
    confianca: float,
    horizonte: int,
    janela: int,
) -> tuple[list[dict], list[dict]]:
    """VaR, ES, Sharpe e Sortino de cada papel, isoladamente.

    Bloco compacto de proposito: sai o VaR pontual dos tres metodos e o
    RESUMO do backtest, sem a serie dia a dia. A serie completa so faz
    sentido para o book agregado — replicar por papel inflaria o payload
    sem acrescentar leitura.

    Passa pelo mesmo caminho do book: `retornos_simples` -> `retorno_carteira`
    com peso 1, e depois os mesmos `pontual`/`rolling` dos tres modulos.
    """
    linhas, avisos = [], []

    for posicao in marcacao["posicoes"]:
        papel = posicao["id"]
        precos = matriz[[papel]].dropna(how="any")
        if len(precos) < MINIMO_OBSERVACOES:
            avisos.append(
                _aviso(
                    "historico_insuficiente",
                    "erro",
                    f"{papel}: só há {len(precos)} preços publicados, abaixo do "
                    f"mínimo de {MINIMO_OBSERVACOES} para estimar risco.",
                    papel=papel,
                    observacoes=len(precos),
                    minimo=MINIMO_OBSERVACOES,
                )
            )
            continue

        retornos = retorno_carteira(retornos_simples(precos), {papel: 1.0})
        valor = posicao["valor_marcado"]

        metodos = {}
        for modulo in METODOS:
            pontual = modulo.pontual(retornos, confianca, horizonte)
            resumo = resumo_violacoes(
                modulo.rolling(retornos, confianca, janela), confianca
            )
            metodos[modulo.NOME] = {
                "rotulo": modulo.ROTULO,
                "var_percentual": _num(pontual["var"]),
                "var_monetario": _dinheiro(pontual["var"], valor),
                "es_percentual": _num(pontual["es"]),
                "es_monetario": _dinheiro(pontual["es"], valor),
                "backtest_resumo": resumo,
            }

        avisos.extend(
            avisos_do_backtest(
                metodos["empirico"]["backtest_resumo"],
                confianca,
                janela,
                len(retornos),
                papel=papel,
            )
        )

        excesso = (retornos - selic.reindex(retornos.index).ffill().bfill()).to_numpy()
        linhas.append(
            {
                "id": papel,
                "tipo": posicao["tipo"],
                "vencimento": posicao["vencimento"],
                "peso": posicao["peso"],
                "valor_marcado": valor,
                "observacoes": int(len(retornos)),
                "inicio": retornos.index[0].strftime("%Y-%m-%d"),
                "fim": retornos.index[-1].strftime("%Y-%m-%d"),
                "metodos": metodos,
                "sharpe": _num(rr.sharpe(excesso)),
                "sortino": _num(rr.sortino(excesso)),
                "vol_anualizada": _num(
                    float(retornos.std(ddof=1)) * np.sqrt(rr.DIAS_UTEIS_ANO)
                ),
            }
        )

    return linhas, avisos


def preparar(
    quadro: pd.DataFrame,
    posicoes: list,
    confianca: float,
    janela: int,
    hoje: date | None = None,
    inicio: date | None = None,
    fim: date | None = None,
) -> dict:
    """Marca o book e monta a matriz de precos pronta para o motor de risco."""
    marcacao = marcar(quadro, posicoes, hoje=hoje)
    matriz = matriz_pu(quadro, marcacao, inicio=inicio, fim=fim)

    comum = matriz.dropna(how="any")
    if len(comum) < MINIMO_OBSERVACOES:
        raise ErroRendaFixa(
            f"Só há {len(comum)} datas com preço para todos os papéis do book, "
            f"abaixo do mínimo de {MINIMO_OBSERVACOES}. Amplie o período ou tire "
            "do book o papel de emissão mais recente."
        )

    return {
        "marcacao": marcacao,
        "matriz": matriz,
        "pesos": pesos_por_valor_marcado(marcacao),
        "valor_marcado": marcacao["totais"]["valor_marcado"],
        "avisos": avisos_da_matriz(matriz),
    }


# --------------------------------------------------------------------------- #
# Book consolidado: acoes + renda fixa
# --------------------------------------------------------------------------- #

def valores_marcados(marcacao: dict) -> dict[str, float]:
    """id do papel -> valor marcado a mercado, a base de peso do consolidado."""
    return {l["id"]: l["valor_marcado"] for l in marcacao["posicoes"]}


def consolidar(
    precos_acoes: pd.DataFrame,
    pesos_acoes: dict[str, float],
    valor_acoes: float,
    matriz_rf: pd.DataFrame,
    valores_rf: dict[str, float],
) -> dict:
    """Junta os dois books numa matriz de precos e num vetor de pesos.

    Os dois lados chegam com bases diferentes — acoes sao dirigidas por peso
    (valor = peso x valor da carteira) e renda fixa por quantidade (valor =
    quantidade x PU). A unificacao e por VALOR MONETARIO: cada perna pesa o
    que vale em reais sobre o total dos dois books. E a unica base em que as
    duas classes sao comparaveis.

    Nao ha colisao de nome de coluna: ticker de acao e maiusculo com sufixo
    da bolsa, id de titulo e slug minusculo.
    """
    valor_rf = sum(valores_rf.values())
    total = valor_acoes + valor_rf
    if total <= 0:
        raise ErroRendaFixa("O book consolidado nao tem valor positivo.")

    # acoes: peso normalizado vira reais; renda fixa: ja esta em reais
    pesos = {t: (p * valor_acoes) / total for t, p in pesos_acoes.items()}
    pesos.update({papel: valor / total for papel, valor in valores_rf.items()})

    matriz = pd.concat([precos_acoes, matriz_rf], axis=1).sort_index()

    avisos = []
    ultimo_acoes = precos_acoes.dropna(how="any").index.max()
    ultimo_rf = matriz_rf.dropna(how="any").index.max()
    if pd.notna(ultimo_acoes) and pd.notna(ultimo_rf) and ultimo_acoes != ultimo_rf:
        avisos.append(
            _aviso(
                "calendarios_defasados",
                "aviso",
                f"A bolsa tem preço até {ultimo_acoes:%d/%m/%Y} e o Tesouro até "
                f"{ultimo_rf:%d/%m/%Y}. O book consolidado para na data mais "
                "antiga das duas, porque o motor só usa datas em comum.",
                ultimo_pregao=ultimo_acoes.strftime("%Y-%m-%d"),
                ultima_data_base=ultimo_rf.strftime("%Y-%m-%d"),
            )
        )

    comum = matriz.dropna(how="any")
    if len(comum) < MINIMO_OBSERVACOES:
        raise ErroRendaFixa(
            f"Só há {len(comum)} datas em comum entre a bolsa e o Tesouro no "
            f"período, abaixo do mínimo de {MINIMO_OBSERVACOES}."
        )

    avisos.extend(avisos_da_matriz(matriz))
    return {
        "matriz": matriz,
        "pesos": pesos,
        "valor_total": round(total, 2),
        "valor_acoes": round(valor_acoes, 2),
        "valor_renda_fixa": round(valor_rf, 2),
        "avisos": avisos,
    }
