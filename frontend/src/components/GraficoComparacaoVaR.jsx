import { useMemo } from 'react'
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import { COR_METODO, CORES, dataCurta, num, pct, rotuloConfianca } from '../formato'

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

function PainelMetodo({ metodo, cor, dominio }) {
  const serie = useMemo(
    () =>
      metodo.backtest.serie.map((d) => ({
        ...d,
        ponto: d.violacao ? d.retorno : null,
      })),
    [metodo]
  )
  const resumo = metodo.backtest.resumo

  return (
    <div className="cartao">
      <h4 style={{ color: cor }}>{metodo.rotulo}</h4>
      <p className="legenda-mini">
        {resumo.violacoes} violações · esperadas {num(resumo.violacoes_esperadas, 1)} ·{' '}
        {metodo.descricao}
      </p>
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={serie} margin={{ top: 6, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey="data"
            stroke="rgba(255,255,255,0.35)"
            tick={{ fontSize: 10 }}
            tickLine={false}
            minTickGap={42}
            tickFormatter={(v) => v.slice(2, 7)}
          />
          <YAxis
            domain={dominio}
            stroke="rgba(255,255,255,0.35)"
            tick={{ fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
          />
          <Tooltip content={<Dica />} cursor={{ stroke: 'rgba(255,255,255,0.2)' }} />
          <Line
            type="monotone"
            dataKey="retorno"
            stroke="rgba(255,255,255,0.28)"
            strokeWidth={0.8}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="var"
            stroke={cor}
            strokeWidth={1.8}
            dot={false}
            isAnimationActive={false}
          />
          {/* ZAxis fixa o raio do ponto: sem isso o padrão do Recharts engole o gráfico */}
          <ZAxis range={[9, 9]} />
          <Scatter dataKey="ponto" fill={CORES.branco} shape="circle" isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

/**
 * Um painel por método, mesma escala vertical nos três.
 * Escala compartilhada é o que permite comparar de relance: o EWMA respira com
 * a volatilidade, o paramétrico acompanha de longe e o empírico anda em degraus
 * — cada degrau é uma perda grande entrando ou saindo da janela.
 */
export default function GraficoComparacaoVaR({ dados }) {
  const { metodos, ordem_metodos, parametros } = dados

  // domínio único: sem isso cada gráfico se auto-escala e a comparação mente
  const dominio = useMemo(() => {
    let min = Infinity
    let max = -Infinity
    for (const nome of ordem_metodos) {
      for (const d of metodos[nome].backtest.serie) {
        min = Math.min(min, d.retorno, d.var)
        max = Math.max(max, d.retorno)
      }
    }
    const folga = (max - min) * 0.04
    return [min - folga, max + folga]
  }, [metodos, ordem_metodos])

  return (
    <section>
      <div className="titulo-secao">
        <h3>Os VaRs no tempo</h3>
        <p className="legenda">
          Limite de {rotuloConfianca(parametros.confianca)} recalculado a cada pregão com a janela
          móvel dos {parametros.janela_backtest} dias anteriores, sem look-ahead. A linha cinza é o
          retorno realizado e cada ponto branco é um dia em que ele furou o limite. Os três painéis
          dividem a mesma escala vertical.
        </p>
      </div>
      <div className="trio">
        {ordem_metodos.map((nome) => (
          <PainelMetodo
            key={nome}
            metodo={metodos[nome]}
            cor={COR_METODO[nome]}
            dominio={dominio}
          />
        ))}
      </div>
    </section>
  )
}
