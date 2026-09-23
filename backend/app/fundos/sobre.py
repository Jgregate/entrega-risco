"""Leitura qualitativa de um fundo, a partir do cadastro da CVM.

O que esta tela responde e "o que este fundo faz com o dinheiro?" - a pergunta
que nenhum indicador responde. A fonte e a mesma de sempre (o cadastro de
classes e fundos da CVM), e a regra do projeto continua valendo: **nada aqui e
inventado**. Cada campo ou sai direto de uma coluna do cadastro, ou e a
traducao de uma classificacao que a propria CVM/ANBIMA publica.

Duas categorias de campo, e a interface distingue as duas:

- REGISTRAL: gestora, administrador, diretor, publico-alvo, benchmark,
  condominio, previdencia, exterior. Vem literalmente do cadastro.
- DERIVADO: estrategia, classe de ativos, mercados, perfil de risco e
  horizonte. Sao leituras da classificacao ANBIMA/CVM - `Multimercados L/S -
  Direcional` significa comprado e vendido em acoes com exposicao liquida
  direcional, e isso e o que o texto diz. Nada alem do que o codigo da
  classificacao ja carrega.

O que a CVM NAO publica em nenhum arquivo: descricao textual da gestora,
descricao livre da estrategia e o nome do gestor de carteira (o `Diretor` do
cadastro e o responsavel perante a CVM, que nao e a mesma pessoa). Esses
campos saem como None e a interface mostra a lacuna - ver `Cadastro.jsx`, que
segue a mesma regra na ficha cadastral.

Uma observacao sobre a classificacao ANBIMA no cadastro da CVM: ela vem
TRUNCADA em 40 caracteres ("Renda Fixa Duracao Livre Credito Liv"), entao os
tokens abaixo sao propositalmente curtos.
"""

from __future__ import annotations

