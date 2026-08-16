const BASE = import.meta.env.VITE_API_URL || ''

export async function calcularVaREmpirico(pedido) {
  const resp = await fetch(`${BASE}/api/var/empirico`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(pedido),
  })

  if (!resp.ok) {
    let detalhe = `Erro ${resp.status}`
    try {
      const corpo = await resp.json()
      if (typeof corpo.detail === 'string') detalhe = corpo.detail
      else if (Array.isArray(corpo.detail)) {
        detalhe = corpo.detail.map((d) => d.msg).join(' · ')
      }
    } catch {
      /* resposta sem corpo JSON */
    }
    throw new Error(detalhe)
  }
  return resp.json()
}
