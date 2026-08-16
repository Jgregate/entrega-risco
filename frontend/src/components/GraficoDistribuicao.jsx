import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CORES, pct } from '../formato'

function DicaDist({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-data">retorno {pct(p.retorno)}</div>
      <div>
        densidade empírica <strong>{p.densidade.toFixed(1)}</strong>
      </div>
      <div style={{ color: 'rgba(255,255,255,0.55)' }}>
        normal equivalente {p.normal.toFixed(1)}
      </div>
    </div>
  )
}

export default function GraficoDistribuicao({ dados }) {
  const { distribuicao, resultado, parametros, estatisticas } = dados
  const corte = -resultado.var_percentual
  const conf = (parametros.confianca * 100).toFixed(parametros.confianca === 0.975 ? 1 : 0)

  return (
    <div className="cartao">
      <h3>Distribuição dos retornos</h3>
      <p className="legenda">
        Histograma dos {estatisticas.observacoes} retornos observados da carteira. A cauda
        destacada é a fatia de {pct(1 - parametros.confianca, 1)} que fica além do VaR. A linha
        clara é a normal de mesma média e desvio — só referência: o VaR empírico não a assume.
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={distribuicao} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey="retorno"
            tickFormatter={(v) => `${(v * 100).toFixed(1).replace('.', ',')}%`}
            stroke="rgba(255,255,255,0.35)"
            tick={{ fontSize: 11 }}
            tickLine={false}
            minTickGap={34}
          />
          <YAxis
            stroke="rgba(255,255,255,0.35)"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<DicaDist />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
          <Bar dataKey="densidade" isAnimationActive={false}>
            {distribuicao.map((d, i) => (
              <Cell
                key={i}
                fill={d.retorno <= corte ? CORES.vermelhoClaro : CORES.vinho}
                fillOpacity={d.retorno <= corte ? 0.95 : 0.85}
              />
            ))}
          </Bar>
          <Line
            type="monotone"
            dataKey="normal"
            stroke="rgba(255,255,255,0.5)"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
          <ReferenceLine
            x={distribuicao.reduce(
              (melhor, d) =>
                Math.abs(d.retorno - corte) < Math.abs(melhor - corte) ? d.retorno : melhor,
              distribuicao[0]?.retorno ?? 0
            )}
            stroke={CORES.branco}
            strokeDasharray="4 4"
            label={{
              value: `VaR ${conf}%`,
              position: 'insideTopLeft',
              fill: CORES.branco,
              fontSize: 11,
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
