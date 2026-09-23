import BookRendaFixa from './BookRendaFixa'
import PainelParametros from './PainelParametros'
import ParametrosRisco from './ParametrosRisco'
import { CORES } from '../formato'

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
}) {
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
    </>
  )
}