# Estrategia, na ordem de especificidade: o primeiro token que aparecer na
# classificacao ANBIMA manda. Cada entrada e (token, rotulo, como o gestor
# implementa) - e a definicao da propria categoria ANBIMA em portugues corrido.
ESTRATEGIAS = (
    ("l/s - neutro", "Long & Short Neutro",
     "Compra e vende ações simultaneamente e neutraliza a exposição líquida à "
     "bolsa, buscando ganhar na diferença entre as duas pontas."),
    ("l/s - direcional", "Long & Short Direcional",
     "Mantém posições compradas e vendidas em ações e assume uma exposição "
     "líquida direcional à bolsa conforme a leitura da equipe."),
    ("macro", "Macro",
     "Monta posições em juros, câmbio, bolsa e commodities a partir de "
     "cenários macroeconômicos, com liberdade para mudar de mercado."),
    ("juros e moedas", "Macro — juros e moedas",
     "Concentra as posições em juros e câmbio, sem exposição relevante a "
     "bolsa."),
    ("trading", "Tática (trading)",
     "Opera taticamente, com giro alto e posições de curta duração."),
    ("capital protegido", "Capital protegido",
     "Estrutura as posições para limitar a perda do capital aplicado, abrindo "
     "mão de parte do ganho em troca dessa proteção."),
    ("balanceados", "Alocação balanceada",
     "Distribui o patrimônio entre classes de ativos em proporções definidas "
     "pelo mandato e rebalanceia a carteira ao longo do tempo."),
    ("data alvo", "Alocação por data-alvo",
     "Reduz gradualmente o risco da carteira à medida que se aproxima da data "
     "alvo do plano."),
    ("dinâmico", "Multiestratégia dinâmica",
     "Muda a alocação entre classes de ativos conforme o cenário, sem "
     "percentuais fixos."),
    ("estrat", "Estratégia específica",
     "Concentra-se em uma única estratégia declarada no regulamento."),
    ("grau de inv", "Crédito — grau de investimento",
     "Compra títulos de crédito privado restritos às classificações de risco "
     "consideradas grau de investimento."),
    ("crédito", "Crédito",
     "Compra títulos de crédito privado sem restrição de classificação de "
     "risco, assumindo risco de crédito para buscar prêmio sobre o CDI."),
    ("soberano", "Renda fixa soberana",
     "Investe em títulos públicos federais, sem risco de crédito privado."),
    ("simples", "Renda fixa simples",
     "Mantém a carteira em títulos públicos e de baixo risco de crédito, no "
     "formato simplificado previsto na regulação."),
    ("índice", "Indexada",
     "Acompanha a carteira teórica de um índice de referência, sem seleção "
     "ativa de ativos."),
    ("indexad", "Indexada",
     "Acompanha a carteira teórica de um índice de referência, sem seleção "
     "ativa de ativos."),
    ("valor/crescimento", "Long Only — valor e crescimento",
     "Seleciona ações por fundamentos (preço abaixo do valor estimado ou "
     "crescimento de resultados) e mantém a posição comprada."),
    ("dividendos", "Long Only — dividendos",
     "Seleciona ações de empresas com histórico de distribuição de proventos "
     "e mantém a posição comprada."),
    ("small caps", "Long Only — small caps",
     "Seleciona ações de empresas de menor capitalização, onde a dispersão de "
     "resultados é maior."),
    ("sustentabilidade", "Long Only — ESG",
     "Seleciona ações por critérios de sustentabilidade e governança, além "
     "dos fundamentos."),
    ("governança", "Long Only — ESG",
     "Seleciona ações por critérios de sustentabilidade e governança, além "
     "dos fundamentos."),
    ("setoriais", "Long Only setorial",
     "Concentra a carteira em um setor específico da bolsa."),
    ("mono ação", "Long Only concentrada",
     "Concentra a carteira em uma única companhia."),
    ("fmp - fgts", "Long Only — FMP-FGTS",
     "Carteira formada com recursos de FGTS aplicados em ações de companhias "
     "específicas, com prazo de carência."),
    ("fechados de ações", "Ações em condomínio fechado",
     "Mantém carteira de ações sem resgate: a saída do cotista é pela venda "
     "da cota, não pelo fundo."),
    ("ações ativo", "Renda variável ativa",
     "Seleciona ativamente as ações da carteira, buscando superar o índice de "
     "referência."),
    ("ações livre", "Renda variável — seleção livre",
     "Seleciona livremente as ações da carteira, mantendo a maior parte do "
     "patrimônio em renda variável."),
    ("multimercados livre", "Multiestratégia (livre)",
     "Não se compromete com uma classe de ativos: combina as estratégias que "
     "a equipe julgar melhores em cada momento."),
    ("cambial", "Cambial",
     "Acompanha a variação de uma moeda estrangeira, normalmente o dólar."),
)

# Classe de ativos principal, por categoria (ver `cadastro.CATEGORIAS`).
CLASSE_ATIVOS = {
    "renda_fixa": "Títulos de renda fixa (públicos e privados)",
    "acoes": "Ações",
    "multimercado": "Várias classes — juros, câmbio, bolsa e crédito",
    "cambial": "Moeda estrangeira e derivativos de câmbio",
    "fii": "Ativos imobiliários (imóveis, CRI e cotas de FII)",
    "etf": "Cesta de ativos que replica um índice",
    "fidc": "Direitos creditórios",
    "fip": "Participações em empresas",
    "fiagro": "Ativos do agronegócio",
}

MERCADOS = {
    "renda_fixa": "Juros e crédito privado no Brasil",
    "acoes": "Bolsa brasileira",
    "multimercado": "Juros, câmbio, bolsa e crédito",
    "cambial": "Câmbio",
    "fii": "Mercado imobiliário brasileiro",
    "etf": "O mercado do índice replicado",
    "fidc": "Crédito privado",
    "fip": "Empresas de capital fechado",
    "fiagro": "Agronegócio",
}

PERFIL_RISCO = {
    "renda_fixa": "Moderado",
    "acoes": "Arrojado",
    "multimercado": "Moderado a arrojado",
    "cambial": "Arrojado",
    "fii": "Arrojado",
    "fidc": "Arrojado",
    "fip": "Arrojado",
    "fiagro": "Arrojado",
}

