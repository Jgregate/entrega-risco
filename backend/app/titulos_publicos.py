"""Ingestao do historico de precos e taxas do Tesouro Direto.

Fonte unica: o CSV publico do Tesouro Transparente — sem cadastro, sem chave.
O arquivo traz o historico inteiro desde 2002 (hoje ~14 MB e 176 mil linhas),
com uma linha por (Tipo Titulo, Data Vencimento, Data Base). Baixar isso a
cada request esta fora de questao, entao a ingestao guarda o resultado em
dois niveis:

  1. memoria — variavel de modulo, no mesmo padrao de `data.py` e `selic.py`;
  2. disco   — pickle em `backend/.cache/`, para o historico sobreviver ao
               reload do uvicorn, que e o caso comum em desenvolvimento.

Se o download falhar, a camada cai para o cache anterior mesmo vencido e
marca o resultado como degradado, em vez de derrubar a rota. Só levanta
ErroTesouro quando nao ha download nem cache nenhum.

Particularidades do arquivo, verificadas na fonte: `sep=";"`, `decimal=","`,
`encoding="latin1"` e datas em formato brasileiro. Ha ainda uma oitava
coluna, `PU Base Manha`, que nao e usada em lugar nenhum do projeto.

Convencao de unidade: as taxas saem daqui como FRACAO (0,1425 para 14,25% ao
ano), nao como percentual. E o que o resto do projeto assume — a Selic em
`selic.py` faz a mesma divisao, e o `pct()` do front multiplica por 100.
Os PUs ficam em reais, como vem na fonte.
"""

from __future__ import annotations

import pickle
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests

URL_TESOURO = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv"
)

TTL_SEGUNDOS = 60 * 60 * 12

# (connect, read): o arquivo e grande e o servidor do Tesouro nao e rapido
TIMEOUT = (10, 180)

DIRETORIO_CACHE = Path(__file__).resolve().parent.parent / ".cache"
# o sufixo versiona o formato do pickle: mudou o parsing, invalida o que esta la
ARQUIVO_CACHE = "tesouro_direto_v1.pkl"

# nome na fonte -> nome usado no projeto. `PU Base Manha` fica de fora de proposito.
COLUNAS = {
    "Tipo Titulo": "tipo",
    "Data Vencimento": "vencimento",
    "Data Base": "data_base",
    "Taxa Compra Manha": "taxa_compra",
    "Taxa Venda Manha": "taxa_venda",
    "PU Compra Manha": "pu_compra",
    "PU Venda Manha": "pu_venda",
}

# sem esses campos a linha nao serve nem para marcacao nem para serie historica
ESSENCIAIS = ("tipo", "vencimento", "data_base", "pu_venda")

_MEMORIA: "Historico | None" = None


class ErroTesouro(Exception):
    """Falha ao obter ou validar o historico do Tesouro Direto."""


@dataclass(frozen=True)
class Historico:
    """O historico completo mais a procedencia de onde ele veio.

    `degradado` e True quando o download falhou e o que esta em `quadro` e
    cache vencido. Quem consome decide se avisa o usuario — a rota nao cai
    por causa disso.
    """

    quadro: pd.DataFrame
    origem: str
    baixado_em: float
    degradado: bool = False

    @property
    def baixado_em_iso(self) -> str:
        return datetime.fromtimestamp(self.baixado_em).isoformat(timespec="seconds")

    @property
    def data_base_max(self) -> pd.Timestamp:
        """Ultimo dia util publicado no arquivo."""
        return self.quadro["data_base"].max()

    def meta(self) -> dict:
        """Bloco de procedencia para anexar ao payload da API."""
        return {
            "origem": self.origem,
            "degradado": self.degradado,
            "baixado_em": self.baixado_em_iso,
            "data_base": self.data_base_max.strftime("%Y-%m-%d"),
            "linhas": int(len(self.quadro)),
        }


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

