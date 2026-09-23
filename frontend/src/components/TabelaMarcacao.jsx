import { brl, dataCurta, num, pct } from '../formato'

const SEVERIDADE = { erro: 'perda', aviso: 'destaque-suave' }

/**
 * Marcação a mercado explícita: PU de aquisição, PU de marcação, valor
 * marcado e P&L lado a lado, com a data-base declarada em cima. A ideia é
 * que a marcação apareça, e não fique implícita dentro do número de risco.
 */
export default function TabelaMarcacao({ marcacao, avisos = [] }) {
  const { posicoes, totais } = marcacao

  return (
    <div className="cartao">
      <h3>Marcação a mercado</h3>
      <p className="legenda">
        Marcado pelo <strong>PU de venda</strong> de{' '}
        <strong>{dataCurta(marcacao.data_base)}</strong>, último dia útil publicado pelo Tesouro
        {marcacao.defasagem_dias > 0 ? ` (D−${marcacao.defasagem_dias})` : ''} — não é o preço de
        agora. O PU de venda é quanto o Tesouro recompra o papel, ou seja, quanto a posição
        valeria se fosse liquidada hoje.
        {totais.algum_pu_estimado && (
          <>
            {' '}
            As linhas marcadas com <strong>*</strong> tiveram o PU de aquisição{' '}
            <strong>estimado</strong> pelo PU de venda da data da compra.
          </>
        )}
      </p>

      {avisos.length > 0 && (
        <ul className="avisos">
          {avisos.map((a, i) => (
            <li key={i} className={SEVERIDADE[a.severidade] || ''}>
              {a.mensagem}
            </li>
          ))}
        </ul>
      )}

      <table>
        <thead>
          <tr>
            <th>Papel</th>
            <th style={{ textAlign: 'right' }}>Qtde.</th>
            <th style={{ textAlign: 'right' }}>PU aquisição</th>
            <th style={{ textAlign: 'right' }}>PU marcação</th>
            <th style={{ textAlign: 'right' }}>Valor marcado</th>
            <th style={{ textAlign: 'right' }}>P&amp;L</th>
            <th style={{ textAlign: 'right' }}>P&amp;L %</th>
            <th style={{ textAlign: 'right' }}>Part.</th>
          </tr>
        </thead>
        <tbody>
          {posicoes.map((p) => (
            <tr key={p.id}>
              {/* o código oficial identifica o papel; o nome comercial do
                  Tesouro fica abaixo, junto do vencimento */}
              <td style={{ color: '#fff', fontWeight: 500 }}>
                {p.rotulo ?? p.tipo}
                <span className="legenda-mini" style={{ display: 'block', margin: 0 }}>
                  {p.tipo} · vence {dataCurta(p.vencimento)}
                </span>
              </td>
              <td className="num">{num(p.quantidade)}</td>
              <td className="num">
                {brl(p.pu_aquisicao, 2)}
                {p.pu_estimado && (
                  <abbr
                    title={`Estimado pelo PU de venda de ${dataCurta(p.data_pu_aquisicao)}`}
                    style={{ cursor: 'help' }}
                  >
                    *
                  </abbr>
                )}
              </td>
              <td className="num">{brl(p.pu_marcacao, 2)}</td>
              <td className="num destaque-suave">{brl(p.valor_marcado)}</td>
              <td className={`num ${p.pnl_reais < 0 ? 'perda' : 'ganho'}`}>
                {brl(p.pnl_reais)}
              </td>
              <td className={`num ${p.pnl_percentual < 0 ? 'perda' : 'ganho'}`}>
                {pct(p.pnl_percentual)}
              </td>
              <td className="num">{pct(p.peso, 1)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>Book de renda fixa</td>
            <td colSpan={3} />
            <td className="num">{brl(totais.valor_marcado)}</td>
            <td className={`num ${totais.pnl_reais < 0 ? 'perda' : 'ganho'}`}>
              {brl(totais.pnl_reais)}
            </td>
            <td className={`num ${totais.pnl_percentual < 0 ? 'perda' : 'ganho'}`}>
              {pct(totais.pnl_percentual)}
            </td>
            <td className="num">100%</td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
