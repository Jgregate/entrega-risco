const BASE = import.meta.env.VITE_API_URL || ''

async function post(rota, corpo) {
  const resp = await fetch(`${BASE}${rota}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo),
  })

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

/** Payload completo: os três VaRs, o book e a relação risco-retorno. */
export const analisar = (pedido) => post('/api/analise', pedido)

/** Somente o VaR empírico — contrato antigo, mantido para integrações. */
export const calcularVaREmpirico = (pedido) => post('/api/var/empirico', pedido)