def parse_csv(conteudo: bytes) -> pd.DataFrame:
    """Le o CSV do Tesouro e devolve o quadro ja normalizado.

    Colunas de saida: tipo, vencimento, data_base, taxa_compra, taxa_venda,
    pu_compra, pu_venda. Taxas em fracao, PUs em reais, datas como Timestamp.
    """
    try:
        bruto = pd.read_csv(
            BytesIO(conteudo),
            sep=";",
            decimal=",",
            encoding="latin1",
        )
    except Exception as exc:
        raise ErroTesouro(f"Nao foi possivel ler o CSV do Tesouro: {exc}") from exc

    faltando = [c for c in COLUNAS if c not in bruto.columns]
    if faltando:
        raise ErroTesouro(
            "O CSV do Tesouro nao tem as colunas esperadas: " + ", ".join(faltando)
        )

    quadro = bruto[list(COLUNAS)].rename(columns=COLUNAS)

    for coluna in ("vencimento", "data_base"):
        quadro[coluna] = pd.to_datetime(quadro[coluna], dayfirst=True, errors="coerce")

    for coluna in ("taxa_compra", "taxa_venda", "pu_compra", "pu_venda"):
        quadro[coluna] = pd.to_numeric(quadro[coluna], errors="coerce")

    # percentual ao ano -> fracao, alinhado com o resto do projeto
    quadro["taxa_compra"] = quadro["taxa_compra"] / 100.0
    quadro["taxa_venda"] = quadro["taxa_venda"] / 100.0

    quadro["tipo"] = quadro["tipo"].astype(str).str.strip()

    # PU nao positivo nao e preco. Sao 48 linhas no arquivo inteiro, todas no dia
    # anterior ao vencimento de papeis com juros semestrais ja vencidos, e nenhuma
    # no universo disponivel — mas um zero no meio de uma serie de precos vira
    # -100% seguido de +inf no pct_change(), entao sai aqui e nao adiante.
    quadro.loc[quadro["pu_compra"] <= 0, "pu_compra"] = pd.NA
    quadro = quadro[quadro["pu_venda"] > 0]

    quadro = quadro.dropna(subset=list(ESSENCIAIS))
    if quadro.empty:
        raise ErroTesouro("O CSV do Tesouro nao trouxe nenhuma linha aproveitavel.")

    quadro = quadro.sort_values(["tipo", "vencimento", "data_base"], ignore_index=True)
    return quadro


# --------------------------------------------------------------------------- #
# Cache em disco
# --------------------------------------------------------------------------- #

def _caminho_cache() -> Path:
    """Resolvido na chamada, e nao no import, para o teste poder redirecionar."""
    return DIRETORIO_CACHE / ARQUIVO_CACHE


def _le_disco() -> Historico | None:
    caminho = _caminho_cache()
    if not caminho.exists():
        return None
    try:
        with caminho.open("rb") as arquivo:
            guardado = pickle.load(arquivo)
        return Historico(
            quadro=guardado["quadro"],
            origem="cache-disco",
            baixado_em=float(guardado["baixado_em"]),
        )
    except Exception:
        # cache corrompido ou de um formato antigo: trata como inexistente
        return None


