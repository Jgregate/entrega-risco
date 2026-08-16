export const pct = (v, casas = 2) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : `${(v * 100).toFixed(casas).replace('.', ',')}%`

export const brl = (v) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })

export const num = (v, casas = 2) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : Number(v).toFixed(casas).replace('.', ',')

export const dataCurta = (iso) => {
  if (!iso) return '—'
  const [a, m, d] = iso.split('-')
  return `${d}/${m}/${a}`
}

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
