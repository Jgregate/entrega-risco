import { useEffect, useState } from 'react'
import { analiseFundo, atualizarFundos, buscarFundos, statusFundos, top10Fundos } from '../api'
import { CORES, num, pct } from '../formato'
import CartaoGrafico from './CartaoGrafico'
import GraficoComparativoIndices from './GraficoComparativoIndices'
import GraficoCrescimentoFundo from './GraficoCrescimentoFundo'
import GraficoHeatmapMensal from './GraficoHeatmapMensal'
import GraficoRetornoPorJanela from './GraficoRetornoPorJanela'
import GraficoSharpeSortinoPorJanela from './GraficoSharpeSortinoPorJanela'
import { Kpi } from './Kpis'

const JANELAS_MESES = [
  { meses: 6, texto: '6 meses' },
  { meses: 12, texto: '1 ano' },
  { meses: 24, texto: '2 anos' },
  { meses: 36, texto: '3 anos' },
]

/**
 * Aba Fundos: busca/ranking de fundos ativos na CVM (equivalente à sidebar
 * do sistema FUNDOS original) + análise do fundo escolhido. Estado próprio,
 * não depende da carteira de ações montada na aba Book.
 */
export default function AbaFundos() {
  const [modo, setModo] = useState('busca')

  const [query, setQuery] = useState('')
  const [resultadosBusca, setResultadosBusca] = useState(null)
  const [buscando, setBuscando] = useState(false)

  const [anosRanking, setAnosRanking] = useState(1)
  const [top10, setTop10] = useState(null)
  const [carregandoTop10, setCarregandoTop10] = useState(false)

  const [fundo, setFundo] = useState(null) // { cnpj, nome }
  const [meses, setMeses] = useState(24)
  const [dados, setDados] = useState(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState(null)

  const [status, setStatus] = useState(null)
  const [atualizando, setAtualizando] = useState(false)

  useEffect(() => {
    statusFundos().then(setStatus).catch(() => setStatus(null))
  }, [])

  useEffect(() => {
    if (modo !== 'top10') return
    setCarregandoTop10(true)
    top10Fundos(anosRanking)
      .then(setTop10)
      .catch((e) => setErro(e.message))
      .finally(() => setCarregandoTop10(false))
  }, [modo, anosRanking])

  useEffect(() => {
    if (!fundo) return
    setCarregando(true)
    setErro(null)
    analiseFundo(fundo.cnpj, meses)
      .then(setDados)
      .catch((e) => {
        setErro(e.message)
        setDados(null)
      })
      .finally(() => setCarregando(false))
  }, [fundo, meses])

  const buscar = (e) => {
    e.preventDefault()
    if (query.trim().length < 2) return
    setBuscando(true)
    setErro(null)
    buscarFundos(query)
      .then(setResultadosBusca)
      .catch((e2) => setErro(e2.message))
      .finally(() => setBuscando(false))
  }

  const escolher = (cnpj, nome) => setFundo({ cnpj, nome })

  const atualizar = () => {
    setAtualizando(true)
    atualizarFundos()
      .then(() => statusFundos())
      .then(setStatus)
      .then(() => {
        if (fundo) setFundo({ ...fundo }) // reforça o efeito de análise sem duplicar lógica
      })
      .catch((e) => setErro(e.message))
      .finally(() => setAtualizando(false))
  }

  return (
    <>
      <div className="cartao">
        <h3>Escolha o fundo</h3>
        <p className="legenda">
          Fundos ativos e registrados na CVM (dados.cvm.gov.br), restritos aos que reportaram cota
          nos dois últimos meses fechados.
        </p>

        <div className="segmentado">
          <button
            className={`chip${modo === 'busca' ? ' ativo' : ''}`}
            onClick={() => setModo('busca')}
          >
            Buscar por nome
          </button>
          <button
            className={`chip${modo === 'top10' ? ' ativo' : ''}`}
            onClick={() => setModo('top10')}
          >
            Top 10 por retorno
          </button>
        </div>

        {modo === 'busca' ? (
          <>
            <form onSubmit={buscar} className="dupla" style={{ gridTemplateColumns: '1fr auto' }}>
              <input
                value={query}
                placeholder="ex.: TREND NASDAQ 100"
                onChange={(e) => setQuery(e.target.value)}
              />
              <button className="btn-principal" style={{ width: 'auto', margin: 0 }} disabled={buscando}>
                {buscando ? <span className="carregando" /> : 'Buscar'}
              </button>
            </form>

            {resultadosBusca && resultadosBusca.length === 0 && (
              <p className="aviso-pesos">Nenhum fundo ativo encontrado com esse nome.</p>
            )}

            {resultadosBusca && resultadosBusca.length > 0 && (
              <table style={{ marginTop: 14 }}>
                <tbody>
                  {resultadosBusca.map((f) => (
                    <tr key={f.cnpj} onClick={() => escolher(f.cnpj, f.nome)} style={{ cursor: 'pointer' }}>
                      <td style={fundo?.cnpj === f.cnpj ? { color: CORES.vermelhoClaro, fontWeight: 500 } : undefined}>
                        {f.nome}
                      </td>
                      <td className="num" style={{ color: 'var(--texto-fraco)' }}>
                        {f.cnpj}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        ) : (
          <>
            <div className="segmentado">
              {[1, 2, 3].map((a) => (
                <button
                  key={a}
                  className={`chip${anosRanking === a ? ' ativo' : ''}`}
                  onClick={() => setAnosRanking(a)}
                >
                  {a} ano{a > 1 ? 's' : ''}
                </button>
              ))}
            </div>

            {carregandoTop10 && <p className="aviso-pesos">Calculando ranking…</p>}

            {top10 && top10.length === 0 && !carregandoTop10 && (
              <p className="aviso-pesos">Não foi possível montar o ranking para essa janela.</p>
            )}

            {top10 && top10.length > 0 && (
              <table style={{ marginTop: 8 }}>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Fundo</th>
                    <th style={{ textAlign: 'right' }}>Retorno</th>
                    <th style={{ textAlign: 'right' }}>Patrimônio (R$ mi)</th>
                    <th style={{ textAlign: 'right' }}>Cotistas</th>
                  </tr>
                </thead>
                <tbody>
                  {top10.map((f, i) => (
                    <tr key={f.cnpj} onClick={() => escolher(f.cnpj, f.nome)} style={{ cursor: 'pointer' }}>
                      <td>{i + 1}</td>
                      <td style={fundo?.cnpj === f.cnpj ? { color: CORES.vermelhoClaro, fontWeight: 500 } : undefined}>
                        {f.nome}
                      </td>
                      <td className="num">{pct(f['retorno_%'] / 100, 1)}</td>
                      <td className="num">{num(f.patrimonio_mi, 1)}</td>
                      <td className="num">{num(f.cotistas, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="aviso-pesos">
              Entre fundos com pelo menos 100 cotistas (exclui exclusivos/institucionais) e sem
              saltos mensais suspeitos (proxy de desdobramento/erro de reporte, não performance
              real).
            </p>
          </>
        )}

        <div className="separador" />
        <p className="aviso-pesos">
          {status?.ultima_atualizacao
            ? `Dados do mês mais recente baixados em: ${status.ultima_atualizacao}`
            : 'Ainda sem dados do mês mais recente em cache.'}{' '}
          <button className="btn-texto" style={{ width: 'auto', display: 'inline-block', padding: '2px 10px' }} onClick={atualizar} disabled={atualizando}>
            {atualizando ? 'atualizando…' : '🔄 atualizar dados agora'}
          </button>
        </p>
      </div>

      {erro && <div className="erro">{erro}</div>}

      {!fundo && !erro && (
        <div className="vazio">
          Busque um fundo pelo nome ou veja o Top 10 para escolher um.
        </div>
      )}

      {fundo && (
        <>
          <div className="titulo-secao">
            <h3>{fundo.nome}</h3>
            <p className="legenda">CNPJ {fundo.cnpj}</p>
          </div>

          {carregando && <p className="aviso-pesos">Carregando análise…</p>}

          {dados && (
            <>
              <div className="segmentado" style={{ marginBottom: 16 }}>
                {JANELAS_MESES.map((j) => (
                  <button
                    key={j.meses}
                    className={`chip${meses === j.meses ? ' ativo' : ''}`}
                    onClick={() => setMeses(j.meses)}
                  >
                    {j.texto}
                  </button>
                ))}
              </div>

              <div className="kpis">
                <Kpi
                  rotulo={`Retorno acumulado (${dados.resumo.janela_meses}m)`}
                  valor={pct(dados.resumo['retorno_acumulado_%'] / 100, 1)}
                  cor={CORES.vermelhoClaro}
                  destaque
                  nota={`CDI no período: ${pct(dados.resumo['retorno_cdi_%'] / 100, 1)}`}
                />
                <Kpi
                  rotulo="Volatilidade anualizada"
                  valor={pct(dados.resumo['volatilidade_anualizada_%'] / 100, 1)}
                />
                <Kpi
                  rotulo="Sharpe · Sortino"
                  valor={`${num(dados.resumo.sharpe)} · ${num(dados.resumo.sortino)}`}
                  nota="excesso sobre o CDI"
                />
              </div>

              {dados.meses_disponiveis < meses && (
                <p className="aviso-pesos">
                  Esse fundo só tem {dados.meses_disponiveis} mês(es) fechado(s) de histórico
                  disponível — usando todos.
                </p>
              )}

              <div className="duo">
                <GraficoCrescimentoFundo dados={dados} />
                <GraficoHeatmapMensal dados={dados} />
              </div>

              {dados.comparativo_disponivel ? (
                <GraficoComparativoIndices dados={dados} />
              ) : (
                <div className="vazio">
                  Aumente a janela para pelo menos 12 meses para ver o comparativo com Ibovespa.
                </div>
              )}

              <div className="duo">
                <GraficoRetornoPorJanela dados={dados} />
                <GraficoSharpeSortinoPorJanela dados={dados} />
              </div>

              <CartaoGrafico titulo="Retornos mensais">
                {() => (
                  <table>
                    <thead>
                      <tr>
                        <th>Mês</th>
                        <th style={{ textAlign: 'right' }}>Fundo</th>
                        <th style={{ textAlign: 'right' }}>CDI</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dados.serie_mensal.map((p) => (
                        <tr key={`${p.ano}-${p.mes}`}>
                          <td>
                            {String(p.mes).padStart(2, '0')}/{p.ano}
                          </td>
                          <td className={`num ${p['fundo_%'] < 0 ? 'perda' : 'ganho'}`}>
                            {pct(p['fundo_%'] / 100, 2)}
                          </td>
                          <td className="num">{pct(p['cdi_%'] / 100, 2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </CartaoGrafico>
            </>
          )}
        </>
      )}
    </>
  )
}
