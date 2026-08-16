import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CORES, dataCurta, num, pct } from '../formato'

function DicaAno({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-data">{label}</div>
      <div>
        <strong>{p.violacoes}</strong> violações em {p.pregoes} pregões
      </div>
      <div style={{ color: 'rgba(255,255,255,0.55)' }}>
        esperadas: {p.esperadas.toFixed(1)}
      </div>
    </div>
  )
}

export default function Violacoes({ dados }) {
  const { serie, resumo } = dados.backtest
  const alpha = 1 - dados.parametros.confianca

  const porAno = useMemo(() => {
    const mapa = new Map()
    for (const d of serie) {
      const ano = d.data.slice(0, 4)
      const atual = mapa.get(ano) || { ano, violacoes: 0, pregoes: 0 }
      atual.pregoes += 1
      if (d.violacao) atual.violacoes += 1
      mapa.set(ano, atual)
    }
    return [...mapa.values()].map((a) => ({ ...a, esperadas: a.pregoes * alpha }))
  }, [serie, alpha])

  const piores = useMemo(
    () =>
      serie
        .filter((d) => d.violacao)
        .map((d) => ({ ...d, excesso: -(d.retorno - d.var) }))
        .sort((a, b) => b.excesso - a.excesso)
        .slice(0, 10),
    [serie]
  )

  const kupiec = resumo.kupiec
  const reprovado = kupiec?.rejeita_5pct

  return (
    <>
      <div className="cartao">
        <h3>Violações por ano</h3>
        <p className="legenda">
          Barras claras acima do esperado indicam concentração de excessos — normalmente estresse
          de mercado que a janela histórica ainda não tinha absorvido.
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={porAno} margin={{ top: 8, right: 12, bottom: 0, left: -24 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="ano"
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 11 }}
              tickLine={false}
            />
            <YAxis
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
            />
            <Tooltip content={<DicaAno />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
            <Bar
              dataKey="violacoes"
              radius={[4, 4, 0, 0]}
              maxBarSize={64}
              isAnimationActive={false}
            >
              {porAno.map((a, i) => (
                <Cell
                  key={i}
                  fill={a.violacoes > a.esperadas ? CORES.vermelhoClaro : CORES.vermelhoEscuro}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="cartao">
        <h3>
          Aderência do modelo{' '}
          <span className={`selo-teste ${reprovado ? 'falha' : 'ok'}`}>
            Kupiec {reprovado ? 'rejeita H₀' : 'não rejeita H₀'}
          </span>
        </h3>
        <p className="legenda">
          Teste de cobertura incondicional (POF). H₀: a taxa de violações é igual a{' '}
          {pct(alpha, 1)}. Estatística LR = {num(kupiec?.estatistica_lr)} · p-valor ={' '}
          {num(kupiec?.p_valor, 3)}. Taxa observada {pct(resumo.taxa_observada, 2)} em{' '}
          {resumo.observacoes} pregões · maior sequência de violações consecutivas:{' '}
          {resumo.maior_sequencia}.
        </p>
        <span className="rotulo">10 maiores excessos</span>
        <table>
          <thead>
            <tr>
              <th>Data</th>
              <th style={{ textAlign: 'right' }}>Retorno</th>
              <th style={{ textAlign: 'right' }}>Limite VaR</th>
              <th style={{ textAlign: 'right' }}>Excesso</th>
            </tr>
          </thead>
          <tbody>
            {piores.length === 0 && (
              <tr>
                <td colSpan={4}>Nenhuma violação no período.</td>
              </tr>
            )}
            {piores.map((d) => (
              <tr key={d.data}>
                <td>{dataCurta(d.data)}</td>
                <td className="num perda">{pct(d.retorno)}</td>
                <td className="num">{pct(d.var)}</td>
                <td className="num">{pct(-d.excesso)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
