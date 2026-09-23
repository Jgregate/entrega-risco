import { useMemo, useState } from 'react'
import { MESES_ABREV, corDivergente, corTextoLegivel, num, pctSinal } from '../../formato'
import { Segmentado, Vazio } from '../ui'

/**
 * Rentabilidade histórica: ano nas linhas, mês nas colunas, acumulado do ano
 * na ponta — o formato que o mercado lê sem legenda.
 *
 * A cor da célula é uma escala DIVERGENTE: vermelho para queda, branco para
 * alta e cinza neutro no meio, com a escala fixa no maior |retorno| da tabela
 * para as duas asas terem o mesmo passo. O meio é acromático de propósito:
 * mês perto de zero tem que se dissolver no fundo em vez de competir por
 * atenção. O número fica escrito em cada célula, então a cor reforça a
 * leitura — nunca é o único jeito de saber o valor.
 */
export default function TabelaMensal({ linhas, rotuloBenchmark }) {
  const [serie, setSerie] = useState('fundo')

  const { dados, vmax } = useMemo(() => {
    if (!linhas?.length) return { dados: [], vmax: 1 }
    const doBenchmark = serie === 'benchmark'
    let max = 0
    const saida = linhas.map((l) => {
      const meses = doBenchmark ? l.meses_benchmark : l.meses
      const acumulado = doBenchmark ? l.acumulado_benchmark : l.acumulado
      for (const v of meses || []) {
        if (v !== null && v !== undefined) max = Math.max(max, Math.abs(v))
      }
      return { ano: l.ano, meses: meses || new Array(12).fill(null), acumulado }
    })
    return { dados: saida, vmax: max || 0.01 }
  }, [linhas, serie])

  if (!linhas?.length) {
    return (
      <Vazio motivo="O período selecionado não fecha nenhum mês-calendário.">
        Sem rentabilidade mensal para exibir.
      </Vazio>
    )
  }

  const temBenchmark = linhas.some((l) => l.meses_benchmark)

  return (
    <div className="cartao">
      <div className="cartao-cabecalho">
        <div>
          <h4>Rentabilidade histórica mensal</h4>
          <p className="legenda-mini">
            Retorno de cada mês-calendário e o acumulado do ano. Vermelho é queda,
            claro é alta; a intensidade é proporcional ao maior movimento da tabela.
          </p>
        </div>
        {temBenchmark && (
          <Segmentado
            aria="Série exibida na tabela"
            valor={serie}
            onMudar={setSerie}
            opcoes={[
              { valor: 'fundo', texto: 'Fundo' },
              { valor: 'benchmark', texto: rotuloBenchmark || 'Benchmark' },
            ]}
          />
        )}
      </div>

      <div className="rolagem-horizontal">
        <table className="tabela-mensal">
          <thead>
            <tr>
              <th scope="col">Ano</th>
              {MESES_ABREV.map((m) => (
                <th key={m} scope="col" className="col-mes">
                  {m}
                </th>
              ))}
              <th scope="col" className="col-num col-acumulado">
                Ano
              </th>
            </tr>
          </thead>
          <tbody>
            {dados.map((linha) => (
              <tr key={linha.ano}>
                <th scope="row">{linha.ano}</th>
                {linha.meses.map((v, i) => {
                  const cor = corDivergente(v, vmax)
                  return (
                    <td
                      key={i}
                      className={`celula-mes${v === null || v === undefined ? ' vazia' : ''}`}
                      style={cor ? { background: cor, color: corTextoLegivel(cor) } : undefined}
                      title={
                        v === null || v === undefined
                          ? `${MESES_ABREV[i]}/${linha.ano}: sem dado`
                          : `${MESES_ABREV[i]}/${linha.ano}: ${pctSinal(v)}`
                      }
                    >
                      {v === null || v === undefined ? '' : num(v * 100, 1)}
                    </td>
                  )
                })}
                <td
                  className={`num col-acumulado ${
                    linha.acumulado < 0 ? 'perda' : 'ganho'
                  }`}
                >
                  {linha.acumulado === null || linha.acumulado === undefined
                    ? '—'
                    : pctSinal(linha.acumulado)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="legenda-mini nota-unidade">Valores em % no mês.</p>
    </div>
  )
}
