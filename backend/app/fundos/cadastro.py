"""Cadastro institucional das classes de fundos (CVM, dados abertos).

A CVM publica o cadastro em tres arquivos dentro de
`CAD/DADOS/registro_fundo_classe.zip`, e so a combinacao dos tres responde o
que a tela de Informacoes do Fundo precisa:

  registro_fundo.csv     o FUNDO      -> gestora, administrador, RCVM 175
  registro_classe.csv    a CLASSE     -> CNPJ negociado, benchmark, ANBIMA...
  registro_subclasse.csv a SUBCLASSE  -> previdencia

O informe diario e por CLASSE (`CNPJ_FUNDO_CLASSE`), entao a classe e a
unidade do sistema inteiro: e ela que tem cota, patrimonio e cotistas. Fundo e
subclasse entram so para preencher campos que nao existem no nivel da classe.

O que NAO existe em nenhum dos tres: taxa de administracao, taxa de
performance e prazo de resgate. O `cad_fi.csv` legado ainda traz as duas taxas,
mas so para os fundos que nunca migraram para a RCVM 175 - na pratica uma
fracao minima do cadastro atual. Por isso esses campos sao opcionais aqui e
ficam vazios quando a CVM nao publica: quem informa e o usuario, na posicao do
book. Ver `analytics.py` e `book.py`.
"""

from __future__ import annotations

import io
import re
import sqlite3
import time
import zipfile

import pandas as pd
import requests

from .._certs import sessao_requests

REGISTRY_URL = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"
CAD_FI_URL = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi.csv"

REQUEST_TIMEOUT = 120
ATUALIZACAO_HORAS = 6

# Situacao considerada "ativa" - mesma regra que o modulo ja usava.
SITUACAO_ATIVA = "Em Funcionamento Normal"

# Colunas da tabela `cadastro`, na ordem de insercao. Tudo que a CVM publica e
# a interface exibe; o que ela nao publica simplesmente fica NULL.
COLUNAS = (
    "cnpj_fmt",
    "codigo_cvm",
    "nome",
    "tipo_classe",
    "situacao",
    "data_inicio",
    "data_registro",
    "classificacao_cvm",
    "classificacao_anbima",
    "benchmark",
    "classe_cotas",
    "tributacao_longo_prazo",
    "entidade_investimento",
    "cem_por_cento_exterior",
    "classe_esg",
    "forma_condominio",
    "exclusivo",
    "publico_alvo",
    "patrimonio_liquido_cad",
    "data_patrimonio_cad",
    "custodiante",
    "auditor",
    "cnpj_fundo",
    "tipo_fundo",
    "gestora",
    "administrador",
    "diretor",
    "data_adaptacao_rcvm175",
    "data_constituicao_fundo",
    "previdenciario",
    "taxa_administracao",
    "taxa_performance",
    "atualizado_em",
)

_CRIA_TABELA = f"""
CREATE TABLE IF NOT EXISTS cadastro (
    {COLUNAS[0]} TEXT PRIMARY KEY,
    {", ".join(f"{c} TEXT" for c in COLUNAS[1:-3])},
    taxa_administracao REAL,
    taxa_performance   REAL,
    atualizado_em      REAL NOT NULL
)
"""

def cria_tabelas(conn: sqlite3.Connection) -> None:
    conn.execute(_CRIA_TABELA)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cadastro_nome ON cadastro (nome)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cadastro_gestora ON cadastro (gestora)")


def cnpj_digitos(valor) -> str:
    """So os 14 digitos, sem pontuacao - a forma canonica de comparar CNPJ
    entre arquivos que os formatam de jeitos diferentes."""
    return re.sub(r"\D", "", str(valor)).zfill(14)


def cnpj_formatado(valor) -> str:
    d = cnpj_digitos(valor)
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"


