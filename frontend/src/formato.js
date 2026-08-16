export const pct = (v, casas = 2) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : `${(v * 100).toFixed(casas).replace('.', ',')}%`

export const brl = (v, casas = 0) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : v.toLocaleString('pt-BR', {
        style: 'currency',
        currency: 'BRL',
        minimumFractionDigits: casas,
        maximumFractionDigits: casas,
      })

export const num = (v, casas = 2) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : Number(v).toFixed(casas).replace('.', ',')

export const dataCurta = (iso) => {
  if (!iso) return '—'
  const [a, m, d] = iso.split('-')
  return `${d}/${m}/${a}`
}

export const rotuloConfianca = (c) =>
  `${(c * 100).toFixed(Number.isInteger(c * 100) ? 0 : 1).replace('.', ',')}%`

export const CORES = {
  vermelhoClaro: '#ff4545',
  vermelhoMedio: '#ad2727',
  vermelho: '#c00000',
  vermelhoEscuro: '#850000',
  vinho: '#580000',
  marrom: '#360100',
  branco: '#ffffff',
  quasePreto: '#130000',
}

// uma cor por método de VaR, usada de forma consistente em todos os gráficos
export const COR_METODO = {
  empirico: CORES.vermelhoClaro,
  parametrico: CORES.branco,
  ewma: CORES.vermelho,
}
