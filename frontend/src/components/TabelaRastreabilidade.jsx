import { brl, dataCurta, haQuantoTempo, num, pct } from '../formato'

const ROTULO_CLASSE = { acoes: 'Ação', 'renda-fixa': 'Título' }

/**
 * Uma linha por posição, da compra até a projeção.
 *
 * A ordem das colunas é a ordem da pergunta que a tabela responde: o que eu
 * tenho, desde quando, por quanto comprei, quanto vale hoje, quanto
 * valorizou, e para onde a série aponta. Ler da esquerda para a direita é
 * percorrer a vida da posição.
 *
 * Serve às três classes sem ramificação: em ações a coluna de preço é o
 * fechamento ajustado, em renda fixa é o PU de venda. A tabela não precisa
 * saber a diferença — o backend já entrega os dois no mesmo contrato.
 */
export default function TabelaRastreabilidade({ rastreabilidade, mostrarClasse = false }) {
  const { posicoes, totais } = rastreabilidade

  return (
    <div className="cartao">
      <h3>Rastreabilidade das posições</h3>
      <p className="legenda">
        De quando cada posição foi comprada até o preço de{' '}
        <strong>{dataCurta(rastreabilidade.data_referencia)}</strong>. A{' '}
        <strong>valorização</strong> é o preço de hoje contra o preço pago; o{' '}
        <strong>anualizado</strong> só aparece com posse de pelo menos 21 pregões, porque
        anualizar uma semana de posse informaria menos do que o número sugere.
        {totais.algum_preco_estimado && (
          <>
            {' '}
            As linhas com <strong>*</strong> tiveram o preço de compra <strong>estimado</strong>{' '}
            pelo fechamento da data da compra, por não ter sido informado.
          </>
        )}
      </p>

      <table>
        <thead>
          <tr>
            <th>Posição</th>
            {mostrarClasse && <th style={{ width: 74 }}>Classe</th>}
            <th>Comprada</th>
            <th style={{ textAlign: 'right' }}>Preço pago</th>
            <th style={{ textAlign: 'right' }}>Preço hoje</th>
            <th style={{ textAlign: 'right' }}>Valor hoje</th>
            <th style={{ textAlign: 'right' }}>Valorização</th>
            <th style={{ textAlign: 'right' }}>%</th>
            <th style={{ textAlign: 'right' }}>a.a.</th>
            <th style={{ textAlign: 'right' }}>Do pico</th>
            <th style={{ textAlign: 'right' }}>Projeção</th>
          </tr>
        </thead>
        <tbody>
          {posicoes.map((p) => {
            const proj = p.projecao?.disponivel ? p.projecao : null
            return (
              <tr key={p.id}>
                <td style={{ color: '#fff', fontWeight: 500 }}>
                  {p.rotulo}
                  {p.detalhe?.vencimento && (
                    <span className="legenda-mini" style={{ display: 'block', margin: 0 }}>
                      vence {dataCurta(p.detalhe.vencimento)}
                    </span>
                  )}
                </td>
                {mostrarClasse && (
                  <td className="legenda-mini">{ROTULO_CLASSE[p.classe] || p.classe}</td>
                )}
                <td>
                  {dataCurta(p.data_compra)}
                  <span className="legenda-mini" style={{ display: 'block', margin: 0 }}>
                    {haQuantoTempo(p.dias_corridos)} · {p.pregoes} pregões
                  </span>
                </td>
                <td className="num">
                  {brl(p.preco_compra, 2)}
                  {p.preco_compra_estimado && (
                    <abbr
                      title={`Estimado pelo fechamento de ${dataCurta(p.data_compra)}`}
                      style={{ cursor: 'help' }}
                    >
                      *
                    </abbr>
                  )}
                </td>
                <td className="num">{brl(p.preco_atual, 2)}</td>
                <td className="num destaque-suave">{brl(p.valor_atual)}</td>
                <td className={`num ${p.valorizacao_reais < 0 ? 'perda' : 'ganho'}`}>
                  {brl(p.valorizacao_reais)}
                </td>
                <td className={`num ${p.valorizacao_percentual < 0 ? 'perda' : 'ganho'}`}>
                  {pct(p.valorizacao_percentual)}
                </td>
                <td className="num">{pct(p.retorno_anualizado, 1)}</td>
                <td className="num">{pct(p.queda_desde_o_pico, 1)}</td>
                <td className="num">
                  {proj ? brl(proj.valor_esperado) : '—'}
                  {proj && (
                    <span className="legenda-mini" style={{ display: 'block', margin: 0 }}>
                      piso {brl(proj.metodos.empirico.piso)}
                    </span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={mostrarClasse ? 3 : 2}>
              Book · {totais.posicoes} posições
              <span className="legenda-mini" style={{ display: 'block', margin: 0 }}>
                {totais.ganhadoras} no azul · {totais.perdedoras} no vermelho
              </span>
            </td>
            <td className="num">{brl(totais.valor_compra)}</td>
            <td />
            <td className="num">{brl(totais.valor_atual)}</td>
            <td className={`num ${totais.valorizacao_reais < 0 ? 'perda' : 'ganho'}`}>
              {brl(totais.valorizacao_reais)}
            </td>
            <td className={`num ${totais.valorizacao_percentual < 0 ? 'perda' : 'ganho'}`}>
              {pct(totais.valorizacao_percentual)}
            </td>
            <td className="num">{pct(totais.retorno_anualizado, 1)}</td>
            <td colSpan={2} className="num">
              {num(totais.pregoes, 0)} pregões
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
