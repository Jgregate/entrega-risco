/**
 * Formatação pt-BR e tokens de cor dos gráficos.
 *
 * As paletas abaixo não são escolhidas a olho: cada uma passou pelas seis
 * checagens de acessibilidade (banda de luminosidade, piso de croma, separação
 * sob protanopia/deuteranopia, piso de visão normal e contraste com o fundo)
 * contra a superfície escura desta aplicação. A ordem dos slots faz parte da
 * validação — trocar a ordem invalida a checagem de pares adjacentes.
 */

export const pct = (v, casas = 2) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : `${(v * 100).toFixed(casas).replace('.', ',')}%`

/** Percentual com sinal explícito — para variação, excesso e contribuição. */
export const pctSinal = (v, casas = 2) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : `${v > 0 ? '+' : ''}${(v * 100).toFixed(casas).replace('.', ',')}%`

export const brl = (v, casas = 0) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : v.toLocaleString('pt-BR', {
        style: 'currency',
        currency: 'BRL',
        minimumFractionDigits: casas,
        maximumFractionDigits: casas,
      })

/** Valores grandes viram R$ 1,2 mi / R$ 3,4 bi — cabe no cartão e se lê de relance. */
export const brlCurto = (v) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const abs = Math.abs(v)
  if (abs >= 1e9) return `R$ ${(v / 1e9).toFixed(2).replace('.', ',')} bi`
  if (abs >= 1e6) return `R$ ${(v / 1e6).toFixed(2).replace('.', ',')} mi`
  if (abs >= 1e3) return `R$ ${(v / 1e3).toFixed(1).replace('.', ',')} mil`
  return brl(v, 2)
}

export const num = (v, casas = 2) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : Number(v).toFixed(casas).replace('.', ',')

export const inteiro = (v) =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : Number(v).toLocaleString('pt-BR')

export const dataCurta = (iso) => {
  if (!iso) return '—'
  const [a, m, d] = iso.split('-')
  return `${d}/${m}/${a}`
}

export const mesAno = (iso) => {
  if (!iso) return '—'
  const [a, m] = iso.split('-')
  return `${m}/${a}`
}

export const rotuloConfianca = (c) =>
  `${(c * 100).toFixed(Number.isInteger(c * 100) ? 0 : 1).replace('.', ',')}%`

export const MESES_ABREV = [
  'jan', 'fev', 'mar', 'abr', 'mai', 'jun',
  'jul', 'ago', 'set', 'out', 'nov', 'dez',
]

/* ------------------------------------------------------------------ *
 * Cores
 * ------------------------------------------------------------------ */

export const CORES = {
  vermelhoClaro: '#ff4545',
  vermelhoMedio: '#ad2727',
  vermelho: '#c00000',
  vermelhoEscuro: '#850000',
  vinho: '#580000',
  marrom: '#360100',
  branco: '#ffffff',
  quasePreto: '#130000',
  // cinzas neutros: eixos, grade e o meio da escala divergente
  grade: 'rgba(255,255,255,0.06)',
  eixo: 'rgba(255,255,255,0.35)',
  neutro: '#2a2224',
}

/**
 * Séries de tempo. O fundo/carteira é sempre o vermelho da marca; o benchmark
 * é a referência neutra em branco. Consistente em toda a aplicação: a cor
 * segue a entidade, nunca a posição na legenda.
 */
export const COR_SERIE = {
  fundo: CORES.vermelhoClaro,
  carteira: CORES.vermelhoClaro,
  benchmark: CORES.branco,
  cdi: '#ff9595',
  ibovespa: '#ad2727',
  ipca: '#ffbebe',
  selic: '#cc3838',
  sp500: '#872222',
  dolar: '#e64040',
}

/**
 * Paleta categórica (identidade: qual classe, qual gestora).
 * Validada em modo escuro sobre a superfície #0d0203 — pior par adjacente
 * ΔE 24,0 sob protanopia. Atribuída em ordem fixa, NUNCA ciclada: a partir do
 * 7º item a cauda vira "Outros" (ver `dobraCategorias`).
 */
export const PALETA_CATEGORICA = [
  '#ff4a4a', '#648eed', '#a14400', '#00a1db', '#8a5800', '#a17adf',
]

