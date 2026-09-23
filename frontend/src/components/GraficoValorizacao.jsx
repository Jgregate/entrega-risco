import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CORES, brl, dataCurta, haQuantoTempo, pct } from '../formato'
import CartaoGrafico from './CartaoGrafico'

function Dica({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-data">{p.rotulo}</div>
      <strong>{pct(p.valorizacao)}</strong> desde {dataCurta(p.data_compra)}
      <br />
      {brl(p.reais)} · {haQuantoTempo(p.dias)}
      {p.anualizado != null && (
        <>
          <br />
          {pct(p.anualizado, 1)} ao ano
        </>
      )}
    </div>
  )
}

/**
 * Quanto cada posição valorizou desde a própria compra.
 *
 * Barras em torno do zero, e não uma pilha: a pergunta aqui é quem ganhou e
 * quem perdeu, não como o total se reparte. Quem está no vermelho aparece na
 * cor de perda — a mesma leitura que as tabelas usam.
 *
 * O percentual, e não os reais, é o que ordena: uma posição pequena que
 * dobrou diz mais sobre a decisão de compra do que uma grande que subiu 2%.
 */
export default function GraficoValorizacao({ rastreabilidade }) {
  const serie = useMemo(
    () =>
      rastreabilidade.posicoes
        .map((p) => ({
          rotulo: p.rotulo,
          valorizacao: p.valorizacao_percentual,
          reais: p.valorizacao_reais,
          dias: p.dias_corridos,
          data_compra: p.data_compra,
          anualizado: p.retorno_anualizado,
        }))
        .sort((a, b) => (b.valorizacao ?? 0) - (a.valorizacao ?? 0)),
    [rastreabilidade]
  )

  if (!serie.length) return null

  return (
    <CartaoGrafico
      titulo="Valorização por posição"
      altura={Math.max(180, serie.length * 34 + 60)}
      subtitulo="Cada barra mede o preço de hoje contra o preço pago na compra daquela posição — os períodos de posse são diferentes entre elas, então a comparação é de decisão, não de janela."
    >
      {(altura) => (
        <ResponsiveContainer width="100%" height={altura}>
          <BarChart
            data={serie}
            layout="vertical"
            margin={{ top: 8, right: 18, bottom: 0, left: 4 }}
          >
            <CartesianGrid stroke="rgba(255,255,255,0.06)" horizontal={false} />
            <XAxis
              type="number"
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              tickFormatter={(v) => pct(v, 0)}
            />
            <YAxis
              type="category"
              dataKey="rotulo"
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={118}
            />
            <Tooltip content={<Dica />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
            <ReferenceLine x={0} stroke="rgba(255,255,255,0.3)" />
            <Bar dataKey="valorizacao" isAnimationActive={false} radius={[0, 3, 3, 0]}>
              {serie.map((p) => (
                <Cell
                  key={p.rotulo}
                  fill={p.valorizacao < 0 ? CORES.vermelho : CORES.branco}
                  fillOpacity={p.valorizacao < 0 ? 0.85 : 0.7}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </CartaoGrafico>
  )
}
