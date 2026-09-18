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

async function get(rota) {
  return trata(await fetch(`${BASE}${rota}`))
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
