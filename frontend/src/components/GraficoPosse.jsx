import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CORES, brl, dataCurta } from '../formato'
import CartaoGrafico from './CartaoGrafico'

function Dica({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-data">{dataCurta(p.data)}</div>
      <strong>{brl(p.valor)}</strong>
      <br />
      {p.posicoes} {p.posicoes === 1 ? 'posição' : 'posições'} em carteira
    </div>
  )
}

/**
 * O valor do book desde a primeira compra, somando cada posição a partir da
 * data em que ela entrou.
 *
 * A segunda série — quantas posições estavam vivas em cada data — existe para
 * impedir uma leitura errada: um degrau nesta curva pode ser valorização ou
 * pode ser posição nova entrando. Sem a contagem ao lado, as duas coisas são
 * visualmente idênticas, e a diferença entre elas é justamente o que a
 * rastreabilidade existe para mostrar.
 */
export default function GraficoPosse({ rastreabilidade }) {
  const serie = rastreabilidade.evolucao
  if (!serie?.length) return null

  const entradas = new Set(serie.map((p) => p.posicoes)).size > 1

  return (
    <CartaoGrafico
      titulo="Valor do book desde a compra"
      altura={210}
      subtitulo={
        entradas
          ? 'Cada posição entra na curva na data da própria compra. A linha clara conta quantas posições estavam em carteira — um degrau nela é entrada de posição, não valorização.'
          : 'Todas as posições foram compradas na mesma data, então a curva é só valorização.'
      }
    >
      {(altura) => (
        <ResponsiveContainer width="100%" height={altura}>
          {entradas ? (
            <ComposedChart data={serie} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
              <defs>
                <linearGradient id="grad-posse" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CORES.vermelho} stopOpacity={0.5} />
                  <stop offset="100%" stopColor={CORES.vermelho} stopOpacity={0.02} />
                </linearGradient>
              </defs>
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
                yAxisId="valor"
                stroke="rgba(255,255,255,0.35)"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={62}
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
              />
              <YAxis
                yAxisId="contagem"
                orientation="right"
                stroke="rgba(255,255,255,0.25)"
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={28}
                allowDecimals={false}
                domain={[0, 'dataMax + 1']}
              />
              <Tooltip content={<Dica />} cursor={{ stroke: 'rgba(255,255,255,0.2)' }} />
              <Area
                yAxisId="valor"
                type="monotone"
                dataKey="valor"
                stroke={CORES.vermelhoClaro}
                strokeWidth={1.6}
                fill="url(#grad-posse)"
                isAnimationActive={false}
              />
              <Line
                yAxisId="contagem"
                type="stepAfter"
                dataKey="posicoes"
                stroke="rgba(255,255,255,0.45)"
                strokeWidth={1.2}
                dot={false}
                isAnimationActive={false}
              />
            </ComposedChart>
          ) : (
            <AreaChart data={serie} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
              <defs>
                <linearGradient id="grad-posse-simples" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CORES.vermelho} stopOpacity={0.5} />
                  <stop offset="100%" stopColor={CORES.vermelho} stopOpacity={0.02} />
                </linearGradient>
              </defs>
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
                width={62}
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip content={<Dica />} cursor={{ stroke: 'rgba(255,255,255,0.2)' }} />
              <Area
                type="monotone"
                dataKey="valor"
                stroke={CORES.vermelhoClaro}
                strokeWidth={1.6}
                fill="url(#grad-posse-simples)"
                isAnimationActive={false}
              />
            </AreaChart>
          )}
        </ResponsiveContainer>
      )}
    </CartaoGrafico>
  )
}
