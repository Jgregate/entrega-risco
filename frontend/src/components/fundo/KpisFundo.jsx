import { CORES, brlCurto, inteiro, num, pct, pctSinal } from '../../formato'
import { GradeKpis, Kpi, Variacao } from '../ui'

/**
 * Os números que respondem "como esse fundo está" antes de qualquer gráfico.
 *
 * Indicador que o período não permite calcular aparece como "—" com a razão
 * na nota, nunca omitido: sumir com o cartão faria a grade dançar a cada troca
 * de período e esconderia que o número existe, só não cabe nessa janela.
 */
export default function KpisFundo({ dados }) {
  const { metricas: m, patrimonio, janelas, periodo, benchmark, variacao_anterior } = dados

  // o segundo cartão nunca repete a janela que já está no primeiro: quando o
  // período selecionado é 12m, ele passa para a próxima janela disponível
  const secundaria =
    ['12m', '24m', '36m', 'inicio']
      .filter((c) => c !== periodo.chave)
      .map((c) => janelas.find((j) => j.chave === c && j.disponivel))
      .find(Boolean) || null

  // a comparação com o período anterior é a DIFERENÇA entre os dois retornos,
  // em pontos percentuais — não o retorno de antes
  const doze = janelas.find((j) => j.chave === '12m' && j.disponivel)
  const deltaAnterior =
    doze && variacao_anterior?.retorno_12m !== null && variacao_anterior?.retorno_12m !== undefined
      ? doze.retorno - variacao_anterior.retorno_12m
      : null

  const curto = m.observacoes < 252
  const notaCurto = curto ? 'exige 12 meses de histórico' : undefined

  return (
    <>
      <GradeKpis colunas={4}>
        <Kpi
          rotulo={`Rentabilidade · ${periodo.rotulo}`}
          valor={pctSinal(m.retorno_acumulado)}
          cor={CORES.vermelhoClaro}
          destaque
          variacao={
            periodo.chave === '12m' ? (
              <Variacao valor={deltaAnterior} sufixo="vs. os 12 meses anteriores" />
            ) : null
          }
          nota={
            m.benchmark_acumulado !== null && m.benchmark_acumulado !== undefined
              ? `${benchmark.rotulo}: ${pctSinal(m.benchmark_acumulado)}`
              : 'sem benchmark comparável no período'
          }
        />
        <Kpi
          rotulo={`Rentabilidade · ${secundaria ? secundaria.rotulo : '12 meses'}`}
          valor={secundaria ? pctSinal(secundaria.retorno) : '—'}
          nota={
            secundaria
              ? secundaria.completo
                ? `${benchmark.rotulo}: ${pctSinal(secundaria.benchmark)}`
                : 'histórico menor que a janela'
              : 'sem outra janela disponível'
          }
        />
        <Kpi
          rotulo="Patrimônio líquido"
          valor={brlCurto(patrimonio.atual)}
          nota={
            patrimonio.medio_12m
              ? `PL médio 12m: ${brlCurto(patrimonio.medio_12m)}`
              : 'sem série de patrimônio publicada'
          }
        />
        <Kpi
          rotulo="Cotistas"
          valor={inteiro(patrimonio.cotistas)}
          nota={patrimonio.data ? `posição de ${patrimonio.data.split('-').reverse().join('/')}` : undefined}
        />
      </GradeKpis>

      <GradeKpis colunas={5} compacto>
        <Kpi
          rotulo="Volatilidade anualizada"
          valor={pct(m.volatilidade_anualizada, 1)}
          nota={`${m.observacoes} pregões no período`}
        />
        <Kpi
          rotulo="Índice de Sharpe"
          valor={num(m.sharpe)}
          nota={m.sharpe === null ? notaCurto || 'volatilidade nula' : 'excesso sobre o CDI'}
          titulo="Excesso de retorno anualizado sobre o CDI, dividido pela volatilidade anualizada."
        />
        <Kpi
          rotulo="Drawdown atual"
          valor={pct(m.drawdown_atual, 2)}
          cor={m.drawdown_atual < -0.0001 ? CORES.vermelhoClaro : undefined}
          nota={
            m.drawdown_maximo !== null
              ? `máximo no período: ${pct(m.drawdown_maximo, 2)}`
              : undefined
          }
        />
        <Kpi
          rotulo={`Contra o ${benchmark.rotulo}`}
          valor={
            m.percentual_do_benchmark !== null && m.percentual_do_benchmark !== undefined
              ? `${num(m.percentual_do_benchmark * 100, 0)}%`
              : pctSinal(m.excesso_acumulado)
          }
          nota={
            m.excesso_acumulado !== null && m.excesso_acumulado !== undefined
              ? `${pctSinal(m.excesso_acumulado)} de excesso`
              : 'benchmark indisponível'
          }
          titulo="Quanto o fundo rendeu em relação ao benchmark no período (100% = empate)."
        />
        <Kpi
          rotulo="Desde o início"
          valor={pctSinal(janelas.find((j) => j.chave === 'inicio')?.retorno)}
          nota={
            periodo.historico_desde
              ? `desde ${periodo.historico_desde.split('-').reverse().join('/')}`
              : undefined
          }
        />
      </GradeKpis>
    </>
  )
}
