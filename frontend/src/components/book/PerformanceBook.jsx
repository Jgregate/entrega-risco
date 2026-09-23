import {
  CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { COR_SERIE, dataCurta, pctSinal } from '../../formato'
import CartaoGrafico from '../CartaoGrafico'
import {
  CURSOR_LINHA, Dica, MARGEM, PROPS_EIXO_X, PROPS_EIXO_Y, PROPS_GRADE, PROPS_LEGENDA,
  tickPercentual,
} from '../grafico'
import { Alternadores } from '../ui'

/**
 * Evolução do book contra os benchmarks escolhidos.
 *
 * Todas as séries são retorno acumulado indexado a zero no início do recorte —
 * mesma unidade, mesmo eixo. Ligar e desligar benchmark não repinta as
 * curvas que ficaram: a cor segue a série, não a posição na legenda.
 */
export default function PerformanceBook({ dados, benchmarks, selecionados, onAlternar }) {
  const serie = dados.serie || []
  const ativos = (dados.benchmarks || []).filter((b) => b.disponivel)

  return (
    <>
      <div className="linha-filtros">
        <span className="rotulo" style={{ margin: 0 }}>
          Comparar com
        </span>
        <Alternadores
          aria="Benchmarks do gráfico"
          selecionados={selecionados}
          onAlternar={onAlternar}
          opcoes={(benchmarks || []).map((b) => ({
            valor: b.chave,
            texto: b.rotulo,
            cor: COR_SERIE[b.chave],
          }))}
        />
      </div>

      <CartaoGrafico
        titulo="Rentabilidade acumulada do book"
        altura={300}
        subtitulo={`Carteira e benchmarks indexados a zero em ${dataCurta(
          dados.periodo.inicio
        )}. Rentabilidade time-weighted: aporte não vira valorização.`}
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
                type="monotone" dataKey="fundo" name="Meu book"
                stroke={COR_SERIE.carteira} strokeWidth={2.2} dot={false} isAnimationActive={false}
              />
              {ativos.map((b) => (
                <Line
                  key={b.chave}
                  type="monotone"
                  dataKey={b.chave}
                  name={b.rotulo}
                  stroke={COR_SERIE[b.chave] || COR_SERIE.benchmark}
                  strokeWidth={1.3}
                  dot={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </CartaoGrafico>

      {(dados.benchmarks || []).some((b) => !b.disponivel) && (
        <p className="ressalva">
          <span aria-hidden="true">ⓘ</span> Não foi possível obter agora a série de:{' '}
          {dados.benchmarks
            .filter((b) => !b.disponivel)
            .map((b) => b.rotulo)
            .join(', ')}
          .
        </p>
      )}
    </>
  )
}
