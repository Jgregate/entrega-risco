import BookRendaFixa from './BookRendaFixa'
import PainelParametros from './PainelParametros'
import ParametrosRisco from './ParametrosRisco'
import TabelaMarcacao from './TabelaMarcacao'
import { CORES, brl, dataCurta, num, pct } from '../formato'

/**
 * As três opções de cálculo do VaR. Cada uma bate numa rota própria e o
 * consolidado não é a média das outras duas: os dois books entram na mesma
 * matriz de preços, ponderados por valor de mercado, então a correlação
 * entre bolsa e Tesouro aparece no número.
 */
const CLASSES = [
  { id: 'acoes', texto: 'Renda Variável' },
  { id: 'renda-fixa', texto: 'Renda Fixa' },
  { id: 'ambos', texto: 'Ambos' },
]

const LEGENDA_CLASSE = {
  acoes: 'Ações da B3 e exterior, com preços do yfinance.',
  'renda-fixa': 'Títulos públicos do Tesouro Direto, marcados pelo PU de venda.',
  ambos:
    'Os dois books na mesma carteira, ponderados pelo valor de mercado de cada perna.',
}

// o que a resposta da API traz em `classe` para cada opção do seletor
const CLASSE_DOS_DADOS = { acoes: 'acoes', 'renda-fixa': 'renda-fixa', ambos: 'consolidado' }

/** Posições de ações da última análise — comportamento original, intacto. */
function TabelaAcoes({ dados, consolidado = false }) {
  return (
    <div className="cartao">
      <h3>Posições da última análise</h3>
      <p className="legenda">
        {consolidado ? (
          <>
            Todas as pernas da carteira consolidada entre{' '}
            {dataCurta(dados.parametros.inicio)} e {dataCurta(dados.parametros.fim)} ·{' '}
            {dados.parametros.pregoes} datas em comum entre a bolsa e o Tesouro. Os títulos
            aparecem pelo identificador do papel e têm a marcação detalhada na tabela abaixo.
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
            <td className="num">{pct(dados.risco_retorno?.retorno_acumulado)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

/** Quanto cada classe pesa na carteira consolidada. */
function Composicao({ composicao }) {
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

/**
 * Book: onde a carteira é montada e todos os parâmetros são manipulados.
 *
 * Uma aba só, com três opções de cálculo. Trocar a opção troca o que se monta
 * e sobre o que a análise roda — os parâmetros de risco são os mesmos, que é
 * o que torna a comparação entre as três honesta.
 */
export default function AbaBook({
  params,
  setParams,
  classe,
  setClasse,
  onCalcular,
  carregando,
  dados,
}) {
  // a tabela de resultado só vale se a última análise foi da classe selecionada
  const classeDosDados = dados?.classe ?? 'acoes'
  const mostrarResultado = dados && classeDosDados === CLASSE_DOS_DADOS[classe]

  const acoesValidas =
    params.posicoes.length > 0 &&
    params.posicoes.every((p) => p.ticker.trim() !== '' && Number(p.peso) > 0)
  const validoAmbos = acoesValidas && params.rendaFixa.length > 0 && params.inicio < params.fim

  return (
    <>
      <div className="barra-janela">
        <div>
          <span className="rotulo" style={{ margin: 0 }}>
            Cálculo do VaR
          </span>
          <p className="legenda-mini" style={{ margin: '5px 0 0' }}>
            {LEGENDA_CLASSE[classe]} A análise roda sobre o book da opção selecionada.
          </p>
        </div>
        <div className="segmentado" style={{ margin: 0 }}>
          {CLASSES.map((c) => (
            <button
              key={c.id}
              className={`chip${classe === c.id ? ' ativo' : ''}`}
              onClick={() => setClasse(c.id)}
              style={
                classe === c.id
                  ? { borderColor: CORES.vermelhoClaro, color: CORES.vermelhoClaro }
                  : undefined
              }
            >
              {c.texto}
            </button>
          ))}
        </div>
      </div>

      {classe === 'acoes' && (
        <PainelParametros
          params={params}
          setParams={setParams}
          onCalcular={onCalcular}
          carregando={carregando}
        />
      )}

      {classe === 'renda-fixa' && (
        <BookRendaFixa
          params={params}
          setParams={setParams}
          onCalcular={onCalcular}
          carregando={carregando}
        />
      )}

      {/* os dois books lado a lado de um único painel de parâmetros: a análise
          consolidada usa os mesmos números para as duas pernas */}
      {classe === 'ambos' && (
        <div className="book">
          <div style={{ display: 'grid', gap: 20 }}>
            <PainelParametros
              params={params}
              setParams={setParams}
              onCalcular={onCalcular}
              carregando={carregando}
              mostrarParametros={false}
            />
            <BookRendaFixa
              params={params}
              setParams={setParams}
              onCalcular={onCalcular}
              carregando={carregando}
              mostrarParametros={false}
            />
          </div>
          <ParametrosRisco
            params={params}
            setParams={setParams}
            onCalcular={onCalcular}
            carregando={carregando}
            valido={validoAmbos}
            aviso="O valor da carteira acima é o da perna de ações; a de renda fixa vale a marcação a mercado. Os pesos entre as duas saem desses valores."
          />
        </div>
      )}

      {mostrarResultado && classe === 'acoes' && <TabelaAcoes dados={dados} />}
      {mostrarResultado && classe === 'renda-fixa' && (
        <TabelaMarcacao marcacao={dados.marcacao} avisos={dados.avisos} />
      )}
      {mostrarResultado && classe === 'ambos' && (
        <>
          <Composicao composicao={dados.composicao} />
          <TabelaAcoes dados={dados} consolidado />
          <TabelaMarcacao marcacao={dados.marcacao} avisos={dados.avisos} />
        </>
      )}
    </>
  )
}
