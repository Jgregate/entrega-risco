const BASE = import.meta.env.VITE_API_URL || ''

// O proxy do Vite responde 500 com corpo não-JSON quando não consegue falar com
// o FastAPI. Sem esta mensagem, backend fora do ar e falha real de cálculo
// aparecem exatamente iguais na tela — os dois viravam "Erro 500".
const BACKEND_FORA =
  'Não foi possível falar com o backend. Confira se ele está rodando: ' +
  'no diretório backend/, rode .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload'

async function trata(resp) {
  if (!resp.ok) {
    let detalhe = `Erro ${resp.status}`
    let temJson = false
    try {
      const json = await resp.json()
      temJson = true
      if (typeof json.detail === 'string') detalhe = json.detail
      else if (Array.isArray(json.detail)) detalhe = json.detail.map((d) => d.msg).join(' · ')
    } catch {
      /* resposta sem corpo JSON */
    }
    if (!temJson && resp.status >= 500) detalhe = BACKEND_FORA
    throw new Error(detalhe)
  }
  return resp.json()
}

/** `fetch` só rejeita em falha de rede — ali não há status para interpretar. */
async function buscar(rota, opcoes) {
  try {
    return await fetch(`${BASE}${rota}`, opcoes)
  } catch {
    throw new Error(BACKEND_FORA)
  }
}

async function post(rota, corpo) {
  return trata(
    await buscar(rota, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corpo),
    })
  )
}

async function get(rota) {
  return trata(await buscar(rota))
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

/** Fundos ativos na CVM cujo nome contém `q`. */
export const buscarFundos = (q) => get(`/api/fundos/buscar?q=${encodeURIComponent(q)}`)

/** Top 10 fundos por retorno acumulado nos últimos `anos` anos. */
export const top10Fundos = (anos) => get(`/api/fundos/top10?anos=${anos}`)

/** Métricas, série mensal e comparativo de um fundo (CNPJ formatado). */
export const analiseFundo = (cnpj, meses) =>
  get(`/api/fundos/analise?cnpj=${encodeURIComponent(cnpj)}&meses=${meses}`)

/** Data/hora do último download bem-sucedido do mês mais recente. */
export const statusFundos = () => get('/api/fundos/status')

/** Força a próxima consulta a reprocessar o que pode ter mudado na CVM. */
export const atualizarFundos = () => post('/api/fundos/atualizar')
