import {
  Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { CORES, brlCurto, dataCurta, inteiro } from '../../formato'
import CartaoGrafico from '../CartaoGrafico'
import {
  CURSOR_LINHA, Dica, MARGEM, PROPS_EIXO_X, PROPS_EIXO_Y, PROPS_GRADE, PROPS_LEGENDA,
} from '../grafico'
import { Vazio } from '../ui'

/**
 * Patrimônio e cotistas.
 *
 * São DOIS gráficos, não um com dois eixos: reais e número de pessoas não
 * compartilham escala, e sobrepor as duas curvas num eixo duplo inventaria
 * uma correlação que os dados não têm. Lado a lado, o leitor compara as
 * formas e tira a própria conclusão.
 */
export default function Patrimonio({ dados }) {
  const serie = dados.patrimonio.serie || []

  if (serie.length < 2) {
    return (
      <Vazio motivo="A CVM não publicou série de patrimônio para esse fundo no período.">
        Sem histórico de patrimônio.
      </Vazio>
    )
  }

  const temTotal = serie.some((p) => p.patrimonio_total !== null && p.patrimonio_total !== undefined)
  const temCotistas = serie.some((p) => p.cotistas !== null && p.cotistas !== undefined)

  return (
    <div className="duo">
      <CartaoGrafico
        titulo="Patrimônio"
        altura={260}
        subtitulo={
          temTotal
            ? 'Patrimônio líquido (após obrigações) e patrimônio total aplicado, em reais.'
            : 'Patrimônio líquido do fundo, em reais.'
        }
      >
        {(altura) => (
          <ResponsiveContainer width="100%" height={altura}>
            <AreaChart data={serie} margin={MARGEM}>
              <defs>
                <linearGradient id="grad-pl" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CORES.vermelhoClaro} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={CORES.vermelhoClaro} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid {...PROPS_GRADE} />
              <XAxis dataKey="data" {...PROPS_EIXO_X} tickFormatter={dataCurta} />
              <YAxis {...PROPS_EIXO_Y} width={74} tickFormatter={brlCurto} />
              <Tooltip
                content={<Dica formatar={(v) => brlCurto(v)} rotularData={dataCurta} />}
                cursor={CURSOR_LINHA}
              />
              <Legend {...PROPS_LEGENDA} />
              {temTotal && (
                <Area
                  type="monotone" dataKey="patrimonio_total" name="Patrimônio total"
                  stroke={CORES.vermelhoMedio} strokeWidth={1.2} fill="transparent"
                  isAnimationActive={false}
                />
              )}
              <Area
                type="monotone" dataKey="patrimonio_liquido" name="Patrimônio líquido"
                stroke={CORES.vermelhoClaro} strokeWidth={2} fill="url(#grad-pl)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CartaoGrafico>

      {temCotistas ? (
        <CartaoGrafico
          titulo="Cotistas"
          altura={260}
          subtitulo="Número de cotistas da classe, pregão a pregão. Cresce com captação e cai com resgate."
        >
          {(altura) => (
            <ResponsiveContainer width="100%" height={altura}>
              <LineChart data={serie} margin={MARGEM}>
                <CartesianGrid {...PROPS_GRADE} />
                <XAxis dataKey="data" {...PROPS_EIXO_X} tickFormatter={dataCurta} />
                <YAxis {...PROPS_EIXO_Y} width={62} tickFormatter={(v) => inteiro(v)} />
                <Tooltip
                  content={<Dica formatar={(v) => `${inteiro(v)} cotistas`} rotularData={dataCurta} />}
                  cursor={CURSOR_LINHA}
                />
                <Line
                  type="monotone" dataKey="cotistas" name="Cotistas"
                  stroke={CORES.branco} strokeWidth={1.8} dot={false} isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CartaoGrafico>
      ) : (
        <Vazio motivo="O informe diário do período não traz número de cotistas para esse fundo.">
          Sem série de cotistas.
        </Vazio>
      )}
    </div>
  )
}
