const BASE = import.meta.env.VITE_API_URL || ''

async function checaResposta(resp) {
  if (resp.ok) return resp.json()
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

async function post(rota, corpo) {
  const resp = await fetch(`${BASE}${rota}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo),
  })
  return checaResposta(resp)
}

async function get(rota) {
  return checaResposta(await fetch(`${BASE}${rota}`))
}

/** Payload completo: os três VaRs, o book e a relação risco-retorno. */
export const analisar = (pedido) => post('/api/analise', pedido)

/** Somente o VaR empírico — contrato antigo, mantido para integrações. */
export const calcularVaREmpirico = (pedido) => post('/api/var/empirico', pedido)

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
