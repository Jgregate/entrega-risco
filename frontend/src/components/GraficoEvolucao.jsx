import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CORES, brl, dataCurta } from '../formato'
import { recortar } from '../janela'
import CartaoGrafico from './CartaoGrafico'

function Dica({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-data">{dataCurta(p.data)}</div>
      <strong>{brl(p.valor)}</strong>
    </div>
  )
}

export default function GraficoEvolucao({ dados, corte }) {
  // rebase: a janela começa valendo o valor da carteira, senão a curva
  // apareceria partindo de um número arbitrário do meio do histórico
  const serie = useMemo(() => {
    const recorte = recortar(dados.evolucao, corte)
    if (!recorte.length) return []
    const fator = dados.parametros.valor_carteira / recorte[0].valor
    return recorte.map((p) => ({ ...p, valor: p.valor * fator }))
  }, [dados, corte])

  return (
    <CartaoGrafico
      titulo="Evolução da carteira"
      altura={210}
      subtitulo={`Valor acumulado da carteira com os pesos informados, rebalanceada diariamente, partindo de ${brl(
        dados.parametros.valor_carteira
      )}.`}
    >
      {(altura) => (
      <ResponsiveContainer width="100%" height={altura}>
        <AreaChart data={serie} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id="grad-carteira" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CORES.vermelho} stopOpacity={0.55} />
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
            fill="url(#grad-carteira)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
      )}
    </CartaoGrafico>
  )
}
