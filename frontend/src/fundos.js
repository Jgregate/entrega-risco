/** Utilidades específicas da aba Fundos: rótulo de mês e escala de cor do heatmap. */

const MESES_ABREV = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

export function rotuloMes({ ano, mes }) {
  return `${MESES_ABREV[mes - 1]}/${String(ano).slice(2)}`
}

function hexParaRgb(hex) {
  const v = hex.replace('#', '')
  return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)]
}

function interpolar(hexA, hexB, t) {
  const [r1, g1, b1] = hexParaRgb(hexA)
  const [r2, g2, b2] = hexParaRgb(hexB)
  const r = Math.round(r1 + (r2 - r1) * t)
  const g = Math.round(g1 + (g2 - g1) * t)
  const b = Math.round(b1 + (b2 - b1) * t)
  return `rgb(${r}, ${g}, ${b})`
}

/**
 * Vermelho (perda) -> marrom escuro (perto de zero) -> branco (ganho),
 * escala fixa em `vmax` (maior |retorno| do período) - mesma ideia divergente
 * do heatmap original, na paleta do entrega-risco em vez de azul/verde.
 */
export function corCelulaHeatmap(v, vmax) {
  if (v === null || v === undefined || Number.isNaN(v)) return null
  const t = vmax > 0 ? Math.min(Math.abs(v) / vmax, 1) : 0
  return v >= 0 ? interpolar('#360100', '#ffffff', t) : interpolar('#360100', '#ff4545', t)
}

/** Preto ou branco, o que for mais legível sobre `corFundo` (luminância percebida). */
export function corTextoLegivel(corFundo) {
  const m = corFundo.match(/\d+/g)
  if (!m) return '#fff'
  const [r, g, b] = m.map(Number)
  const luminancia = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return luminancia > 0.6 ? '#130000' : '#ffffff'
}
