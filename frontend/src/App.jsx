import { useState } from 'react'
import { analisar } from './api'
import logo from './assets/logo.png'
import AbaBook from './components/AbaBook'
import AbaFundos from './components/AbaFundos'
import AbaRiscoRetorno from './components/AbaRiscoRetorno'
import GraficoComparacaoVaR from './components/GraficoComparacaoVaR'
import GraficoDistribuicao from './components/GraficoDistribuicao'
import GraficoEvolucao from './components/GraficoEvolucao'
import Kpis from './components/Kpis'
import SeletorJanela from './components/SeletorJanela'
import { Aderencia, ViolacoesPorAno } from './components/Violacoes'
import { dataCurta, rotuloConfianca } from './formato'
import { dataDeCorte } from './janela'

const hoje = new Date()
const iso = (d) => d.toISOString().slice(0, 10)
const anosAtras = (n) => {
  const d = new Date(hoje)
  d.setFullYear(d.getFullYear() - n)
  return d
}

const PADRAO = {
  posicoes: [
    { ticker: 'PETR4.SA', peso: 40 },
    { ticker: 'VALE3.SA', peso: 35 },
    { ticker: 'ITUB4.SA', peso: 25 },
  ],
  inicio: iso(anosAtras(5)),
  fim: iso(hoje),
  confianca: 0.95,
  horizonte: 1,
  janela: 252,
  valor_carteira: 100000,
}

const ABAS = [
  { id: 'vars', titulo: 'VaRs', sub: 'empírico · paramétrico · EWMA' },
  { id: 'risco', titulo: 'Risco e retorno', sub: 'Sharpe · Sortino' },
  { id: 'book', titulo: 'Book', sub: 'carteira e parâmetros' },
  { id: 'fundos', titulo: 'Fundos', sub: 'CVM · fundos de investimento' },
]

export default function App() {
  const [params, setParams] = useState(PADRAO)
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(false)
  const [aba, setAba] = useState('book')
  // janela de visualização da aba de VaRs (null = histórico completo)
  const [janelaAnos, setJanelaAnos] = useState(null)

  const calcular = async () => {
    setCarregando(true)
    setErro(null)
    try {
      const resposta = await analisar({
        posicoes: params.posicoes.map((p) => ({
          ticker: p.ticker.trim().toUpperCase(),
          peso: Number(p.peso),
        })),
        inicio: params.inicio,
        fim: params.fim,
        confianca: params.confianca,
        horizonte: Number(params.horizonte),
        janela: Number(params.janela),
        valor_carteira: Number(params.valor_carteira),
      })
      setDados(resposta)
      setJanelaAnos(null)
      setAba('vars')
    } catch (e) {
      setErro(e.message)
      setDados(null)
    } finally {
      setCarregando(false)
    }
  }

  const fim = dados?.parametros?.fim
  const corte = dataDeCorte(fim, janelaAnos)
  const anosDisponiveis = dados
    ? Math.max(
        1,
        Math.floor(
          (new Date(fim) - new Date(dados.parametros.inicio)) / (365.25 * 24 * 3600 * 1000)
        )
      )
    : 0

  const semDados = (
    <div className="vazio">
      Nenhuma análise rodada ainda.
      <br />
      Monte a carteira na aba <strong>Book</strong> e clique em <strong>Rodar análise</strong>.
    </div>
  )

  return (
    <div className="app">
      <header className="topo">
        <div className="marca">
          <img className="selo" src={logo} alt="Inteli Finance" />
          <div>
            <div className="olho">Inteli Finance · Célula de Risco</div>
            <h1>Painel de risco de carteira</h1>
          </div>
        </div>
        {dados && (
          <p className="subtitulo">
            {Object.keys(dados.parametros.pesos).join(' · ')}
            <br />
            {rotuloConfianca(dados.parametros.confianca)} · {dados.parametros.horizonte_dias}d ·
            janela {dados.parametros.janela_backtest} · {dataCurta(dados.parametros.inicio)} a{' '}
            {dataCurta(dados.parametros.fim)}
          </p>
        )}
      </header>

      <nav className="abas">
        {ABAS.map((a) => (
          <button
            key={a.id}
            className={`aba${aba === a.id ? ' ativa' : ''}`}
            onClick={() => setAba(a.id)}
          >
            <span className="aba-titulo">{a.titulo}</span>
            <span className="aba-sub">{a.sub}</span>
          </button>
        ))}
      </nav>

      <main>
        {erro && <div className="erro">{erro}</div>}

        {aba === 'book' && (
          <AbaBook
            params={params}
            setParams={setParams}
            onCalcular={calcular}
            carregando={carregando}
            dados={dados}
          />
        )}

        {aba === 'vars' &&
          (dados ? (
            <>
              <Kpis dados={dados} />
              <SeletorJanela
                valor={janelaAnos}
                onMudar={setJanelaAnos}
                disponiveis={anosDisponiveis}
                corte={corte}
                fim={fim}
              />
              <GraficoComparacaoVaR dados={dados} corte={corte} />
              <GraficoDistribuicao dados={dados} corte={corte} />
              <ViolacoesPorAno dados={dados} corte={corte} />
              <Aderencia dados={dados} />
              <GraficoEvolucao dados={dados} corte={corte} />
            </>
          ) : (
            semDados
          ))}

        {aba === 'risco' && (dados ? <AbaRiscoRetorno dados={dados} /> : semDados)}

        {aba === 'fundos' && <AbaFundos />}
      </main>

      {dados && (
        <div className="rodape">
          <span>
            Preços: yfinance (fechamento ajustado) · taxa livre de risco:{' '}
            {dados.risco_retorno?.fonte_taxa === 'bcb-sgs-11'
              ? 'Selic diária, série 11 do BCB'
              : 'taxa fixa (BCB indisponível)'}
          </span>
          <span>
            {dados.parametros.pregoes} pregões · carteira de{' '}
            {dados.parametros.valor_carteira.toLocaleString('pt-BR', {
              style: 'currency',
              currency: 'BRL',
              maximumFractionDigits: 0,
            })}
          </span>
        </div>
      )}
    </div>
  )
}
