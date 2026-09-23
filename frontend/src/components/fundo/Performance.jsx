import {
  Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { COR_SERIE, CORES, dataCurta, num, pct, pctSinal } from '../../formato'
import CartaoGrafico from '../CartaoGrafico'
import {
  CURSOR_LINHA, Dica, MARGEM, PROPS_EIXO_X, PROPS_EIXO_Y, PROPS_GRADE, tickPercentual,
} from '../grafico'
import { Vazio } from '../ui'

/** Uma linha da ficha de indicadores: nome, valor e o que ele significa. */
function Indicador({ rotulo, valor, explicacao, ausente }) {
  return (
    <tr>
      <th scope="row">
        {rotulo}
        <span className="indicador-ajuda">{explicacao}</span>
      </th>
      <td className={`num${ausente ? ' dado-ausente' : ''}`}>{valor}</td>
    </tr>
  )
}

/**
 * Ficha de índices de performance e risco (§ "Índices e métricas") ao lado da
 * evolução da volatilidade.
 *
 * Indicador que a janela não permite calcular aparece como "—" com o motivo
 * ao lado, em vez de sumir: o usuário precisa saber que o número existe e por
 * que não está ali.
 */
export default function Performance({ dados }) {
  const { metricas: m, serie, benchmark, periodo } = dados
  const curto = m.observacoes < 252

  const comVol = serie.filter((p) => p.volatilidade !== null && p.volatilidade !== undefined)

  return (
    <div className="duo">
      <div className="cartao">
        <h4>Índices de performance e risco</h4>
        <p className="legenda-mini">
          Calculados sobre os {m.observacoes} pregões de {dataCurta(periodo.inicio)} a{' '}
          {dataCurta(periodo.fim)}. Sharpe e Sortino usam o CDI como taxa livre de risco.
        </p>

        <table className="tabela-indicadores">
          <tbody>
            <Indicador
              rotulo="Rentabilidade acumulada"
              explicacao="retorno composto no período"
              valor={pctSinal(m.retorno_acumulado)}
            />
            <Indicador
              rotulo="Rentabilidade anualizada"
              explicacao={curto ? 'exige 12 meses — não é extrapolada' : 'retorno composto ao ano'}
              valor={pct(m.retorno_anualizado)}
              ausente={m.retorno_anualizado === null}
            />
            <Indicador
              rotulo="Volatilidade anualizada"
              explicacao="desvio-padrão dos retornos diários × √252"
              valor={pct(m.volatilidade_anualizada, 2)}
            />
            <Indicador
              rotulo="Volatilidade 12 meses"
              explicacao="mesma conta, só nos últimos 252 pregões"
              valor={pct(m.volatilidade_12m, 2)}
              ausente={m.volatilidade_12m === null}
            />
            <Indicador
              rotulo="Índice de Sharpe"
              explicacao="excesso sobre o CDI por unidade de risco total"
              valor={num(m.sharpe)}
              ausente={m.sharpe === null}
            />
            <Indicador
              rotulo="Índice de Sortino"
              explicacao="idem, punindo só a oscilação de queda"
              valor={num(m.sortino)}
              ausente={m.sortino === null}
            />
            <Indicador
              rotulo="Drawdown máximo"
              explicacao={
                m.data_drawdown_maximo ? `fundo em ${dataCurta(m.data_drawdown_maximo)}` : 'maior queda sobre o topo'
              }
              valor={pct(m.drawdown_maximo, 2)}
            />
            <Indicador
              rotulo="Drawdown atual"
              explicacao="distância para o topo histórico da janela"
              valor={pct(m.drawdown_atual, 2)}
            />
            <Indicador
              rotulo={`Retorno vs. ${benchmark.rotulo}`}
              explicacao="diferença de retorno acumulado"
              valor={pctSinal(m.excesso_acumulado)}
              ausente={m.excesso_acumulado === null}
            />
            <Indicador
              rotulo={`% do ${benchmark.rotulo}`}
              explicacao="100% = empatou com o benchmark"
              valor={
                m.percentual_do_benchmark === null || m.percentual_do_benchmark === undefined
                  ? '—'
                  : `${num(m.percentual_do_benchmark * 100, 0)}%`
              }
              ausente={m.percentual_do_benchmark === null}
            />
            <Indicador
              rotulo="Meses positivos"
              explicacao={`${m.meses_positivos} de ${m.meses_positivos + m.meses_negativos} meses fechados`}
              valor={pct(m.percentual_meses_positivos, 1)}
              ausente={m.percentual_meses_positivos === null}
            />
            <Indicador
              rotulo={`Meses acima do ${benchmark.rotulo}`}
              explicacao="fração dos meses em que superou o benchmark"
              valor={pct(m.percentual_meses_acima_benchmark, 1)}
              ausente={m.percentual_meses_acima_benchmark === null}
            />
            <Indicador
              rotulo="Consistência (12m móveis)"
              explicacao="fração das janelas de 12 meses em que bateu o benchmark"
              valor={pct(m.consistencia_12m, 1)}
              ausente={m.consistencia_12m === null}
            />
          </tbody>
        </table>
      </div>

      <CartaoGrafico
        titulo="Evolução da volatilidade"
        altura={300}
        subtitulo="Desvio-padrão dos retornos numa janela móvel de 21 pregões, anualizado. Mostra se o risco do fundo mudou de patamar."
      >
        {(altura) =>
          comVol.length < 2 ? (
            <Vazio motivo="A janela móvel de 21 pregões não cabe no período selecionado.">
              Sem volatilidade móvel para exibir.
            </Vazio>
          ) : (
            <ResponsiveContainer width="100%" height={altura}>
              <AreaChart data={comVol} margin={MARGEM}>
                <defs>
                  <linearGradient id="grad-vol" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COR_SERIE.fundo} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={COR_SERIE.fundo} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid {...PROPS_GRADE} />
                <XAxis dataKey="data" {...PROPS_EIXO_X} tickFormatter={dataCurta} />
                <YAxis {...PROPS_EIXO_Y} width={56} tickFormatter={tickPercentual(0)} />
                {m.volatilidade_anualizada > 0 && (
                  <ReferenceLine
                    y={m.volatilidade_anualizada}
                    stroke={CORES.eixo}
                    strokeWidth={1}
                    label={{
                      value: `média ${pct(m.volatilidade_anualizada, 1)}`,
                      position: 'insideTopRight',
                      fill: 'rgba(255,255,255,0.55)',
                      fontSize: 10,
                    }}
                  />
                )}
                <Tooltip
                  content={<Dica formatar={(v) => pct(v, 2)} rotularData={dataCurta} />}
                  cursor={CURSOR_LINHA}
                />
                <Area
                  type="monotone" dataKey="volatilidade" name="Volatilidade anualizada"
                  stroke={COR_SERIE.fundo} strokeWidth={2} fill="url(#grad-vol)"
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )
        }
      </CartaoGrafico>
    </div>
  )
}
