const BASE = import.meta.env.VITE_API_URL || ''

async function trata(resp) {
  if (!resp.ok) {
    let detalhe = `Erro ${resp.status}`
    try {
      const json = await resp.json()
      if (typeof json.detail === 'string') detalhe = json.detail
      else if (Array.isArray(json.detail)) detalhe = json.detail.map((d) => d.msg).join(' · ')
    } catch {
      /* resposta sem corpo JSON */
    }
    throw new Error(detalhe)
  }
  return resp.json()
}

async function post(rota, corpo) {
  return trata(
    await fetch(`${BASE}${rota}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corpo),
    })
  )
}

async function get(rota, params) {
  const busca = params ? `?${new URLSearchParams(params)}` : ''
  return trata(await fetch(`${BASE}${rota}${busca}`))
}

/** Payload completo: os três VaRs, o book e a relação risco-retorno. */
export const analisar = (pedido) => post('/api/analise', pedido)

/** Somente o VaR empírico — contrato antigo, mantido para integrações. */
export const calcularVaREmpirico = (pedido) => post('/api/var/empirico', pedido)

/** Universo do Tesouro Direto no último dia útil publicado. */
export const titulosDisponiveis = () => get('/api/titulos-publicos/disponiveis')

/** Mesmo contrato de `analisar`, com marcação a mercado e avisos por cima. */
export const analisarRendaFixa = (pedido) => post('/api/analise/renda-fixa', pedido)

/** Os dois books na mesma análise, ponderados por valor de mercado. */
export const analisarConsolidado = (pedido) => post('/api/analise/consolidado', pedido)

/* --------------------------- catálogo ----------------------------- */

/**
 * Períodos rápidos da interface — vêm do backend para as telas não divergirem.
 * `escopo: 'ranking'` traz só as janelas que o ranking consegue calcular.
 */
export const listarPeriodos = (escopo) =>
  get('/api/fundos/periodos', escopo ? { escopo } : undefined)

/** Categorias de fundo oferecidas como filtro do ranking. */
export const listarCategorias = () => get('/api/fundos/categorias')

/** Benchmarks que o sistema sabe buscar (CDI, Ibovespa, IPCA, Selic...). */
export const listarBenchmarks = () => get('/api/fundos/benchmarks')

/** Data/hora do último download dos dados da CVM. */
export const statusFundos = () => get('/api/fundos/status')

/** Força a próxima consulta a reprocessar o que pode ter mudado na CVM. */
export const atualizarFundos = () => post('/api/fundos/atualizar')

/* ------------------------ análise de fundo ------------------------ */

/** Busca por nome, CNPJ, código CVM ou gestora. */
export const buscarFundos = (q) => get('/api/fundos/buscar', { q })

/**
 * Top 10 por retorno acumulado na janela escolhida — a descoberta da Visão
 * Geral. `categoria` vazia significa "todas as categorias".
 */
export const top10Fundos = (periodo, categoria) =>
  get('/api/fundos/top10', categoria ? { periodo, categoria } : { periodo })

/** Informações institucionais da classe. */
export const cadastroFundo = (cnpj) => get('/api/fundos/cadastro', { cnpj })

/**
 * Payload completo da análise individual.
 * `opcoes` aceita `periodo`, `benchmark` e o par `inicio`/`fim` do intervalo
 * personalizado; o que vier vazio simplesmente não entra na query.
 */
export const analiseFundo = (cnpj, opcoes = {}) => {
  const params = { cnpj }
  for (const chave of ['periodo', 'benchmark', 'inicio', 'fim']) {
    if (opcoes[chave]) params[chave] = opcoes[chave]
  }
  return get('/api/fundos/analise', params)
}

/** Composição da carteira do fundo no mês mais recente do CDA. */
export const composicaoFundo = (cnpj) => get('/api/fundos/composicao', { cnpj })

/* ------------------------------ book ------------------------------ */

/** Consolida as posições informadas numa carteira única. */
export const analiseBook = (posicoes, periodo, benchmarks) =>
  post('/api/book/analise', { posicoes, periodo, benchmarks })
