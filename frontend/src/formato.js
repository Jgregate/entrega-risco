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

// mesma ideia, para as séries da aba Fundos (fundo em destaque, CDI como
// referência neutra, índices de comparação em tons intermediários)
export const COR_SERIE_FUNDO = {
  fundo: CORES.vermelhoClaro,
  cdi: CORES.branco,
  ibovespa: CORES.vermelhoMedio,
}

// séries da aba Rastreabilidade: o realizado em branco (é fato), o projetado
// em vermelho (é estimativa) — a distinção visual entre os dois é a leitura
// mais importante do gráfico
export const COR_SERIE_RASTREIO = {
  realizado: CORES.branco,
  esperado: CORES.vermelhoClaro,
  banda: CORES.vermelho,
}

/** "há 412 dias" — o tempo de posse escrito como se lê em voz alta. */
export const haQuantoTempo = (dias) => {
  if (dias === null || dias === undefined) return '—'
  if (dias === 0) return 'hoje'
  if (dias === 1) return 'há 1 dia'
  if (dias < 60) return `há ${dias} dias`
  const meses = Math.round(dias / 30.44)
  if (dias < 730) return `há ${dias} dias · ~${meses} ${meses === 1 ? 'mês' : 'meses'}`
  const anos = (dias / 365.25).toFixed(1).replace('.', ',')
  return `há ${dias} dias · ~${anos} anos`
}

// nível de confiabilidade da projeção -> como o selo aparece
export const SELO_CONFIABILIDADE = {
  SAUDAVEL: 'ok',
  REDUZIDA: 'ok',
  BAIXA: 'falha',
  CRITICA: 'falha',
}
