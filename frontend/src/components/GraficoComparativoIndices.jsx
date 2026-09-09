import { useMemo } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { COR_SERIE_FUNDO, pct } from '../formato'
import { rotuloMes } from '../fundos'
import CartaoGrafico from './CartaoGrafico'

function Dica({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="tooltip">
      <div className="t-data">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: <strong>{pct(p.value / 100, 1)}</strong>
        </div>
      ))}
    </div>
  )
}

/**
 * Rentabilidade acumulada do fundo vs. Ibovespa e CDI: quanto R$ 100
 * investidos em cada um teriam rendido.
 */
export default function GraficoComparativoIndices({ dados }) {
  const serie = useMemo(() => {
    let acc = { fundo: 0, cdi: 0, ibovespa: 0 }
    return dados.serie_mensal.map((p) => {
      acc = {
        fundo: (1 + acc.fundo / 100) * (1 + p['fundo_%'] / 100) * 100 - 100,
        cdi: (1 + acc.cdi / 100) * (1 + p['cdi_%'] / 100) * 100 - 100,
        ibovespa: (1 + acc.ibovespa / 100) * (1 + (p['ibov_%'] ?? 0) / 100) * 100 - 100,
      }
      return { mes: rotuloMes(p), ...acc }
    })
  }, [dados])

  return (
    <CartaoGrafico
      titulo="Fundo vs. Ibovespa vs. CDI"
      altura={240}
      subtitulo="Ibovespa: fechamento ajustado de fim de mês (Yahoo Finance)."
    >
      {(altura) => (
        <ResponsiveContainer width="100%" height={altura}>
          <LineChart data={serie} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="mes"
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 10 }}
              tickLine={false}
              minTickGap={36}
            />
            <YAxis
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={50}
              tickFormatter={(v) => `${v.toFixed(0)}%`}
            />
            <Tooltip content={<Dica />} cursor={{ stroke: 'rgba(255,255,255,0.2)' }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line
              type="monotone" dataKey="fundo" name="Fundo"
              stroke={COR_SERIE_FUNDO.fundo} strokeWidth={2.4} dot={false} isAnimationActive={false}
            />
            <Line
              type="monotone" dataKey="ibovespa" name="Ibovespa"
              stroke={COR_SERIE_FUNDO.ibovespa} strokeWidth={1.4} dot={false} isAnimationActive={false}
            />
            <Line
              type="monotone" dataKey="cdi" name="CDI"
              stroke={COR_SERIE_FUNDO.cdi} strokeWidth={1.4} dot={false} isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </CartaoGrafico>
  )
}