HORIZONTE = {
    "renda_fixa": "Médio prazo (1 a 3 anos)",
    "acoes": "Longo prazo (acima de 5 anos)",
    "multimercado": "Médio a longo prazo (2 a 5 anos)",
    "cambial": "Curto prazo (uso tático ou proteção cambial)",
    "fii": "Longo prazo (acima de 5 anos)",
    "fidc": "Longo prazo — baixa liquidez",
    "fip": "Longo prazo — baixa liquidez",
    "fiagro": "Longo prazo (acima de 5 anos)",
}

# Sufixos da classificacao ANBIMA de previdencia -> classe do ativo por baixo
# da estrutura previdenciaria. "Previdencia" e o veiculo, nao o mandato.
_BASE_PREVIDENCIA = (
    ("previdência rf", "renda_fixa"),
    ("previdência ações", "acoes"),
    ("previdência multimercado", "multimercado"),
    ("previdência balanceados", "multimercado"),
    ("previdência data alvo", "multimercado"),
)


def _txt(valor) -> str | None:
    if valor is None:
        return None
    s = str(valor).strip()
    return s or None


def _baixo(valor) -> str:
    return (_txt(valor) or "").lower()


def _inicial_minuscula(texto: str) -> str:
    """Minúscula só na primeira letra — o resto pode ter nome próprio
    ("Juros e crédito no Brasil" não pode virar "no brasil")."""
    return texto[:1].lower() + texto[1:]


def _classe_base(dados: dict, categoria: str | None) -> str | None:
    """Categoria do MANDATO. Igual à categoria do fundo, exceto em
    previdência, onde o mandato está na classificação ANBIMA."""
    if categoria != "previdencia":
        return categoria
    anbima = _baixo(dados.get("classificacao_anbima"))
    for prefixo, base in _BASE_PREVIDENCIA:
        if anbima.startswith(prefixo):
            return base
    return None


def _estrategia(dados: dict) -> tuple[str, str] | None:
    anbima = _baixo(dados.get("classificacao_anbima"))
    if not anbima:
        return None
    for token, rotulo, descricao in ESTRATEGIAS:
        if token in anbima:
            return rotulo, descricao
    return None


def _horizonte(dados: dict, categoria: str | None, base: str | None) -> str | None:
    if categoria == "previdencia":
        return "Longo prazo — acumulação para a aposentadoria"
    anbima = _baixo(dados.get("classificacao_anbima"))
    if base == "renda_fixa" and ("duração baixa" in anbima or "simples" in anbima):
        return "Curto prazo (até 1 ano)"
    return HORIZONTE.get(base or "")


# O campo `Indicador_Desempenho` da CVM e texto livre padronizado, e uma parte
# dos fundos preenche com um sentinela de "sem benchmark". Tratar isso como
# rotulo produziria "tem Nao se aplica como referencia" no resumo.
_SEM_BENCHMARK = ("não se aplica", "nao se aplica", "não aplicável", "nao aplicavel", "n/a")


def _benchmark(dados: dict) -> str | None:
    valor = _txt(dados.get("benchmark"))
    if valor is None or valor.lower() in _SEM_BENCHMARK:
        return None
    return valor


def _exterior(dados: dict) -> str | None:
    """Campo registral `Permitido_Aplicacao_CemPorCento_Exterior`, com a
    classificação ANBIMA como complemento quando ela cita o exterior."""
    permitido = _txt(dados.get("cem_por_cento_exterior"))
    exterior_anbima = "exterior" in _baixo(dados.get("classificacao_anbima"))
    if permitido == "Sim":
        return "Sim — a classe é autorizada a aplicar até 100% no exterior"
    if exterior_anbima:
        return "Sim — a classificação ANBIMA indica investimento no exterior"
    if permitido == "Não":
        return "Não é autorizada a aplicar 100% no exterior"
    return None


