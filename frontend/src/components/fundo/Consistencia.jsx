import { MESES_ABREV, corDivergente, pct, pctSinal } from '../../formato'
import { GradeKpis, Kpi, Vazio } from '../ui'

/**
 * Consistência: não "quanto rendeu", mas "com que regularidade".
 *
 * A faixa de quadradinhos é um pequeno múltiplo temporal — um quadrado por
 * mês, na ordem. Ela responde de relance o que a tabela mensal responde com
 * precisão: onde estão as sequências boas e ruins. Quando há benchmark, um
 * traço embaixo do quadrado marca os meses em que o fundo o superou — um
 * segundo canal, para a informação não depender só da cor.
 */
export default function Consistencia({ dados, rotuloBenchmark }) {
  const c = dados.consistencia
  if (!c || !c.serie?.length) {
    return (
      <Vazio motivo="O período selecionado não fecha nenhum mês-calendário.">
        Sem meses fechados para medir consistência.
      </Vazio>
    )
  }

  const vmax = Math.max(...c.serie.map((m) => Math.abs(m.retorno ?? 0)), 0.01)
  const temBenchmark = c.serie.some((m) => m.benchmark !== null && m.benchmark !== undefined)

  return (
    <>
      <GradeKpis colunas={5} compacto>
        <Kpi rotulo="Meses positivos" valor={`${c.positivos} de ${c.meses}`} nota={pct(c.percentual_positivos, 1)} />
        <Kpi rotulo="Meses negativos" valor={`${c.negativos} de ${c.meses}`} />
        <Kpi
          rotulo={`Meses acima do ${rotuloBenchmark}`}
          valor={
            c.acima_benchmark === null || c.acima_benchmark === undefined
              ? '—'
              : `${c.acima_benchmark} de ${c.meses_comparaveis}`
          }
          nota={
            c.percentual_acima_benchmark !== null && c.percentual_acima_benchmark !== undefined
              ? pct(c.percentual_acima_benchmark, 1)
              : 'benchmark indisponível'
          }
        />
        <Kpi
          rotulo="Maior sequência positiva"
          valor={`${c.maior_sequencia_positiva} ${c.maior_sequencia_positiva === 1 ? 'mês' : 'meses'}`}
        />
        <Kpi
          rotulo="Maior sequência negativa"
          valor={`${c.maior_sequencia_negativa} ${c.maior_sequencia_negativa === 1 ? 'mês' : 'meses'}`}
        />
      </GradeKpis>

      <div className="cartao">
        <h4>Mês a mês</h4>
        <p className="legenda-mini">
          Um quadrado por mês fechado, do mais antigo ao mais recente. A cor é o retorno
          (vermelho = queda, claro = alta).
          {temBenchmark && (
            <> O traço embaixo marca os meses em que o fundo superou o {rotuloBenchmark}.</>
          )}
        </p>

        <div className="faixa-meses">
          {c.serie.map((m) => {
            const cor = corDivergente(m.retorno, vmax)
            const bateu =
              m.benchmark !== null && m.benchmark !== undefined && m.retorno > m.benchmark
            return (
              <div
                key={`${m.ano}-${m.mes}`}
                className={`quadro-mes${bateu ? ' bateu' : ''}`}
                style={{ background: cor }}
                title={
                  `${MESES_ABREV[m.mes - 1]}/${m.ano}: ${pctSinal(m.retorno)}` +
                  (m.benchmark !== null && m.benchmark !== undefined
                    ? ` · ${rotuloBenchmark}: ${pctSinal(m.benchmark)}`
                    : '')
                }
              >
                <span className="quadro-rotulo">{MESES_ABREV[m.mes - 1]}</span>
              </div>
            )
          })}
        </div>

        <div className="legenda-escala">
          <span className="legenda-escala-rotulo">{pctSinal(-vmax)}</span>
          <span className="legenda-escala-barra" />
          <span className="legenda-escala-rotulo">{pctSinal(vmax)}</span>
        </div>
      </div>
    </>
  )
}