def _texto(valor):
    """Normaliza celula de CSV da CVM para texto limpo ou None."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    s = str(valor).strip()
    return s or None


def _booleano(valor):
    """'S'/'N' da CVM -> 'Sim'/'Nao' (texto, porque a coluna guarda texto e a
    interface exibe o rotulo direto). Qualquer outra coisa vira None."""
    s = _texto(valor)
    if s is None:
        return None
    u = s.upper()
    if u in ("S", "SIM"):
        return "Sim"
    if u in ("N", "NAO", "NÃO"):
        return "Não"
    return s


def _data(valor):
    """Datas da CVM ja vem em ISO (YYYY-MM-DD); so valida e devolve texto."""
    s = _texto(valor)
    if s is None:
        return None
    try:
        return pd.to_datetime(s).date().isoformat()
    except (ValueError, TypeError):
        return None


def _numero(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    try:
        return float(valor)
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------------- #
# Download e parsing
# --------------------------------------------------------------------------- #

def _baixa(url: str, timeout: int = REQUEST_TIMEOUT, tentativas: int = 3) -> bytes:
    erro: Exception | None = None
    for i in range(tentativas):
        try:
            resp = sessao_requests().get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            erro = exc
            if i < tentativas - 1:
                time.sleep(1.5 * (i + 1))
    raise erro  # type: ignore[misc]


def _le_csv(z: zipfile.ZipFile, nome: str, colunas: list[str]) -> pd.DataFrame:
    """Os CSVs do cadastro sao latin-1 (nao UTF-8) e mudam de colunas entre
    safras; `colunas` e o que queremos, e o que nao existir vira NaN."""
    with z.open(nome) as f:
        cabecalho = pd.read_csv(f, sep=";", encoding="latin1", nrows=0)
    presentes = [c for c in colunas if c in cabecalho.columns]
    with z.open(nome) as f:
        df = pd.read_csv(f, sep=";", encoding="latin1", usecols=presentes, low_memory=False)
    for c in colunas:
        if c not in df.columns:
            df[c] = None
    return df


def _taxas_legado() -> pd.DataFrame:
    """Taxa de adm/performance do `cad_fi.csv` legado, indexadas pelo CNPJ do
    FUNDO. Cobre so os fundos que ainda constam naquela base antiga; devolve
    vazio (sem quebrar) se a CVM tirar o arquivo do ar."""
    try:
        conteudo = _baixa(CAD_FI_URL, tentativas=2)
    except requests.RequestException:
        return pd.DataFrame(columns=["cnpj_fundo", "taxa_administracao", "taxa_performance"])

    df = pd.read_csv(
        io.BytesIO(conteudo), sep=";", encoding="latin1", low_memory=False,
        usecols=lambda c: c in ("CNPJ_FUNDO", "TAXA_ADM", "TAXA_PERFM"),
    )
    if "CNPJ_FUNDO" not in df.columns:
        return pd.DataFrame(columns=["cnpj_fundo", "taxa_administracao", "taxa_performance"])

    df = df.rename(
        columns={"TAXA_ADM": "taxa_administracao", "TAXA_PERFM": "taxa_performance"}
    )
    for c in ("taxa_administracao", "taxa_performance"):
        if c not in df.columns:
            df[c] = None
    df["cnpj_fundo"] = df["CNPJ_FUNDO"].map(cnpj_digitos)
    df = df.dropna(subset=["taxa_administracao", "taxa_performance"], how="all")
    return df[["cnpj_fundo", "taxa_administracao", "taxa_performance"]].drop_duplicates(
        subset="cnpj_fundo"
    )


def _monta_cadastro() -> pd.DataFrame:
    """Baixa e junta os tres niveis do cadastro numa linha por CLASSE."""
    z = zipfile.ZipFile(io.BytesIO(_baixa(REGISTRY_URL)))

    classe = _le_csv(z, "registro_classe.csv", [
        "ID_Registro_Fundo", "ID_Registro_Classe", "CNPJ_Classe", "Codigo_CVM",
        "Data_Registro", "Data_Inicio", "Tipo_Classe", "Denominacao_Social",
        "Situacao", "Classificacao", "Indicador_Desempenho", "Classe_Cotas",
        "Classificacao_Anbima", "Tributacao_Longo_Prazo", "Entidade_Investimento",
        "Permitido_Aplicacao_CemPorCento_Exterior", "Classe_ESG", "Forma_Condominio",
        "Exclusivo", "Publico_Alvo", "Patrimonio_Liquido", "Data_Patrimonio_Liquido",
        "Custodiante", "Auditor",
    ])
    fundo = _le_csv(z, "registro_fundo.csv", [
        "ID_Registro_Fundo", "CNPJ_Fundo", "Tipo_Fundo", "Gestor", "Administrador",
        "Diretor", "Data_Adaptacao_RCVM175", "Data_Constituicao",
    ])
    try:
        subclasse = _le_csv(z, "registro_subclasse.csv", [
            "ID_Registro_Classe", "Previdenciario",
        ])
    except KeyError:
        subclasse = pd.DataFrame(columns=["ID_Registro_Classe", "Previdenciario"])

    df = classe.merge(fundo, on="ID_Registro_Fundo", how="left")

    # Uma classe pode ter varias subclasses. Previdencia e uma caracteristica
    # do produto, nao da subclasse individual: basta uma previdenciaria para a
    # classe ser tratada como previdencia.
    if len(subclasse):
        prev = (
            subclasse.assign(
                _p=subclasse["Previdenciario"].astype(str).str.strip().str.upper().eq("S")
            )
            .groupby("ID_Registro_Classe")["_p"]
            .any()
            .rename("previdenciario_bool")
        )
        df = df.merge(prev, left_on="ID_Registro_Classe", right_index=True, how="left")
    else:
        df["previdenciario_bool"] = None

    df["cnpj_fundo_dig"] = df["CNPJ_Fundo"].map(cnpj_digitos)
    taxas = _taxas_legado()
    df = df.merge(taxas, left_on="cnpj_fundo_dig", right_on="cnpj_fundo", how="left")

    # uma classe e uma linha; se a CVM repetir o CNPJ, a primeira ocorrencia vale
    return df.drop_duplicates(subset="CNPJ_Classe")


def _linhas(df: pd.DataFrame, agora: float) -> list[tuple]:
    def prev(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return "Sim" if bool(v) else "Não"

    return [
        (
            cnpj_formatado(r.CNPJ_Classe),
            _texto(r.Codigo_CVM),
            _texto(r.Denominacao_Social),
            _texto(r.Tipo_Classe),
            _texto(r.Situacao),
            _data(r.Data_Inicio),
            _data(r.Data_Registro),
            _texto(r.Classificacao),
            _texto(r.Classificacao_Anbima),
            _texto(r.Indicador_Desempenho),
            _texto(r.Classe_Cotas),
            _booleano(r.Tributacao_Longo_Prazo),
            _booleano(r.Entidade_Investimento),
            _booleano(r.Permitido_Aplicacao_CemPorCento_Exterior),
            _booleano(r.Classe_ESG),
            _texto(r.Forma_Condominio),
            _booleano(r.Exclusivo),
            _texto(r.Publico_Alvo),
            _texto(r.Patrimonio_Liquido),
            _data(r.Data_Patrimonio_Liquido),
            _texto(r.Custodiante),
            _texto(r.Auditor),
            cnpj_formatado(r.CNPJ_Fundo) if _texto(r.CNPJ_Fundo) else None,
            _texto(r.Tipo_Fundo),
            _texto(r.Gestor),
            _texto(r.Administrador),
            _texto(r.Diretor),
            _data(r.Data_Adaptacao_RCVM175),
            _data(r.Data_Constituicao),
            prev(r.previdenciario_bool),
            _numero(r.taxa_administracao),
            _numero(r.taxa_performance),
            agora,
        )
        for r in df.itertuples()
    ]


# --------------------------------------------------------------------------- #
# Persistencia
# --------------------------------------------------------------------------- #

def precisa_rebaixar(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT MAX(atualizado_em) FROM cadastro").fetchone()
    if row is None or row[0] is None:
        return True
    return (time.time() - row[0]) >= ATUALIZACAO_HORAS * 3600


def rebaixa(conn: sqlite3.Connection) -> None:
    """Rebaixa o cadastro inteiro. Se a rede falhar mas ja houver cadastro em
    banco, mantem o que existe - cadastro velho e melhor que tela vazia."""
    tem_dados = conn.execute("SELECT 1 FROM cadastro LIMIT 1").fetchone() is not None
    try:
        df = _monta_cadastro()
    except requests.RequestException:
        if tem_dados:
            return
        raise

    agora = time.time()
    conn.execute("DELETE FROM cadastro")
    conn.executemany(
        f"INSERT OR REPLACE INTO cadastro ({', '.join(COLUNAS)}) "
        f"VALUES ({', '.join('?' * len(COLUNAS))})",
        _linhas(df, agora),
    )
    conn.commit()


def invalida(conn: sqlite3.Connection) -> None:
    """Zera o carimbo para a proxima consulta rebaixar, sem apagar os dados
    (a tela continua funcionando enquanto o download nao termina)."""
    conn.execute("UPDATE cadastro SET atualizado_em = 0")
    conn.commit()


# --------------------------------------------------------------------------- #
# Categorias de fundo
# --------------------------------------------------------------------------- #
#
# Taxonomia do filtro de categoria do ranking. Ela sai inteira do que a CVM
# publica - `Tipo_Fundo` (o veiculo: FI, FIDC, FIP, FII, FIIM, FIAGRO),
# `Classificacao` (a classe CVM) e a classificacao ANBIMA - nesta ordem de
# precedencia, porque o veiculo e um fato registral e a classe so existe para
# os fundos do tipo FI/FIF.
#
# Nao confundir com `book.classe_do_fundo`: aquela agrupa a alocacao do book em
# quatro classes macro (e separa "Internacional"); esta separa os veiculos
# estruturados, que o investidor escolhe como produtos distintos.

CATEGORIAS = (
    {"chave": "renda_fixa", "rotulo": "Renda Fixa"},
    {"chave": "acoes", "rotulo": "Ações"},
    {"chave": "multimercado", "rotulo": "Multimercado"},
    {"chave": "cambial", "rotulo": "Cambiais"},
    {"chave": "fii", "rotulo": "Imobiliários (FII)"},
    {"chave": "etf", "rotulo": "Índice (ETF)"},
    {"chave": "previdencia", "rotulo": "Previdência (PGBL/VGBL)"},
    {"chave": "fidc", "rotulo": "FIDC"},
    {"chave": "fip", "rotulo": "FIP"},
    {"chave": "fiagro", "rotulo": "Fiagro"},
)

CATEGORIAS_POR_CHAVE = {c["chave"]: c for c in CATEGORIAS}

# Tipo_Fundo -> categoria, para os veiculos que ja se definem pelo registro.
# FIIM e o "fundo de indice de mercado" da CVM, o que o mercado chama de ETF.
_CATEGORIA_POR_TIPO = {
    "FII": "fii",
    "FICART": "fii",
    "FIIM": "etf",
    "FIDC": "fidc",
    "FIP": "fip",
    "FMIEE": "fip",
    "FIAGRO": "fiagro",
    "FAPI": "previdencia",
}

# Prefixo da classe CVM (ou da ANBIMA, quando a CVM nao classifica) -> categoria
_CATEGORIA_POR_CLASSE = (
    ("ações", "acoes"),
    ("acoes", "acoes"),
    ("fmp-fgts", "acoes"),
    ("renda fixa", "renda_fixa"),
    ("multimercado", "multimercado"),
    ("cambial", "cambial"),
)


def _minusculo(valor) -> str:
    return (_texto(valor) or "").strip().lower()


def categoria(dados) -> str | None:
    """Categoria de uma linha do cadastro, ou None quando nao da para dizer.

    `dados` e qualquer mapeamento com as colunas do cadastro (o dict de
    `cadastro_fundo`, uma linha do registry). Campo ausente nunca vira palpite:
    fundo sem tipo, sem classe CVM e sem ANBIMA sai como None e fica de fora
    de qualquer filtro.
    """
    tipo = (_texto(dados.get("tipo_fundo")) or "").strip().upper()
    if tipo in _CATEGORIA_POR_TIPO:
        return _CATEGORIA_POR_TIPO[tipo]

    anbima = _minusculo(dados.get("classificacao_anbima"))
    # previdencia vem antes da classe: "Previdência RF Duração Livre" tem
    # Classificacao = "Renda Fixa" na CVM, mas o produto e previdenciario
    if _minusculo(dados.get("previdenciario")) == "sim" or anbima.startswith("previd"):
        return "previdencia"

    for prefixo, chave in _CATEGORIA_POR_CLASSE:
        if _minusculo(dados.get("classificacao_cvm")).startswith(prefixo):
            return chave
    for prefixo, chave in _CATEGORIA_POR_CLASSE:
        if anbima.startswith(prefixo):
            return chave
    return None


def rotulo_categoria(chave: str | None) -> str | None:
    item = CATEGORIAS_POR_CHAVE.get(chave or "")
    return item["rotulo"] if item else None