def _caracteristicas(dados: dict) -> list[str]:
    """Só fatos registrais, um por campo preenchido do cadastro."""
    itens = []
    if _txt(dados.get("forma_condominio")) == "Fechado":
        itens.append("Condomínio fechado — não há resgate; a saída é pela venda da cota")
    if _txt(dados.get("exclusivo")) == "Sim":
        itens.append("Fundo exclusivo — feito para um único cotista ou grupo")
    if _txt(dados.get("previdenciario")) == "Sim":
        itens.append("Estrutura previdenciária (PGBL/VGBL)")
    if _txt(dados.get("classe_esg")) == "Sim":
        itens.append("Classe identificada como ESG no cadastro da CVM")
    if _txt(dados.get("entidade_investimento")) == "Sim":
        itens.append("Entidade de investimento — ativos avaliados a valor justo")
    trib = _txt(dados.get("tributacao_longo_prazo"))
    if trib == "Sim":
        itens.append("Tributação de longo prazo (alíquota regressiva a partir de 22,5%)")
    elif trib == "Não":
        itens.append("Tributação de curto prazo (alíquota mínima de 20%)")
    return itens


def _resumo(campos: dict, dados: dict) -> str | None:
    """Parágrafo em linguagem natural — só com as partes que existem."""
    frases = []

    abertura = "O fundo"
    if campos["gestora"]:
        abertura += f" é gerido pela {campos['gestora']}"
    if campos["estrategia"]:
        abertura += (
            f"{' e' if campos['gestora'] else ''} tem a estratégia classificada "
            f"como {campos['estrategia']}"
        )
    elif campos["classe_ativos"]:
        abertura += (
            f"{' e' if campos['gestora'] else ''} investe em "
            f"{_inicial_minuscula(campos['classe_ativos'])}"
        )
    if abertura != "O fundo":
        frases.append(abertura + ".")

    if campos["implementacao"]:
        frases.append(campos["implementacao"])

    if campos["mercados"]:
        frases.append(f"Atua em {_inicial_minuscula(campos['mercados'])}.")

    referencia = []
    if campos["benchmark"]:
        referencia.append(f"tem {campos['benchmark']} como referência")
    if campos["perfil_risco"]:
        referencia.append(
            f"apresenta perfil de risco {_inicial_minuscula(campos['perfil_risco'])}"
        )
    if referencia:
        frases.append("O fundo " + " e ".join(referencia) + ".")

    destino = []
    if campos["publico_alvo"]:
        destino.append(
            f"é destinado a investidores do tipo {campos['publico_alvo'].lower()}"
        )
    if campos["horizonte"]:
        destino.append(f"sugere horizonte de {_inicial_minuscula(campos['horizonte'])}")
    if destino:
        frases.append("Ele " + " e ".join(destino) + ".")

    return " ".join(frases) or None


def perfil(dados: dict | None, categoria: str | None = None) -> dict:
    """Ficha qualitativa do fundo. Campo sem fonte vem como None.

    `categoria` é a chave de `cadastro.CATEGORIAS`; quando não vier, sai de
    `cadastro.categoria(dados)`.
    """
    if not dados:
        return {}

    if categoria is None:
        from .cadastro import categoria as classifica  # evita import circular
        categoria = classifica(dados)

    base = _classe_base(dados, categoria)
    estrategia = _estrategia(dados)

    campos = {
        # registral
        "gestora": _txt(dados.get("gestora")),
        "descricao_gestora": None,  # a CVM não publica texto sobre a gestora
        "administrador": _txt(dados.get("administrador")),
        "responsavel": _txt(dados.get("diretor")),
        "equipe_gestao": None,  # idem: o cadastro não traz o gestor de carteira
        "benchmark": _benchmark(dados),
        "publico_alvo": _txt(dados.get("publico_alvo")),
        "classificacao_anbima": _txt(dados.get("classificacao_anbima")),
        "classificacao_cvm": _txt(dados.get("classificacao_cvm")),
        "exterior": _exterior(dados),
        "caracteristicas": _caracteristicas(dados),
        # derivado da classificação
        "categoria": categoria,
        "estrategia": estrategia[0] if estrategia else None,
        "implementacao": estrategia[1] if estrategia else None,
        "classe_ativos": CLASSE_ATIVOS.get(base or ""),
        "mercados": MERCADOS.get(base or ""),
        "perfil_risco": PERFIL_RISCO.get(base or ""),
        "horizonte": _horizonte(dados, categoria, base),
    }
    campos["resumo"] = _resumo(campos, dados)
    return campos
