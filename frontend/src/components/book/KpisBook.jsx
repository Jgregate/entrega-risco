import { CORES, brl, brlCurto, inteiro, num, pct, pctSinal } from '../../formato'
import { GradeKpis, Kpi } from '../ui'

/**
 * O topo do book: quanto tem, quanto rendeu, quanto de risco.
 *
 * Resultado financeiro e valor investido dependem de o usuário ter informado
 * preço médio ou data de entrada. Quando a cobertura é parcial, o cartão diz
 * sobre que fatia do book o número foi calculado em vez de apresentar um
 * total incompleto como se fosse o total.
 */
export default function KpisBook({ dados }) {
  const { resumo, metricas: m, janelas, periodo } = dados
  const porChave = Object.fromEntries(janelas.map((j) => [j.chave, j]))
  const cobertura = resumo.cobertura_custo

  const notaCobertura =
    cobertura !== null && cobertura !== undefined && cobertura < 0.999
      ? `sobre ${pct(cobertura, 0)} do book (falta custo de aquisição no resto)`
      : undefined

  return (
    <>
      <GradeKpis colunas={4}>
        <Kpi
          rotulo="Patrimônio líquido total"
          valor={brl(resumo.patrimonio, 2)}
          cor={CORES.vermelhoClaro}
          destaque
          nota={`${resumo.fundos} ${resumo.fundos === 1 ? 'fundo' : 'fundos'} · ${
            resumo.gestoras
          } ${resumo.gestoras === 1 ? 'gestora' : 'gestoras'}`}
        />
        <Kpi
          rotulo="Valor investido"
          valor={resumo.valor_investido === null ? '—' : brl(resumo.valor_investido, 2)}
          nota={notaCobertura || 'soma do custo de aquisição informado'}
        />
        <Kpi
          rotulo="Resultado financeiro"
          valor={resumo.resultado === null ? '—' : brl(resumo.resultado, 2)}
          cor={resumo.resultado < 0 ? CORES.vermelhoClaro : undefined}
          nota={
            resumo.resultado === null
              ? 'informe preço médio ou data de entrada'
              : notaCobertura || 'ganho ou perda não realizada'
          }
        />
        <Kpi
          rotulo={`Rentabilidade · ${periodo.rotulo}`}
          valor={pctSinal(m.retorno_acumulado)}
          nota={
            m.cdi_acumulado !== null && m.cdi_acumulado !== undefined
              ? `CDI no período: ${pctSinal(m.cdi_acumulado)}`
              : 'CDI indisponível'
          }
          titulo="Rentabilidade time-weighted: aportes e resgates não contam como valorização."
        />
      </GradeKpis>

      <GradeKpis colunas={4} compacto>
        <Kpi rotulo="No mês" valor={pctSinal(porChave['1m']?.retorno)} nota="últimos 30 dias corridos" />
        <Kpi
          rotulo="Em 12 meses"
          valor={porChave['12m']?.disponivel ? pctSinal(porChave['12m'].retorno) : '—'}
          nota={porChave['12m']?.completo === false ? 'book mais novo que 12 meses' : undefined}
        />
        <Kpi
          rotulo="Desde o início"
          valor={pctSinal(porChave.inicio?.retorno)}
          nota={`${periodo.pregoes} pregões consolidados`}
        />
        <Kpi
          rotulo="Volatilidade da carteira"
          valor={pct(m.volatilidade_anualizada, 1)}
          nota="anualizada, já considerando a correlação entre os fundos"
        />
      </GradeKpis>

      <GradeKpis colunas={4} compacto>
        <Kpi
          rotulo="Índice de Sharpe"
          valor={num(m.sharpe)}
          nota={m.sharpe === null ? 'exige 12 meses de histórico' : 'excesso sobre o CDI'}
        />
        <Kpi
          rotulo="Drawdown atual"
          valor={pct(m.drawdown_atual, 2)}
          cor={m.drawdown_atual < -0.0001 ? CORES.vermelhoClaro : undefined}
        />
        <Kpi
          rotulo="Maior drawdown"
          valor={pct(m.drawdown_maximo, 2)}
          nota={
            m.data_drawdown_maximo
              ? `em ${m.data_drawdown_maximo.split('-').reverse().join('/')}`
              : undefined
          }
        />
        <Kpi
          rotulo="Maior posição"
          valor={pct(dados.risco?.concentracao_fundo?.maior, 1)}
          nota={`${inteiro(dados.risco?.concentracao_fundo?.itens)} fundos no cálculo`}
          titulo="Peso do maior fundo no patrimônio total."
        />
      </GradeKpis>

      <p className="legenda-mini nota-unidade">
        Patrimônio calculado com a última cota publicada de cada fundo ·{' '}
        {brlCurto(resumo.patrimonio)}
      </p>
    </>
  )
}
