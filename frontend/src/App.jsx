import { useState } from 'react'
import { calcularVaREmpirico } from './api'
import logo from './assets/logo.png'
import PainelParametros from './components/PainelParametros'
import Kpis from './components/Kpis'
import GraficoDistribuicao from './components/GraficoDistribuicao'
import GraficoBacktest from './components/GraficoBacktest'
import Violacoes from './components/Violacoes'
import GraficoEvolucao from './components/GraficoEvolucao'
import { dataCurta } from './formato'

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

export default function App() {
  const [params, setParams] = useState(PADRAO)
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(false)

  const calcular = async () => {
    setCarregando(true)
    setErro(null)
    try {
      const resposta = await calcularVaREmpirico({
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
    } catch (e) {
      setErro(e.message)
      setDados(null)
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div className="app">
      <header className="topo">
        <div className="marca">
          <img className="selo" src={logo} alt="Inteli Finance" />
          <div>
            <div className="olho">Inteli Finance · Célula de Risco</div>
            <h1>VaR Empírico</h1>
          </div>
        </div>
        <p className="subtitulo">
          Value at Risk por simulação histórica: o risco lido direto da distribuição observada,
          sem hipótese de normalidade. Dados de mercado via yfinance.
        </p>
      </header>

      <div className="grade">
        <PainelParametros
          params={params}
          setParams={setParams}
          onCalcular={calcular}
          carregando={carregando}
        />

        <main>
          {erro && <div className="erro">{erro}</div>}

          {!dados && !erro && (
            <div className="vazio">
              Monte a carteira ao lado e clique em <strong>Calcular VaR empírico</strong>.
              <br />
              O cálculo baixa os preços do yfinance — a primeira consulta leva alguns segundos.
            </div>
          )}

          {dados && (
            <>
              <Kpis dados={dados} />
              <GraficoDistribuicao dados={dados} />
              <GraficoBacktest dados={dados} />
              <Violacoes dados={dados} />
              <GraficoEvolucao dados={dados} />

              <div className="rodape">
                <span>
                  Método: simulação histórica ·{' '}
                  {Object.entries(dados.parametros.pesos)
                    .map(([t, w]) => `${t} ${(w * 100).toFixed(0)}%`)
                    .join(' · ')}
                </span>
                <span>
                  {dados.parametros.pregoes} pregões · {dataCurta(dados.parametros.inicio)} a{' '}
                  {dataCurta(dados.parametros.fim)} · fonte yfinance
                </span>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  )
}
