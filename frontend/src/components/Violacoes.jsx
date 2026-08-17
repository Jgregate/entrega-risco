import { useMemo, useState } from 'react'
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
import { COR_METODO, dataCurta, num, pct } from '../formato'
import { recortar } from '../janela'
import CartaoGrafico from './CartaoGrafico'

function DicaAno({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-data">{label}</div>
      <div>
        taxa observada <strong>{pct(p.taxa)}</strong>
      </div>
      <div style={{ color: 'rgba(255,255,255,0.55)' }}>
        {p.violacoes} violações em {p.observacoes} observações
      </div>
      <div style={{ color: 'rgba(255,255,255,0.55)' }}>esperado: {pct(p.esperado)}</div>
    </div>
  )
}

function PainelAno({ metodo, cor, serie, dominioY, esperado }) {
  const acima = serie.filter((b) => b.taxa > b.esperado).length

  return (
    <CartaoGrafico
      titulo={metodo.rotulo}
      cor={cor}
      altura={220}
      subtitulo={`${acima} de ${serie.length} ano(s) acima do esperado · ${metodo.descricao}`}
    >
      {(altura) => (
        <ResponsiveContainer width="100%" height={altura}>
          <BarChart data={serie} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
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
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            />
            <Tooltip content={<DicaAno />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
            <ReferenceLine y={esperado} stroke="rgba(255,255,255,0.55)" strokeDasharray="4 4" />
            {/* com poucos anos na janela a barra fina fica perdida no eixo */}
            <Bar
              dataKey="taxa"
              radius={[3, 3, 0, 0]}
              maxBarSize={serie.length <= 3 ? 110 : 54}
              isAnimationActive={false}
            >
              {serie.map((b, i) => (
                <Cell key={i} fill={cor} fillOpacity={b.taxa > b.esperado ? 1 : 0.45} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </CartaoGrafico>
  )
}

/**
 * Violações em TAXA (violações ÷ observações do ano), não em contagem.
 * Em taxa a linha do esperado é a mesma em qualquer ano — é o próprio
 * 1 − confiança — então anos com número diferente de pregões continuam
 * comparáveis entre si e entre métodos.
 */
export function ViolacoesPorAno({ dados, corte }) {
  const { metodos, ordem_metodos, parametros } = dados
  const esperado = 1 - parametros.confianca

  const porMetodo = useMemo(() => {
    const saida = {}
    for (const nome of ordem_metodos) {
      const mapa = new Map()
      for (const d of recortar(metodos[nome].backtest.serie, corte)) {
        const ano = d.data.slice(0, 4)
        const linha = mapa.get(ano) || { ano, observacoes: 0, violacoes: 0, esperado }
        linha.observacoes += 1
        if (d.violacao) linha.violacoes += 1
        mapa.set(ano, linha)
      }
      saida[nome] = [...mapa.values()]
        .map((l) => ({ ...l, taxa: l.observacoes ? l.violacoes / l.observacoes : 0 }))
        .sort((a, b) => a.ano.localeCompare(b.ano))
    }
    return saida
  }, [metodos, ordem_metodos, corte, esperado])

  const maxTaxa = Math.max(
    ...ordem_metodos.flatMap((n) => porMetodo[n].map((b) => b.taxa)),
    esperado
  )
  const dominioY = [0, Math.ceil((maxTaxa * 1.12) / 0.01) * 0.01]

  return (
    <section>
      <div className="titulo-secao">
        <h3>Violações por ano</h3>
        <p className="legenda">
          Cada barra é a <strong>taxa de violações</strong> do ano — violações dividido pelo número
          de observações do período — e não a contagem bruta. Em taxa a linha tracejada do esperado
          ({pct(esperado, 1)}) vale para qualquer ano, então anos com mais ou menos pregões
          continuam comparáveis. Barras cheias estão acima do esperado.
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
            esperado={esperado}
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
      <h3>
        Aderência do modelo <span className="selo-teste ok">período completo</span>
      </h3>
      <p className="legenda">
        Teste de Kupiec (POF), cobertura incondicional, sobre todo o histórico — a janela dos
        gráficos não se aplica aqui: com um ou dois anos de dados o teste perde poder e o
        p-valor deixa de significar muita coisa. H₀: a taxa de violações é igual a{' '}
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
            style={
              foco === nome
                ? { borderColor: COR_METODO[nome], color: COR_METODO[nome] }
                : undefined
            }
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
