import { useEffect } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { brl, corCategoria, dataCurta, num, pct, pctSinal } from '../../formato'
import {
  CURSOR_LINHA, Dica, MARGEM, PROPS_EIXO_X, PROPS_EIXO_Y, PROPS_GRADE, PROPS_LEGENDA,
  tickPercentual,
} from '../grafico'
import { Amostra, Vazio } from '../ui'

/**
 * Comparação lado a lado dos fundos marcados na tabela do book.
 *
 * Um modal, não uma página: a comparação é um gesto dentro da leitura do book
 * e o usuário volta para onde estava. As curvas são indexadas a zero no mesmo
 * dia inicial — sem isso, comparar cota de R$ 1,20 com cota de R$ 380 não
 * diria nada.
 */
const LINHAS = [
  { rotulo: 'Patrimônio no book', chave: 'valor_atual', formato: (v) => brl(v, 2) },
  { rotulo: '% do book', chave: 'percentual', formato: (v) => pct(v, 1) },
  { rotulo: 'Rentabilidade da posição', chave: 'rentabilidade', formato: (v) => pctSinal(v), sinal: true },
  { rotulo: 'Resultado financeiro', chave: 'resultado', formato: (v) => brl(v, 2), sinal: true },
  { rotulo: 'Retorno no período', caminho: ['metricas', 'retorno_acumulado'], formato: (v) => pctSinal(v), sinal: true },
  { rotulo: 'Volatilidade anualizada', caminho: ['metricas', 'volatilidade_anualizada'], formato: (v) => pct(v, 2) },
  { rotulo: 'Volatilidade 12M', caminho: ['metricas', 'volatilidade_12m'], formato: (v) => pct(v, 2) },
  { rotulo: 'Índice de Sharpe', caminho: ['metricas', 'sharpe'], formato: (v) => num(v) },
  { rotulo: 'Drawdown máximo', caminho: ['metricas', 'drawdown_maximo'], formato: (v) => pct(v, 2) },
  { rotulo: 'Drawdown atual', caminho: ['metricas', 'drawdown_atual'], formato: (v) => pct(v, 2) },
  { rotulo: 'Classe', chave: 'classe' },
  { rotulo: 'Gestora', chave: 'gestora' },
  { rotulo: 'Benchmark (CVM)', chave: 'benchmark' },
  { rotulo: 'Liquidez', chave: 'liquidez_dias', formato: (v) => `D+${v}` },
  { rotulo: 'Taxa de administração', chave: 'taxa_administracao', formato: (v) => `${num(v, 2)}% a.a.` },
  { rotulo: 'Taxa de performance', chave: 'taxa_performance', formato: (v) => `${num(v, 2)}%` },
]

function valorDe(fundo, linha) {
  if (linha.caminho) return linha.caminho.reduce((o, k) => o?.[k], fundo)
  return fundo[linha.chave]
}

export default function Comparador({ fundos, serieFundos, onFechar }) {
  useEffect(() => {
    const aoTeclar = (e) => e.key === 'Escape' && onFechar()
    window.addEventListener('keydown', aoTeclar)
    const anterior = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', aoTeclar)
      document.body.style.overflow = anterior
    }
  }, [onFechar])

  const temSerie = Array.isArray(serieFundos) && serieFundos.length > 1

  return (
    <div className="lightbox" role="dialog" aria-modal="true" aria-label="Comparação de fundos" onClick={onFechar}>
      <div className="lightbox-caixa comparador" onClick={(e) => e.stopPropagation()}>
        <div className="lightbox-topo">
          <div>
            <h4>Comparar fundos do book</h4>
            <p className="legenda-mini">
              {fundos.length} fundos selecionados. Todos os indicadores são do período de
              análise selecionado no book.
            </p>
          </div>
          <button className="btn-fechar" onClick={onFechar} aria-label="Fechar">
            ✕
          </button>
        </div>

        <div className="comparador-corpo">
          <div className="rolagem-horizontal">
            <table className="tabela-comparacao">
              <thead>
                <tr>
                  <th scope="col">Indicador</th>
                  {fundos.map((f, i) => (
                    <th key={f.cnpj} scope="col" className="col-num">
                      <Amostra cor={corCategoria(i)} />
                      <span className="comparador-nome" title={f.nome}>
                        {f.nome || f.cnpj}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {LINHAS.map((linha) => (
                  <tr key={linha.rotulo}>
                    <th scope="row">{linha.rotulo}</th>
                    {fundos.map((f) => {
                      const v = valorDe(f, linha)
                      const vazio = v === null || v === undefined || v === ''
                      return (
                        <td
                          key={f.cnpj}
                          className={[
                            'num',
                            vazio ? 'dado-ausente' : '',
                            linha.sinal && v < 0 ? 'perda' : '',
                            linha.sinal && v > 0 ? 'ganho' : '',
                          ].filter(Boolean).join(' ')}
                        >
                          {vazio ? '—' : linha.formato ? linha.formato(v) : v}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {temSerie ? (
            <div className="comparador-grafico">
              <h4>Rentabilidade acumulada</h4>
              <p className="legenda-mini">
                Cada fundo indexado a zero no início do período, no mesmo eixo — é o que
                torna comparável um fundo de cota R$ 1,20 com outro de cota R$ 380. A linha
                branca é o book consolidado, para referência.
              </p>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={serieFundos} margin={MARGEM}>
                  <CartesianGrid {...PROPS_GRADE} />
                  <XAxis dataKey="data" {...PROPS_EIXO_X} tickFormatter={dataCurta} />
                  <YAxis {...PROPS_EIXO_Y} width={56} tickFormatter={tickPercentual(0)} />
                  <ReferenceLine y={0} stroke="rgba(255,255,255,0.18)" />
                  <Tooltip
                    content={<Dica formatar={(v) => pctSinal(v)} rotularData={dataCurta} />}
                    cursor={CURSOR_LINHA}
                  />
                  <Legend {...PROPS_LEGENDA} />
                  {fundos.map((f, i) => (
                    <Line
                      key={f.cnpj}
                      type="monotone"
                      dataKey={f.cnpj}
                      name={f.nome || f.cnpj}
                      stroke={corCategoria(i)}
                      strokeWidth={2}
                      dot={false}
                      isAnimationActive={false}
                    />
                  ))}
                  <Line
                    type="monotone" dataKey="fundo" name="Book consolidado"
                    stroke="rgba(255,255,255,0.55)" strokeWidth={1.2} strokeDasharray="4 3"
                    dot={false} isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <Vazio>Sem série consolidada para exibir no período.</Vazio>
          )}
        </div>

        <p className="lightbox-dica">Clique fora ou pressione Esc para fechar.</p>
      </div>
    </div>
  )
}
