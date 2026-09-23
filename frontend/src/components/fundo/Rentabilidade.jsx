import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { COR_SERIE, dataCurta, pct, pctSinal } from '../../formato'
import CartaoGrafico from '../CartaoGrafico'
import {
  CURSOR_BARRA, CURSOR_LINHA, Dica, MARGEM, PROPS_EIXO_X, PROPS_EIXO_Y,
  PROPS_GRADE, PROPS_LEGENDA, tickPercentual,
} from '../grafico'
import { Vazio } from '../ui'

/**
 * Rentabilidade acumulada do fundo contra o benchmark, e o retorno em cada
 * janela rápida.
 *
 * As duas séries dividem o MESMO eixo porque as duas são "retorno acumulado
 * desde o início do recorte" — mesma unidade, mesma base zero. É essa
 * normalização que torna a comparação honesta.
 */
export default function Rentabilidade({ dados }) {
  const { serie, janelas, benchmark, periodo } = dados
  const temBenchmark = benchmark.disponivel && serie.some((p) => p.benchmark !== null)
  const temCdi = serie.some((p) => p.cdi !== null && p.cdi !== undefined)

  const disponiveis = janelas.filter((j) => j.disponivel)

  return (
    <div className="duo duo-largo">
      <CartaoGrafico
        titulo="Rentabilidade acumulada"
        altura={280}
        subtitulo={`Fundo e ${benchmark.rotulo} indexados a zero no início do período (${dataCurta(
          periodo.inicio
        )}).`}
      >
        {(altura) => (
          <ResponsiveContainer width="100%" height={altura}>
            <LineChart data={serie} margin={MARGEM}>
              <CartesianGrid {...PROPS_GRADE} />
              <XAxis dataKey="data" {...PROPS_EIXO_X} tickFormatter={dataCurta} />
              <YAxis {...PROPS_EIXO_Y} width={56} tickFormatter={tickPercentual(0)} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.18)" />
              <Tooltip
                content={<Dica formatar={(v) => pctSinal(v)} rotularData={dataCurta} />}
                cursor={CURSOR_LINHA}
              />
              <Legend {...PROPS_LEGENDA} />
              <Line
                type="monotone" dataKey="fundo" name="Fundo"
                stroke={COR_SERIE.fundo} strokeWidth={2} dot={false} isAnimationActive={false}
              />
              {temBenchmark && (
                <Line
                  type="monotone" dataKey="benchmark" name={benchmark.rotulo}
                  stroke={COR_SERIE.benchmark} strokeWidth={1.4} dot={false}
                  isAnimationActive={false}
                />
              )}
              {temCdi && (
                <Line
                  type="monotone" dataKey="cdi" name="CDI"
                  stroke={COR_SERIE.cdi} strokeWidth={1.2} dot={false}
                  isAnimationActive={false}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        )}
      </CartaoGrafico>

      <CartaoGrafico
        titulo="Retorno por janela"
        altura={280}
        subtitulo="Cada janela é contada para trás a partir do último pregão disponível — não depende do período selecionado acima."
      >
        {(altura) =>
          disponiveis.length === 0 ? (
            <Vazio motivo="O fundo ainda não tem dois pregões publicados.">
              Sem janelas calculáveis.
            </Vazio>
          ) : (
            <ResponsiveContainer width="100%" height={altura}>
              <BarChart data={disponiveis} margin={MARGEM} barGap={2}>
                <CartesianGrid {...PROPS_GRADE} />
                <XAxis dataKey="rotulo" {...PROPS_EIXO_X} minTickGap={4} />
                <YAxis {...PROPS_EIXO_Y} width={56} tickFormatter={tickPercentual(0)} />
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.18)" />
                <Tooltip
                  content={
                    <Dica
                      formatar={(v) => pctSinal(v)}
                      extra={(_, rotulo) => {
                        const j = disponiveis.find((x) => x.rotulo === rotulo)
                        return j && !j.completo ? 'janela maior que o histórico do fundo' : null
                      }}
                    />
                  }
                  cursor={CURSOR_BARRA}
                />
                <Legend {...PROPS_LEGENDA} iconType="square" />
                <Bar dataKey="retorno" name="Fundo" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {disponiveis.map((j) => (
                    // janela incompleta fica esmaecida: o número existe, mas
                    // não cobre o período inteiro que o rótulo promete
                    <Cell
                      key={j.chave}
                      fill={COR_SERIE.fundo}
                      fillOpacity={j.completo ? 1 : 0.45}
                    />
                  ))}
                </Bar>
                {temBenchmark && (
                  <Bar
                    dataKey="benchmark" name={benchmark.rotulo} fill={COR_SERIE.benchmark}
                    radius={[4, 4, 0, 0]} isAnimationActive={false} fillOpacity={0.85}
                  />
                )}
              </BarChart>
            </ResponsiveContainer>
          )
        }
      </CartaoGrafico>

      <div className="cartao tabela-janelas">
        <h4>Rentabilidade por período</h4>
        <p className="legenda-mini">
          Mesmos números do gráfico ao lado, para leitura exata e cópia.
        </p>
        <table>
          <thead>
            <tr>
              <th>Período</th>
              <th className="col-num">Fundo</th>
              <th className="col-num">{benchmark.rotulo}</th>
              <th className="col-num">Excesso</th>
              <th className="col-num">Volatilidade</th>
            </tr>
          </thead>
          <tbody>
            {janelas.map((j) => (
              <tr key={j.chave} className={j.disponivel ? undefined : 'linha-ausente'}>
                <td>
                  {j.rotulo}
                  {j.disponivel && !j.completo && (
                    <span className="marca-parcial" title="Janela maior que o histórico do fundo">
                      {' '}parcial
                    </span>
                  )}
                </td>
                <td className={`num ${j.retorno < 0 ? 'perda' : 'ganho'}`}>
                  {j.disponivel ? pctSinal(j.retorno) : '—'}
                </td>
                <td className="num">{j.benchmark !== null ? pctSinal(j.benchmark) : '—'}</td>
                <td className="num">
                  {j.disponivel && j.benchmark !== null && j.benchmark !== undefined
                    ? pctSinal(j.retorno - j.benchmark)
                    : '—'}
                </td>
                <td className="num">{j.disponivel ? pct(j.volatilidade, 1) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