def _grava_disco(historico: Historico) -> None:
    caminho = _caminho_cache()
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        # grava em temporario e renomeia: se cair no meio, nao deixa pickle pela metade
        temporario = caminho.with_suffix(".tmp")
        with temporario.open("wb") as arquivo:
            pickle.dump(
                {"quadro": historico.quadro, "baixado_em": historico.baixado_em},
                arquivo,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        temporario.replace(caminho)
    except Exception:
        # cache em disco e otimizacao, nao requisito: falhar aqui nao para nada
        pass


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #

def _baixa_bytes() -> bytes:
    """Isolado para o teste poder trocar sem tocar em rede."""
    try:
        resposta = requests.get(URL_TESOURO, timeout=TIMEOUT)
        resposta.raise_for_status()
    except Exception as exc:  # pragma: no cover - depende de rede
        raise ErroTesouro(
            f"Nao foi possivel baixar o CSV do Tesouro Transparente: {exc}"
        ) from exc
    if not resposta.content:
        raise ErroTesouro("O Tesouro Transparente devolveu um arquivo vazio.")
    return resposta.content


def _vencido(historico: Historico, agora: float) -> bool:
    return agora - historico.baixado_em >= TTL_SEGUNDOS


# --------------------------------------------------------------------------- #
# Entrada publica
# --------------------------------------------------------------------------- #

def carregar(usar_cache: bool = True) -> Historico:
    """Historico do Tesouro Direto, do cache quente ou da fonte.

    Ordem: memoria valida -> disco valido -> download. Se o download falhar,
    volta para o cache vencido (memoria ou disco) marcando `degradado=True`.
    Só levanta ErroTesouro se nao houver absolutamente nada a devolver.
    """
    global _MEMORIA
    agora = time.time()

    if usar_cache and _MEMORIA is not None and not _vencido(_MEMORIA, agora):
        return Historico(
            quadro=_MEMORIA.quadro,
            origem="cache-memoria",
            baixado_em=_MEMORIA.baixado_em,
        )

    do_disco = _le_disco() if usar_cache else None
    if do_disco is not None and not _vencido(do_disco, agora):
        _MEMORIA = do_disco
        return do_disco

    try:
        historico = Historico(
            quadro=parse_csv(_baixa_bytes()),
            origem="download",
            baixado_em=agora,
        )
    except ErroTesouro as exc:
        anterior = _MEMORIA or do_disco
        if anterior is None:
            raise
        # degradacao: o CSV atualiza uma vez por dia util, cache velho ainda serve
        return Historico(
            quadro=anterior.quadro,
            origem="cache-vencido",
            baixado_em=anterior.baixado_em,
            degradado=True,
        )

    _MEMORIA = historico
    _grava_disco(historico)
    return historico


# --------------------------------------------------------------------------- #
# Universo de titulos disponiveis
# --------------------------------------------------------------------------- #

def slug_tipo(tipo: str) -> str:
    """Nome do tipo em forma de identificador: 'Tesouro IPCA+' -> 'tesouro_ipca'."""
    sem_acento = unicodedata.normalize("NFKD", str(tipo))
    sem_acento = sem_acento.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_")


# nome comercial do Tesouro Direto -> codigo oficial do papel, que e como a
# mesa se refere a ele. O Tesouro so publica o nome comercial no CSV, entao o
# mapa mora aqui; tipo novo que apareca na fonte cai no proprio nome comercial.
CODIGOS_OFICIAIS = {
    "tesouro_prefixado": "LTN",
    "tesouro_prefixado_com_juros_semestrais": "NTN-F",
    "tesouro_selic": "LFT",
    "tesouro_ipca": "NTN-B Principal",
    "tesouro_ipca_com_juros_semestrais": "NTN-B",
    "tesouro_igpm_com_juros_semestrais": "NTN-C",
    "tesouro_renda": "NTN-B1",
    "tesouro_educa": "NTN-B2",
}


def codigo_oficial(tipo: str) -> str:
    """'Tesouro Prefixado' -> 'LTN'. Sem mapa, devolve o nome comercial."""
    return CODIGOS_OFICIAIS.get(slug_tipo(tipo), str(tipo).strip())


def rotulo_oficial(tipo: str, vencimento) -> str:
    """Como o papel e chamado na mesa: 'LTN 29', 'NTN-B 35'.

    O ano vai com dois digitos porque e assim que se fala do papel; o
    vencimento completo continua no payload, em campo proprio, para a
    interface mostrar a data oficial sem ambiguidade.
    """
    ano = pd.Timestamp(vencimento).year % 100
    return f"{codigo_oficial(tipo)} {ano:02d}"


def identificador(tipo: str, vencimento) -> str:
    """Chave estavel de um papel: '{tipo_slug}_{vencimento_iso}'.

    Estavel porque o par (tipo, vencimento) e o que identifica o titulo na
    fonte — nao ha codigo proprio no CSV. O `+` do nome cai no slug, mas
    'Tesouro IPCA+' e 'Tesouro IPCA+ com Juros Semestrais' seguem distintos.
    """
    return f"{slug_tipo(tipo)}_{pd.Timestamp(vencimento).date().isoformat()}"


def universo(quadro: pd.DataFrame, hoje: date | None = None) -> pd.DataFrame:
    """Papeis que dava para comprar no ultimo dia util publicado.

    'Disponivel' nao e um flag no CSV, e derivado de duas condicoes:

      1. `data_base == max(data_base)` — o ultimo dia util publicado. Amarrar
         no maximo do proprio arquivo resolve fim de semana, feriado e a
         defasagem de publicacao sem calendario nenhum na mao.
      2. `vencimento > hoje` — um papel que venceu ontem ainda aparece no
         ultimo dia util, mas nao e mais compravel.

    A comparacao em (2) e contra hoje de verdade, nao contra a data base:
    entre a publicacao e agora pode ter passado um vencimento.
    """
    if quadro.empty:
        return quadro.copy()

    hoje = hoje or date.today()
    data_base = quadro["data_base"].max()

    disponiveis = quadro[
        (quadro["data_base"] == data_base)
        & (quadro["vencimento"] > pd.Timestamp(hoje))
    ].copy()

    if disponiveis.empty:
        return disponiveis

    disponiveis["id"] = [
        identificador(t, v)
        for t, v in zip(disponiveis["tipo"], disponiveis["vencimento"])
    ]
    disponiveis["tipo_slug"] = disponiveis["tipo"].map(slug_tipo)

    # (tipo, vencimento) ja e chave na fonte; a garantia aqui e contra um
    # eventual duplicado no arquivo virar dois papeis iguais na lista
    disponiveis = disponiveis.drop_duplicates(subset="id", keep="last")

    return disponiveis.sort_values(["tipo", "vencimento"], ignore_index=True)


def serializa_universo(disponiveis: pd.DataFrame) -> list[dict]:
    """Lista de papeis pronta para o front, agrupavel por tipo."""
    return [
        {
            "id": linha["id"],
            "tipo": linha["tipo"],
            "tipo_slug": linha["tipo_slug"],
            "codigo": codigo_oficial(linha["tipo"]),
            "rotulo": rotulo_oficial(linha["tipo"], linha["vencimento"]),
            "vencimento": linha["vencimento"].strftime("%Y-%m-%d"),
            "taxa_venda": round(float(linha["taxa_venda"]), 6),
            "pu_venda": round(float(linha["pu_venda"]), 2),
        }
        for _, linha in disponiveis.iterrows()
    ]


def serie_pu(quadro: pd.DataFrame, tipo: str, vencimento) -> pd.Series:
    """Serie historica de `PU Venda Manha` de um papel, indexada por data base.

    E uma serie de precos como qualquer outra: e o que permite marcar a
    posicao em qualquer data e, adiante, alimentar o motor de risco sem
    escrever calculo novo.
    """
    papel = quadro[
        (quadro["tipo"] == tipo) & (quadro["vencimento"] == pd.Timestamp(vencimento))
    ]
    serie = papel.set_index("data_base")["pu_venda"].sort_index()
    return serie[~serie.index.duplicated(keep="last")]


def limpar_cache(memoria: bool = True, disco: bool = False) -> None:
    """Descarta o cache. Usado pelos testes e util para forcar recarga."""
    global _MEMORIA
    if memoria:
        _MEMORIA = None
    if disco:
        caminho = _caminho_cache()
        if caminho.exists():
            caminho.unlink()
