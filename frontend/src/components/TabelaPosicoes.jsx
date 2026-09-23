import { brl, num, dataCurta, pct } from '../formato'

/**
 * Posições de ações da última análise: peso informado, valor nominal e o
 * retorno do ativo no período analisado.
 *
 * Não confundir com a tabela de rastreabilidade: ali o retorno é medido da
 * DATA DA COMPRA até hoje, posição por posição. Aqui é o retorno do ativo no
 * período da análise, que é o insumo do VaR. As duas convivem porque
 * respondem a perguntas diferentes, e o subtítulo de cada uma diz qual.
 */
export default function TabelaPosicoes({ dados, consolidado = false }) {
  // no consolidado o `book` vem chaveado pelo identificador interno do papel
  // ('tesouro_selic_2027-03-01'); a marcação é quem traduz para o código da
  // mesa. Ticker de ação não está no mapa e passa direto.
  const rotulo = (id) =>
    (dados.marcacao?.posicoes ?? []).find((p) => p.id === id)?.rotulo ?? id

  return (
    <div className="cartao">
      <h3>Posições da última análise</h3>
      <p className="legenda">
        {consolidado ? (
          <>
            Todas as pernas da carteira consolidada entre{' '}
            {dataCurta(dados.parametros.inicio)} e {dataCurta(dados.parametros.fim)} ·{' '}
            {dados.parametros.pregoes} datas em comum entre a bolsa e o Tesouro. Os títulos
            aparecem pelo código oficial e têm a marcação detalhada na tabela abaixo.
          </>
        ) : (
          <>
            Preços de fechamento ajustado do yfinance entre{' '}
            {dataCurta(dados.parametros.inicio)} e {dataCurta(dados.parametros.fim)} ·{' '}
            {dados.parametros.pregoes} pregões em comum. A quantidade é indicativa: valor
            nominal dividido pelo último preço, sem lote nem fracionário.
          </>
        )}
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
              <td style={{ color: '#fff', fontWeight: 500 }}>{rotulo(l.ticker)}</td>
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
            <td className="num">{pct(dados.risco_retorno?.retorno_acumulado)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
