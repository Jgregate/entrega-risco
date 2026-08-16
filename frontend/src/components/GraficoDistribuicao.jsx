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
import { COR_METODO, CORES, brl, pct, rotuloConfianca } from '../formato'

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

function PainelDistribuicao({ metodo, cor, distribuicao, conf, dominioY }) {
  const corte = -metodo.var_percentual

  // encaixa o corte no centro de bin mais próximo, para a linha cair no eixo
  const corteNoEixo = distribuicao.reduce(
    (melhor, d) => (Math.abs(d.retorno - corte) < Math.abs(melhor - corte) ? d.retorno : melhor),
    distribuicao[0]?.retorno ?? 0
  )

  return (
    <div className="cartao">
      <h4 style={{ color: cor }}>{metodo.rotulo}</h4>
      <p className="legenda-mini">
        corte em {pct(metodo.var_percentual)} · {brl(metodo.var_monetario)} · ES{' '}
        {pct(metodo.es_percentual)}
      </p>
      <ResponsiveContainer width="100%" height={240}>
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
                fill={d.retorno <= corte ? cor : CORES.vinho}
                fillOpacity={d.retorno <= corte ? 0.95 : 0.85}
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
    </div>
  )
}

export default function GraficoDistribuicao({ dados }) {
  const { distribuicao, metodos, ordem_metodos, parametros, estatisticas } = dados
  const conf = rotuloConfianca(parametros.confianca)
  // arredonda para cima em múltiplos de 5: evita tick quebrado tipo 60.000001
  const maxDensidade = Math.max(...distribuicao.map((d) => Math.max(d.densidade, d.normal)))
  const dominioY = [0, Math.ceil((maxDensidade * 1.06) / 5) * 5]

  return (
    <section>
      <div className="titulo-secao">
        <h3>Distribuição dos retornos e o corte de cada método</h3>
        <p className="legenda">
          O histograma é o mesmo nos três painéis — {estatisticas.observacoes} retornos observados
          da carteira. O que muda é onde cada método traça a linha: a cauda pintada é a fatia de{' '}
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
          />
        ))}
      </div>
    </section>
  )
}
