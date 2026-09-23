import {
  Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { CORES, dataCurta, inteiro, pct } from '../../formato'
import CartaoGrafico from '../CartaoGrafico'
import {
  CURSOR_LINHA, Dica, MARGEM, PROPS_EIXO_X, PROPS_EIXO_Y, PROPS_GRADE, tickPercentual,
} from '../grafico'
import { GradeKpis, Kpi, Vazio } from '../ui'

/**
 * Drawdown: a distância entre a cota de hoje e o topo que ela já atingiu.
 *
 * Desenhado como área abaixo de zero — a forma já conta a história (quanto
 * fundo, por quanto tempo) sem precisar de rótulo em cada ponto. A área
 * sempre parte de zero no topo, então a escala não engana.
 */
export default function Drawdown({ dados }) {
  const { drawdown: dd, serie, periodo } = dados
  const comDd = serie.filter((p) => p.drawdown !== null && p.drawdown !== undefined)

  return (
    <>
      <GradeKpis colunas={4} compacto>
        <Kpi
          rotulo="Drawdown atual"
          valor={pct(dd.atual, 2)}
          cor={dd.atual < -0.0001 ? CORES.vermelhoClaro : undefined}
          destaque={dd.atual < -0.0001}
          nota={dd.atual < -0.0001 ? 'abaixo do topo histórico do período' : 'no topo histórico do período'}
        />
        <Kpi
          rotulo="Drawdown máximo"
          valor={pct(dd.maximo, 2)}
          nota={dd.inicio_maximo ? `queda iniciada em ${dataCurta(dd.inicio_maximo)}` : undefined}
        />
        <Kpi
          rotulo="Data do maior drawdown"
          valor={dataCurta(dd.data_maximo)}
          nota="pregão em que a cota ficou mais longe do topo"
        />
        <Kpi
          rotulo="Tempo de recuperação"
          valor={
            dd.em_recuperacao
              ? 'em curso'
              : dd.dias_recuperacao !== null
                ? `${inteiro(dd.dias_recuperacao)} dias`
                : '—'
          }
          nota={
            dd.em_recuperacao
              ? 'o fundo ainda não voltou ao topo anterior'
              : dd.data_recuperacao
                ? `topo retomado em ${dataCurta(dd.data_recuperacao)}`
                : undefined
          }
        />
      </GradeKpis>

      <CartaoGrafico
        titulo="Histórico de drawdown"
        altura={260}
        subtitulo={`Queda percentual sobre o topo anterior, pregão a pregão, de ${dataCurta(
          periodo.inicio
        )} a ${dataCurta(periodo.fim)}. Zero significa que a cota está no topo.`}
      >
        {(altura) =>
          comDd.length < 2 ? (
            <Vazio motivo="O período selecionado não tem pregões suficientes.">
              Sem série de drawdown.
            </Vazio>
          ) : (
            <ResponsiveContainer width="100%" height={altura}>
              <AreaChart data={comDd} margin={MARGEM}>
                <defs>
                  <linearGradient id="grad-dd" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={CORES.vermelhoClaro} stopOpacity={0.05} />
                    <stop offset="100%" stopColor={CORES.vermelhoClaro} stopOpacity={0.45} />
                  </linearGradient>
                </defs>
                <CartesianGrid {...PROPS_GRADE} />
                <XAxis dataKey="data" {...PROPS_EIXO_X} tickFormatter={dataCurta} />
                <YAxis {...PROPS_EIXO_Y} width={56} tickFormatter={tickPercentual(0)} />
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.25)" />
                {dd.maximo !== null && (
                  <ReferenceLine
                    y={dd.maximo}
                    stroke={CORES.vermelhoMedio}
                    label={{
                      value: `máximo ${pct(dd.maximo, 1)}`,
                      position: 'insideBottomRight',
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
                  type="monotone" dataKey="drawdown" name="Drawdown"
                  stroke={CORES.vermelhoClaro} strokeWidth={1.6} fill="url(#grad-dd)"
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )
        }
      </CartaoGrafico>
    </>
  )
}
