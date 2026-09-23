import { brl, pct } from '../formato'

/** Quanto cada classe pesa na carteira consolidada. */
export default function Composicao({ composicao }) {
  return (
    <div className="cartao">
      <h3>Composição da carteira</h3>
      <p className="legenda">
        As duas pernas são ponderadas por <strong>valor de mercado</strong> — é a única base em
        que ações e títulos são comparáveis. As ações valem o total informado em parâmetros; os
        títulos valem a marcação a mercado (quantidade × PU de venda).
      </p>
      <table>
        <thead>
          <tr>
            <th>Classe</th>
            <th style={{ textAlign: 'right' }}>Valor</th>
            <th style={{ textAlign: 'right' }}>Peso</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style={{ color: '#fff', fontWeight: 500 }}>Renda variável</td>
            <td className="num destaque-suave">{brl(composicao.valor_acoes)}</td>
            <td className="num">{pct(composicao.peso_acoes, 1)}</td>
          </tr>
          <tr>
            <td style={{ color: '#fff', fontWeight: 500 }}>Renda fixa</td>
            <td className="num destaque-suave">{brl(composicao.valor_renda_fixa)}</td>
            <td className="num">{pct(composicao.peso_renda_fixa, 1)}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td>Carteira</td>
            <td className="num">{brl(composicao.valor_total)}</td>
            <td className="num">100%</td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
