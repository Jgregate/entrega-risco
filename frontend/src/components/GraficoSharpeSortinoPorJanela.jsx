import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CORES, num } from '../formato'
import CartaoGrafico from './CartaoGrafico'

function rotuloJanela(meses) {
  return meses < 12 ? `${meses}m` : `${meses / 12}a`
}

function Dica({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="tooltip">
      <div className="t-data">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: <strong>{num(p.value)}</strong>
        </div>
      ))}
    </div>
  )
}

export default function GraficoSharpeSortinoPorJanela({ dados }) {
  const serie = dados.janelas.map((j) => ({
    janela: rotuloJanela(j.janela_meses),
    sharpe: j.sharpe,
    sortino: j.sortino,
  }))

  return (
    <CartaoGrafico
      titulo="Sharpe e Sortino por janela"
      altura={220}
      subtitulo="Excesso de retorno sobre o CDI por unidade de risco (mensal, anualizado)."
    >
      {(altura) => (
        <ResponsiveContainer width="100%" height={altura}>
          <BarChart data={serie} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis dataKey="janela" stroke="rgba(255,255,255,0.35)" tick={{ fontSize: 11 }} tickLine={false} />
            <YAxis stroke="rgba(255,255,255,0.35)" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} width={40} />
            <Tooltip content={<Dica />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="sharpe" name="Sharpe" fill={CORES.vermelhoClaro} radius={[3, 3, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="sortino" name="Sortino" fill={CORES.branco} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </CartaoGrafico>
  )
}
