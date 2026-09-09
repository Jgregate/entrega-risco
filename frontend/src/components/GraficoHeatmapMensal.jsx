import { useMemo } from 'react'
import { num } from '../formato'
import { corCelulaHeatmap, corTextoLegivel } from '../fundos'
import CartaoGrafico from './CartaoGrafico'

const MESES_ABREV = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

/** Grade ano x mês dos retornos mensais do fundo — sem lib de gráfico, é CSS grid puro. */
export default function GraficoHeatmapMensal({ dados }) {
  const { anos, grade, vmax } = useMemo(() => {
    const porAno = new Map()
    let max = 0
    for (const p of dados.serie_mensal) {
      if (!porAno.has(p.ano)) porAno.set(p.ano, new Array(12).fill(null))
      porAno.get(p.ano)[p.mes - 1] = p['fundo_%']
      max = Math.max(max, Math.abs(p['fundo_%']))
    }
    return { anos: [...porAno.keys()].sort(), grade: porAno, vmax: max || 1 }
  }, [dados])

  return (
    <CartaoGrafico
      titulo="Retornos mensais por ano"
      altura={30 * anos.length + 34}
      subtitulo="Retorno do fundo mês a mês (%)."
    >
      {() => (
        <div className="heatmap-fundo">
          <div className="linha">
            <span />
            {MESES_ABREV.map((m) => (
              <span key={m} className="cabecalho">
                {m}
              </span>
            ))}
          </div>
          {anos.map((ano) => (
            <div className="linha" key={ano}>
              <span className="rotulo-ano">{ano}</span>
              {grade.get(ano).map((v, i) => {
                const cor = corCelulaHeatmap(v, vmax)
                return (
                  <span
                    key={i}
                    className={`celula${v === null ? ' vazia' : ''}`}
                    style={cor ? { background: cor, color: corTextoLegivel(cor) } : undefined}
                  >
                    {v === null ? '' : num(v, 1)}
                  </span>
                )
              })}
            </div>
          ))}
        </div>
      )}
    </CartaoGrafico>
  )
}
