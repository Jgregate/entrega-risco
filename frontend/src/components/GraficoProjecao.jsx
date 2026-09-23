import { useMemo } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { COR_SERIE_RASTREIO, CORES, brl, dataCurta } from '../formato'
import CartaoGrafico from './CartaoGrafico'

function Dica({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-data">{dataCurta(p.data)}</div>
      {p.realizado != null && (
        <>
          <strong>{brl(p.realizado)}</strong> realizado
        </>
      )}
      {p.esperado != null && (
        <>
          {p.realizado != null && <br />}
          <strong>{brl(p.esperado)}</strong> projetado
          <br />
          entre {brl(p.piso)} e {brl(p.teto)}
        </>
      )}
    </div>
  )
}

/**
 * O cone: o que a carteira fez, e a faixa em que ela deve estar no horizonte.
 *
 * Duas séries de naturezas diferentes no mesmo eixo, e a distinção visual
 * carrega o significado: o realizado é linha branca contínua (é fato), o
 * projetado é linha vermelha tracejada dentro de uma banda (é estimativa). A
 * linha vertical marca o corte entre os dois — sem ela, o olho lê a projeção
 * como se fosse histórico.
 *
 * A banda alarga com a raiz do tempo. Não é um alvo com margem de erro: é a
 * distribuição dos retornos passados aberta para a frente.
 */
export default function GraficoProjecao({ rastreabilidade, dias = 180 }) {
  const { projecao, evolucao } = rastreabilidade

  const serie = useMemo(() => {
    if (!projecao?.disponivel) return []
    // só a cauda recente do realizado: o cone tem 21 pregões, e ancorar num
    // histórico de 5 anos o espremeria até virar um traço no canto direito
    const recente = evolucao.slice(-dias).map((p) => ({
      data: p.data,
      realizado: p.valor,
      faixa: null,
    }))
    const emenda = recente.length ? recente[recente.length - 1] : null
    if (emenda) {
      // o primeiro ponto projetado nasce colado no último realizado, senão a
      // banda apareceria descolada da curva
      emenda.esperado = emenda.realizado
      emenda.piso = emenda.realizado
      emenda.teto = emenda.realizado
      emenda.faixa = [emenda.realizado, emenda.realizado]
    }
    const futuro = projecao.trajetoria.map((p) => ({
      data: p.data,
      realizado: null,
      esperado: p.esperado,
      piso: p.piso,
      teto: p.teto,
      faixa: [p.piso, p.teto],
    }))
    return [...recente, ...futuro]
  }, [projecao, evolucao, dias])

  if (!projecao?.disponivel || !serie.length) return null

  const corte = evolucao.length ? evolucao[evolucao.length - 1].data : null

  return (
    <CartaoGrafico
      titulo="Projeção da carteira"
      altura={250}
      subtitulo={`Realizado até ${dataCurta(projecao.data_partida)} e projeção de ${
        projecao.horizonte_pregoes
      } pregões até ${dataCurta(projecao.data_alvo)}. A banda é o VaR ${
        projecao.metodos[projecao.metodo_do_cone].rotulo
      } a ${(rastreabilidade.confianca * 100).toFixed(0)}% aberto pela raiz do tempo.`}
    >
      {(altura) => (
        <ResponsiveContainer width="100%" height={altura}>
          <ComposedChart data={serie} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="grad-projecao" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CORES.vermelho} stopOpacity={0.3} />
                <stop offset="100%" stopColor={CORES.vermelho} stopOpacity={0.08} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="data"
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              minTickGap={60}
              tickFormatter={(v) => (v ? v.slice(0, 7) : '')}
            />
            <YAxis
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={62}
              domain={['auto', 'auto']}
              tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip content={<Dica />} cursor={{ stroke: 'rgba(255,255,255,0.2)' }} />
            <Area
              dataKey="faixa"
              stroke="none"
              fill="url(#grad-projecao)"
              isAnimationActive={false}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="realizado"
              stroke={COR_SERIE_RASTREIO.realizado}
              strokeWidth={1.6}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="esperado"
              stroke={COR_SERIE_RASTREIO.esperado}
              strokeWidth={1.6}
              strokeDasharray="5 3"
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
            {corte && (
              <ReferenceLine
                x={corte}
                stroke="rgba(255,255,255,0.28)"
                strokeDasharray="3 3"
                label={{
                  value: 'hoje',
                  position: 'insideTopRight',
                  fill: 'rgba(255,255,255,0.5)',
                  fontSize: 10,
                }}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </CartaoGrafico>
  )
}
