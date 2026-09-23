import { CORES, brl, inteiro, pct } from '../../formato'
import { GradeKpis, Kpi, Ressalva, Tag, Vazio } from '../ui'

/**
 * IR estimado sobre o ganho não realizado do book.
 *
 * É estimativa, e a tela não deixa isso subentendido: a alíquota vem da
 * tabela regressiva legal aplicada ao prazo desde a data de entrada que o
 * usuário informou. O que o sistema NÃO sabe — come-cotas já recolhido,
 * prejuízo a compensar, custo real de aquisição quando não há preço médio —
 * está escrito, e a posição sem dado suficiente fica fora do total em vez de
 * entrar com um número inventado.
 */
export default function Tributacao({ dados }) {
  const t = dados.tributacao || {}

  if (!t.fundos_estimados) {
    return (
      <Vazio motivo="A estimativa precisa da data de entrada e do custo de aquisição (preço médio ou valor investido na data) de cada posição.">
        Sem dados suficientes para estimar o IR do book.
      </Vazio>
    )
  }

  const parcial = (t.cobertura ?? 1) < 0.999

  return (
    <>
      <GradeKpis colunas={4} compacto>
        <Kpi rotulo="Saldo bruto" valor={brl(t.saldo_bruto, 2)} nota="patrimônio a preço de mercado" />
        <Kpi
          rotulo="IR estimado"
          valor={brl(t.ir_estimado, 2)}
          cor={CORES.vermelhoClaro}
          nota={parcial ? `sobre ${pct(t.cobertura, 0)} do book` : 'sobre o ganho não realizado'}
        />
        <Kpi
          rotulo="Saldo líquido estimado"
          valor={brl(t.saldo_liquido_estimado, 2)}
          nota="se você resgatasse tudo hoje"
        />
        <Kpi rotulo="Impacto tributário" valor={pct(t.impacto, 2)} nota="do patrimônio total" />
      </GradeKpis>

      <div className="cartao">
        <div className="cartao-cabecalho">
          <div>
            <h4>Estimativa por posição</h4>
            <p className="legenda-mini">
              Alíquota pela tabela regressiva do tipo de fundo e pelo prazo desde a entrada.
            </p>
          </div>
          <Tag cor={CORES.vermelhoClaro}>Estimativa</Tag>
        </div>

        <table>
          <thead>
            <tr>
              <th scope="col">Fundo</th>
              <th scope="col">Classe</th>
              <th scope="col" className="col-num">Dias aplicado</th>
              <th scope="col" className="col-num">Alíquota</th>
              <th scope="col" className="col-num">Ganho</th>
              <th scope="col" className="col-num">IR estimado</th>
            </tr>
          </thead>
          <tbody>
            {(t.por_fundo || []).map((f) => {
              const fundo = dados.fundos.find((x) => x.cnpj === f.cnpj)
              const semEstimativa = f.ir_estimado === null || f.ir_estimado === undefined
              return (
                <tr key={f.cnpj} className={semEstimativa ? 'linha-ausente' : undefined}>
                  <td>{fundo?.nome || f.cnpj}</td>
                  <td>{fundo?.classe || '—'}</td>
                  <td className="num">{f.dias_aplicado ? inteiro(f.dias_aplicado) : '—'}</td>
                  <td className="num">{f.aliquota === null || f.aliquota === undefined ? '—' : pct(f.aliquota, 1)}</td>
                  <td className={`num ${f.ganho < 0 ? 'perda' : 'ganho'}`}>
                    {f.ganho === null || f.ganho === undefined ? '—' : brl(f.ganho, 2)}
                  </td>
                  <td className="num destaque-suave">
                    {semEstimativa ? '—' : brl(f.ir_estimado, 2)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {t.fundos_sem_estimativa > 0 && (
          <Ressalva>
            {t.fundos_sem_estimativa}{' '}
            {t.fundos_sem_estimativa === 1 ? 'posição ficou' : 'posições ficaram'} sem
            estimativa — falta data de entrada, custo de aquisição, ou o regime tributário
            depende de escolha do cotista (caso dos fundos de previdência).
          </Ressalva>
        )}
      </div>

      <Ressalva>{t.observacao}</Ressalva>
      <Ressalva>
        Come-cotas não é projetado: fundos de renda fixa e multimercado abertos antecipam IR
        em maio e novembro, o que reduz o imposto devido no resgate mas também reduz o saldo
        aplicado ao longo do caminho. Esta tela não substitui o informe de rendimentos do
        administrador.
      </Ressalva>
    </>
  )
}
