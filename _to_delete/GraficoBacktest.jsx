import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CORES, dataCurta, pct } from '../formato'

function Dica({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-data">{dataCurta(p.data)}</div>
      <div>
        retorno <strong>{pct(p.retorno)}</strong>
      </div>
      <div>limite do VaR {pct(p.var)}</div>
      {p.violacao && (
        <div style={{ color: CORES.vermelhoClaro, marginTop: 4 }}>violação do VaR</div>
      )}
    </div>
  )
}

export default function GraficoBacktest({ dados }) {
  const serie = dados.backtest.serie
  const janela = dados.parametros.janela_backtest
  const conf = (dados.parametros.confianca * 100).toFixed(
    dados.parametros.confianca === 0.975 ? 1 : 0
  )

  const comViolacao = serie.map((d) => ({ ...d, ponto: d.violacao ? d.retorno : null }))

  return (
    <div className="cartao">
      <h3>Backtest do VaR — histórico de violações</h3>
      <p className="legenda">
        VaR {conf}% recalculado a cada pregão com a janela móvel dos {janela} dias anteriores (sem
        look-ahead). Cada ponto marcado é um dia em que a perda realizada furou o limite.
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={comViolacao} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey="data"
            stroke="rgba(255,255,255,0.35)"
            tick={{ fontSize: 11 }}
            tickLine={false}
            minTickGap={60}
            tickFormatter={(v) => v.slice(0, 7)}
          />
          <YAxis
            stroke="rgba(255,255,255,0.35)"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
          />
          <Tooltip content={<Dica />} cursor={{ stroke: 'rgba(255,255,255,0.2)' }} />
          <Line
            type="monotone"
            dataKey="retorno"
            stroke="rgba(255,255,255,0.4)"
            strokeWidth={0.9}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="var"
            stroke={CORES.vermelhoClaro}
            strokeWidth={1.8}
            dot={false}
            isAnimationActive={false}
          />
          <Scatter dataKey="ponto" fill={CORES.branco} shape="circle" isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
