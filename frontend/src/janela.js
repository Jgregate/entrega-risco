/**
 * Janela de visualização da aba de VaRs.
 *
 * A janela filtra o que se VÊ, não o que o modelo calculou: os VaRs continuam
 * vindo do backend com todo o histórico disponível (sem isso a janela móvel do
 * backtest não teria de onde sair). Aqui só recortamos o período exibido e
 * recalculamos estatística descritiva — contagem e histograma — sobre o recorte.
 * Nenhuma fórmula de VaR é reimplementada no front.
 */

export const JANELAS = [
  { anos: 1, texto: '1 ano' },
  { anos: 2, texto: '2 anos' },
  { anos: 3, texto: '3 anos' },
  { anos: 5, texto: '5 anos' },
  { anos: null, texto: 'Tudo' },
]

/** Data de corte: `anos` antes do último pregão da série. */
export function dataDeCorte(ultimaData, anos) {
  if (!anos || !ultimaData) return null
  const [a, m, d] = ultimaData.split('-').map(Number)
  const corte = new Date(Date.UTC(a - anos, m - 1, d))
  return corte.toISOString().slice(0, 10)
}

/** Recorta uma série de pontos `{ data: 'YYYY-MM-DD', ... }`. */
export function recortar(serie, corte) {
  if (!corte) return serie
  return serie.filter((p) => p.data >= corte)
}

/** Anos-calendário presentes no recorte, do mais antigo ao mais recente. */
export function anosDaSerie(serie) {
  return [...new Set(serie.map((p) => p.data.slice(0, 4)))].sort()
}

/**
 * Histograma de densidade + normal de mesma média e desvio.
 * Mesma saída do `histograma()` do backend, para os gráficos não precisarem
 * saber de onde os dados vieram.
 */
export function histograma(valores, nBins = 60) {
  if (!valores.length) return []

  const min = Math.min(...valores)
  const max = Math.max(...valores)
  const largura = (max - min) / nBins || 1
  const contagem = new Array(nBins).fill(0)

  for (const v of valores) {
    const i = Math.min(nBins - 1, Math.floor((v - min) / largura))
    contagem[i] += 1
  }

  const media = valores.reduce((s, v) => s + v, 0) / valores.length
  const variancia =
    valores.reduce((s, v) => s + (v - media) ** 2, 0) / Math.max(valores.length - 1, 1)
  const desvio = Math.sqrt(variancia)

  return contagem.map((c, i) => {
    const centro = min + largura * (i + 0.5)
    const densidade = c / (valores.length * largura)
    const normal =
      desvio > 0
        ? (1 / (desvio * Math.sqrt(2 * Math.PI))) *
          Math.exp(-0.5 * ((centro - media) / desvio) ** 2)
        : 0
    return {
      retorno: centro,
      densidade: Number(densidade.toFixed(4)),
      normal: Number(normal.toFixed(4)),
    }
  })
}

/** Contagem e taxa de violações de um recorte. */
export function resumoDoRecorte(serie) {
  const observacoes = serie.length
  const violacoes = serie.reduce((s, p) => s + (p.violacao ? 1 : 0), 0)
  return {
    observacoes,
    violacoes,
    taxa: observacoes ? violacoes / observacoes : null,
  }
}
