import { useMemo } from 'react'
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
import { COR_METODO, CORES, dataCurta, pct, rotuloConfianca } from '../formato'
import { histograma, recortar } from '../janela'
import CartaoGrafico from './CartaoGrafico'

function DicaDist({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-data">retorno {pct(p.retorno)}</div>
      <div>
        densidade empírica <strong>{p.densidade.toFixed(1)}</strong>
      </div>
      <div style={{ color: 'rgba(255,255,255,0.55)' }}>normal equivalente {p.normal.toFixed(1)}</div>
    </div>
  )
}

function PainelDistribuicao({ metodo, cor, distribuicao, conf, dominioY, corte, dataFim }) {
  // limite vigente no último pregão da janela — valor calculado no backend,
  // aqui só selecionado
  const ultimo = useMemo(() => {
    const recorte = recortar(metodo.backtest.serie, corte)
    return recorte.length ? recorte[recorte.length - 1] : null
  }, [metodo, corte])

  const corteVaR = ultimo ? ultimo.var : -metodo.var_percentual

  const corteNoEixo = distribuicao.reduce(
    (melhor, d) =>
      Math.abs(d.retorno - corteVaR) < Math.abs(melhor - corteVaR) ? d.retorno : melhor,
    distribuicao[0]?.retorno ?? 0
  )

  return (
    <CartaoGrafico
      titulo={metodo.rotulo}
      cor={cor}
      altura={240}
      subtitulo={`limite vigente em ${dataCurta(ultimo?.data ?? dataFim)}: ${pct(
        -corteVaR
      )} · ${metodo.descricao}`}
    >
      {(altura) => (
        <ResponsiveContainer width="100%" height={altura}>
          <ComposedChart data={distribuicao} margin={{ top: 16, right: 8, bottom: 0, left: -14 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="retorno"
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 10 }}
              tickLine={false}
              minTickGap={26}
            />
            <YAxis
              domain={dominioY}
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<DicaDist />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
            <Bar dataKey="densidade" isAnimationActive={false}>
              {distribuicao.map((d, i) => (
                <Cell
                  key={i}
                  fill={d.retorno <= corteVaR ? cor : CORES.vinho}
                  fillOpacity={d.retorno <= corteVaR ? 0.95 : 0.85}
                />
              ))}
            </Bar>
            <Line
              type="monotone"
              dataKey="normal"
              stroke="rgba(255,255,255,0.45)"
              strokeWidth={1.4}
              dot={false}
              isAnimationActive={false}
            />
            <ReferenceLine
              x={corteNoEixo}
              stroke={CORES.branco}
              strokeDasharray="4 4"
              label={{
                value: `VaR ${conf}`,
                position: 'insideTopLeft',
                fill: CORES.branco,
                fontSize: 10.5,
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </CartaoGrafico>
  )
}

export default function GraficoDistribuicao({ dados, corte }) {
  const { metodos, ordem_metodos, parametros } = dados
  const conf = rotuloConfianca(parametros.confianca)

  // o histograma é recontado sobre o recorte: estatística descritiva pura,
  // nenhuma fórmula de VaR reimplementada aqui
  const { distribuicao, observacoes } = useMemo(() => {
    const recorte = recortar(metodos[ordem_metodos[0]].backtest.serie, corte)
    return {
      distribuicao: histograma(recorte.map((d) => d.retorno)),
      observacoes: recorte.length,
    }
  }, [metodos, ordem_metodos, corte])

  // arredonda para cima em múltiplos de 5: evita tick quebrado tipo 60.000001
  const maxDensidade = Math.max(...distribuicao.map((d) => Math.max(d.densidade, d.normal)), 1)
  const dominioY = [0, Math.ceil((maxDensidade * 1.06) / 5) * 5]

  return (
    <section>
      <div className="titulo-secao">
        <h3>Distribuição dos retornos e o corte de cada método</h3>
        <p className="legenda">
          O histograma é o mesmo nos três painéis — {observacoes} retornos observados da carteira
          na janela. O que muda é onde cada método traça a linha: a cauda pintada é a fatia de{' '}
          {pct(1 - parametros.confianca, 1)} que aquele modelo considera além do VaR. A linha clara
          é a normal de mesma média e desvio: o paramétrico enxerga só ela, o empírico enxerga as
          barras.
        </p>
      </div>
      <div className="trio">
        {ordem_metodos.map((nome) => (
          <PainelDistribuicao
            key={nome}
            metodo={metodos[nome]}
            cor={COR_METODO[nome]}
            distribuicao={distribuicao}
            conf={conf}
            dominioY={dominioY}
            corte={corte}
            dataFim={parametros.fim}
          />
        ))}
      </div>
    </section>
  )
}
