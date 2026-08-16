import PainelParametros from './PainelParametros'
import { brl, dataCurta, num, pct } from '../formato'

/** Book: onde a carteira é montada e todos os parâmetros são manipulados. */
export default function AbaBook({ params, setParams, onCalcular, carregando, dados }) {
  return (
    <>
      <PainelParametros
        params={params}
        setParams={setParams}
        onCalcular={onCalcular}
        carregando={carregando}
      />

      {dados && (
        <div className="cartao">
          <h3>Posições da última análise</h3>
          <p className="legenda">
            Preços de fechamento ajustado do yfinance entre {dataCurta(dados.parametros.inicio)} e{' '}
            {dataCurta(dados.parametros.fim)} · {dados.parametros.pregoes} pregões em comum. A
            quantidade é indicativa: valor nominal dividido pelo último preço, sem lote nem
            fracionário.
          </p>
          <table>
            <thead>
              <tr>
                <th>Ativo</th>
                <th style={{ textAlign: 'right' }}>Peso</th>
                <th style={{ textAlign: 'right' }}>Valor nominal</th>
                <th style={{ textAlign: 'right' }}>Preço inicial</th>
                <th style={{ textAlign: 'right' }}>Preço final</th>
                <th style={{ textAlign: 'right' }}>Qtde. aprox.</th>
                <th style={{ textAlign: 'right' }}>Retorno no período</th>
              </tr>
            </thead>
            <tbody>
              {dados.book.map((l) => (
                <tr key={l.ticker}>
                  <td style={{ color: '#fff', fontWeight: 500 }}>{l.ticker}</td>
                  <td className="num">{pct(l.peso, 1)}</td>
                  <td className="num destaque-suave">{brl(l.valor_nominal)}</td>
                  <td className="num">{num(l.preco_inicial)}</td>
                  <td className="num">{num(l.preco_final)}</td>
                  <td className="num">{num(l.quantidade, 0)}</td>
                  <td className={`num ${l.retorno_periodo < 0 ? 'perda' : 'ganho'}`}>
                    {pct(l.retorno_periodo)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td>Carteira</td>
                <td className="num">100%</td>
                <td className="num">{brl(dados.parametros.valor_carteira)}</td>
                <td colSpan={3} />
                <td className="num">
                  {pct(dados.risco_retorno?.retorno_acumulado)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </>
  )
}
