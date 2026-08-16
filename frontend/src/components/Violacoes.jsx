import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { COR_METODO, dataCurta, num, pct } from '../formato'

function DicaAno({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-data">{label}</div>
      <div>
        <strong>{p.violacoes}</strong> violações em {p.pregoes} pregões
      </div>
      <div style={{ color: 'rgba(255,255,255,0.55)' }}>esperadas: {p.esperadas.toFixed(1)}</div>
    </div>
  )
}

function PainelAno({ metodo, cor, serie, dominioY, mediaEsperada }) {
  const acimaDoEsperado = serie.filter((a) => a.violacoes > a.esperadas).length

  return (
    <div className="cartao">
      <h4 style={{ color: cor }}>{metodo.rotulo}</h4>
      <p className="legenda-mini">
        {acimaDoEsperado} de {serie.length} anos acima do esperado · total{' '}
        {metodo.backtest.resumo.violacoes}
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={serie} margin={{ top: 6, right: 8, bottom: 0, left: -26 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey="ano"
            stroke="rgba(255,255,255,0.35)"
            tick={{ fontSize: 10.5 }}
            tickLine={false}
          />
          <YAxis
            domain={dominioY}
            stroke="rgba(255,255,255,0.35)"
            tick={{ fontSize: 10.5 }}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
          />
          <Tooltip content={<DicaAno />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
          <ReferenceLine y={mediaEsperada} stroke="rgba(255,255,255,0.5)" strokeDasharray="4 4" />
          <Bar
            dataKey="violacoes"
            fill={cor}
            radius={[3, 3, 0, 0]}
            maxBarSize={44}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function ViolacoesPorAno({ dados }) {
  const { metodos, ordem_metodos, parametros } = dados
  const alpha = 1 - parametros.confianca

  // um array por método, com o mesmo eixo de anos
  const porMetodo = useMemo(() => {
    const pregoesPorAno = new Map()
    for (const d of metodos[ordem_metodos[0]].backtest.serie) {
      const ano = d.data.slice(0, 4)
      pregoesPorAno.set(ano, (pregoesPorAno.get(ano) || 0) + 1)
    }
    const anos = [...pregoesPorAno.keys()].sort()

    const saida = {}
    for (const nome of ordem_metodos) {
      const contagem = new Map(anos.map((a) => [a, 0]))
      for (const d of metodos[nome].backtest.serie) {
        if (d.violacao) {
          const ano = d.data.slice(0, 4)
          contagem.set(ano, (contagem.get(ano) || 0) + 1)
        }
      }
      saida[nome] = anos.map((ano) => ({
        ano,
        violacoes: contagem.get(ano),
        pregoes: pregoesPorAno.get(ano),
        esperadas: pregoesPorAno.get(ano) * alpha,
      }))
    }
    return saida
  }, [metodos, ordem_metodos, alpha])

  const todas = ordem_metodos.flatMap((n) => porMetodo[n])
  const dominioY = [0, Math.max(...todas.map((a) => a.violacoes)) + 1]
  const mediaEsperada =
    porMetodo[ordem_metodos[0]].reduce((s, a) => s + a.esperadas, 0) /
    Math.max(porMetodo[ordem_metodos[0]].length, 1)

  return (
    <section>
      <div className="titulo-secao">
        <h3>Violações por ano</h3>
        <p className="legenda">
          Barras acima da linha tracejada são anos em que o método furou mais que o previsto —
          tipicamente estresse que a janela histórica ainda não tinha absorvido. A linha marca a
          média anual esperada ({num(mediaEsperada, 1)} violações) e os três painéis dividem a
          mesma escala.
        </p>
      </div>
      <div className="trio">
        {ordem_metodos.map((nome) => (
          <PainelAno
            key={nome}
            metodo={metodos[nome]}
            cor={COR_METODO[nome]}
            serie={porMetodo[nome]}
            dominioY={dominioY}
            mediaEsperada={mediaEsperada}
          />
        ))}
      </div>
    </section>
  )
}

export function Aderencia({ dados }) {
  const { metodos, ordem_metodos, parametros } = dados
  const alpha = 1 - parametros.confianca
  const [foco, setFoco] = useState(ordem_metodos[0])

  const piores = useMemo(() => {
    const serie = metodos[foco].backtest.serie
    return serie
      .filter((d) => d.violacao)
      .map((d) => ({ ...d, excesso: -(d.retorno - d.var) }))
      .sort((a, b) => b.excesso - a.excesso)
      .slice(0, 8)
  }, [metodos, foco])

  return (
    <div className="cartao">
      <h3>Aderência do modelo</h3>
      <p className="legenda">
        Teste de Kupiec (POF), cobertura incondicional. H₀: a taxa de violações é igual a{' '}
        {pct(alpha, 1)}. p-valor abaixo de 0,05 rejeita H₀ — o modelo está mal calibrado, seja por
        furar demais (subestima risco) ou de menos (capital parado à toa).
      </p>

      <table>
        <thead>
          <tr>
            <th>Método</th>
            <th style={{ textAlign: 'right' }}>Violações</th>
            <th style={{ textAlign: 'right' }}>Taxa obs.</th>
            <th style={{ textAlign: 'right' }}>Maior seq.</th>
            <th style={{ textAlign: 'right' }}>LR</th>
            <th style={{ textAlign: 'right' }}>p-valor</th>
            <th style={{ textAlign: 'right' }}>Veredito</th>
          </tr>
        </thead>
        <tbody>
          {ordem_metodos.map((nome) => {
            const r = metodos[nome].backtest.resumo
            const rejeita = r.kupiec.rejeita_5pct
            return (
              <tr key={nome}>
                <td style={{ color: COR_METODO[nome], fontWeight: 500 }}>
                  {metodos[nome].rotulo}
                </td>
                <td className="num">
                  {r.violacoes} / {num(r.violacoes_esperadas, 1)}
                </td>
                <td className="num">{pct(r.taxa_observada)}</td>
                <td className="num">{r.maior_sequencia}</td>
                <td className="num">{num(r.kupiec.estatistica_lr)}</td>
                <td className="num">{num(r.kupiec.p_valor, 3)}</td>
                <td className="num">
                  <span className={`selo-teste ${rejeita ? 'falha' : 'ok'}`}>
                    {rejeita ? 'rejeita H₀' : 'não rejeita'}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <div className="separador" />

      <div className="segmentado">
        <span className="rotulo" style={{ margin: 0 }}>
          Maiores excessos
        </span>
        {ordem_metodos.map((nome) => (
          <button
            key={nome}
            className={`chip${foco === nome ? ' ativo' : ''}`}
            onClick={() => setFoco(nome)}
            style={foco === nome ? { borderColor: COR_METODO[nome], color: COR_METODO[nome] } : undefined}
          >
            {metodos[nome].rotulo}
          </button>
        ))}
      </div>

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
  )
}