/**
 * Rampa ordinal de um tom só (o vermelho da marca), clara → escura.
 * Para escalas com ordem natural — faixas de liquidez, por exemplo.
 * Validada: luminosidade monotônica, degraus ≥ 0,06 e ponta escura a 2,2:1
 * do fundo.
 */
export const RAMPA_ORDINAL = [
  '#ffdcdc', '#ffb3b3', '#ff8a8a', '#ff5f5f',
  '#e64040', '#c53535', '#a62b2b', '#872222',
]

/**
 * Escala divergente: vermelho (negativo) → neutro cinza (zero) → branco
 * (positivo). O meio é acromático de propósito — perto de zero tem que ler
 * como "nada aconteceu" e se dissolver no fundo. Mantém o vermelho com o
 * mesmo significado que ele já tem no resto do sistema: perda.
 */
export const DIVERGENTE = {
  negativo: CORES.vermelhoClaro,
  neutro: CORES.neutro,
  positivo: CORES.branco,
}

/** Cor de um item categórico pela posição — sem ciclar. */
export const corCategoria = (i) =>
  PALETA_CATEGORICA[i] ?? PALETA_CATEGORICA[PALETA_CATEGORICA.length - 1]

/** Cor de um degrau ordinal, distribuído pela rampa inteira. */
export const corOrdinal = (i, total) => {
  if (total <= 1) return RAMPA_ORDINAL[0]
  const pos = Math.round((i / (total - 1)) * (RAMPA_ORDINAL.length - 1))
  return RAMPA_ORDINAL[pos]
}

function hexParaRgb(hex) {
  const v = hex.replace('#', '')
  return [
    parseInt(v.slice(0, 2), 16),
    parseInt(v.slice(2, 4), 16),
    parseInt(v.slice(4, 6), 16),
  ]
}

function interpolar(hexA, hexB, t) {
  const [r1, g1, b1] = hexParaRgb(hexA)
  const [r2, g2, b2] = hexParaRgb(hexB)
  const m = (a, b) => Math.round(a + (b - a) * t)
  return `rgb(${m(r1, r2)}, ${m(g1, g2)}, ${m(b1, b2)})`
}

/**
 * Cor divergente de um valor, com a escala fixa em `vmax` (maior |valor| da
 * série) para que as duas asas tenham o mesmo passo.
 */
export function corDivergente(v, vmax) {
  if (v === null || v === undefined || Number.isNaN(v)) return null
  const t = vmax > 0 ? Math.min(Math.abs(v) / vmax, 1) : 0
  const destino = v >= 0 ? DIVERGENTE.positivo : DIVERGENTE.negativo
  return interpolar(DIVERGENTE.neutro, destino, t)
}

/** Preto ou branco, o que for mais legível sobre `corFundo`. */
export function corTextoLegivel(corFundo) {
  const m = String(corFundo).match(/\d+/g)
  if (!m) return CORES.branco
  const [r, g, b] = m.map(Number)
  const luminancia = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return luminancia > 0.6 ? CORES.quasePreto : CORES.branco
}

/**
 * Dobra uma lista de categorias em no máximo `limite` fatias, somando a cauda
 * em "Outros". Nenhum gráfico desta aplicação inventa uma sétima cor.
 */
export function dobraCategorias(itens, limite = PALETA_CATEGORICA.length, chaveValor = 'valor') {
  if (itens.length <= limite) return itens
  const cabeca = itens.slice(0, limite - 1)
  const cauda = itens.slice(limite - 1)
  return [
    ...cabeca,
    {
      nome: 'Outros',
      [chaveValor]: cauda.reduce((s, i) => s + (i[chaveValor] ?? 0), 0),
      percentual: cauda.reduce((s, i) => s + (i.percentual ?? 0), 0),
      fundos: cauda.reduce((s, i) => s + (i.fundos ?? 0), 0),
      agrupado: cauda.length,
    },
  ]
}

// uma cor por método de VaR, usada de forma consistente em todos os gráficos
export const COR_METODO = {
  empirico: CORES.vermelhoClaro,
  parametrico: CORES.branco,
  ewma: CORES.vermelho,
}
