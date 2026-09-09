import { useMemo } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { COR_SERIE_FUNDO, num } from '../formato'
import { rotuloMes } from '../fundos'
import CartaoGrafico from './CartaoGrafico'

function Dica({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="tooltip">
      <div className="t-data">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: <strong>{num(p.value, 1)}</strong>
        </div>
      ))}
    </div>
  )
}

/** Quanto R$ 100 investidos no fundo e no CDI no início do período valeriam em cada mês. */
export default function GraficoCrescimentoFundo({ dados }) {
  const serie = useMemo(() => {
    let idxFundo = 100
    let idxCdi = 100
    return dados.serie_mensal.map((p) => {
      idxFundo *= 1 + p['fundo_%'] / 100
      idxCdi *= 1 + p['cdi_%'] / 100
      return {
        mes: rotuloMes(p),
        fundo: Number(idxFundo.toFixed(2)),
        cdi: Number(idxCdi.toFixed(2)),
      }
    })
  }, [dados])

  return (
    <CartaoGrafico
      titulo="Crescimento acumulado"
      altura={230}
      subtitulo="R$ 100 investidos no início do período, fundo vs. CDI."
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
              width={44}
            />
            <Tooltip content={<Dica />} cursor={{ stroke: 'rgba(255,255,255,0.2)' }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line
              type="monotone"
              dataKey="fundo"
              name="Fundo"
              stroke={COR_SERIE_FUNDO.fundo}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="cdi"
              name="CDI"
              stroke={COR_SERIE_FUNDO.cdi}
              strokeWidth={1.4}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </CartaoGrafico>
  )
}
