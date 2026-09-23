import { useState } from 'react'
import { analisar, analisarConsolidado, analisarRendaFixa } from './api'
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
import { CORES, brl, dataCurta, rotuloConfianca } from './formato'
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
  rendaFixa: [],
  inicio: iso(anosAtras(5)),
  fim: iso(hoje),
  confianca: 0.95,
  horizonte: 1,
  janela: 252,
  valor_carteira: 100000,
}

const ROTULO_CLASSE = {
  acoes: 'Renda Variável',
  'renda-fixa': 'Renda Fixa',
  consolidado: 'Ambos',
}

const ABAS = [
  { id: 'vars', titulo: 'VaRs', sub: 'empírico · paramétrico · EWMA' },
  { id: 'risco', titulo: 'Risco e retorno', sub: 'Sharpe · Sortino' },
  { id: 'book', titulo: 'Book', sub: 'carteira e parâmetros' },
  { id: 'fundos', titulo: 'Fundos', sub: 'CVM · fundos de investimento' },
]

/**
 * Diz, em cima dos gráficos, sobre qual book as métricas foram calculadas.
 * Sem isso o painel de VaR de renda fixa é visualmente idêntico ao de ações.
 */
function FaixaClasse({ dados, classe }) {
  const rf = classe === 'renda-fixa'
  const consolidado = classe === 'consolidado'
  const avisos = dados.avisos ?? []

  return (
    <div className="barra-janela">
      <div>
        <span className="rotulo" style={{ margin: 0 }}>
          {consolidado
            ? 'Métricas sobre a carteira consolidada'
            : `Métricas sobre o book de ${ROTULO_CLASSE[classe]}`}
        </span>
        <p className="legenda-mini" style={{ margin: '5px 0 0' }}>
          {consolidado ? (
            <>
              {brl(dados.composicao.valor_acoes)} em ações (
              {(dados.composicao.peso_acoes * 100).toFixed(0)}%) e{' '}
              {brl(dados.composicao.valor_renda_fixa)} em títulos (
              {(dados.composicao.peso_renda_fixa * 100).toFixed(0)}%) ·{' '}
              {brl(dados.composicao.valor_total)} no total · as duas pernas na mesma matriz de
              retornos, ponderadas por valor de mercado, então a correlação entre elas entra no
              VaR.
            </>
          ) : rf ? (
            <>
              {dados.marcacao.posicoes.length} título
              {dados.marcacao.posicoes.length > 1 ? 's' : ''} do Tesouro Direto ·{' '}
              {brl(dados.marcacao.totais.valor_marcado)} marcados pelo PU de venda de{' '}
              {dataCurta(dados.marcacao.data_base)} · retornos da série de PU, ponderados por
              valor de mercado.
            </>
          ) : (
            <>
              {dados.book.length} ativos · {brl(dados.parametros.valor_carteira)} · preços de
              fechamento ajustado do yfinance, ponderados pelo peso informado.
            </>
          )}
        </p>
        {avisos.length > 0 && (
          <ul className="avisos">
            {avisos.map((a, i) => (
              <li key={i} className={a.severidade === 'erro' ? 'perda' : 'destaque-suave'}>
                {a.mensagem}
              </li>
            ))}
          </ul>
        )}
      </div>
      <span className="chip ativo" style={{ borderColor: CORES.vermelhoClaro }}>
        {ROTULO_CLASSE[classe]}
      </span>
    </div>
  )
}

export default function App() {
  const [params, setParams] = useState(PADRAO)
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(false)
  const [aba, setAba] = useState('book')
  const [classe, setClasse] = useState('acoes')
  // janela de visualização da aba de VaRs (null = histórico completo)
  const [janelaAnos, setJanelaAnos] = useState(null)

  const calcular = async () => {
    setCarregando(true)
    setErro(null)
    const risco = {
      inicio: params.inicio,
      fim: params.fim,
      confianca: params.confianca,
      horizonte: Number(params.horizonte),
      janela: Number(params.janela),
    }
    try {
      const acoes = params.posicoes.map((p) => ({
        ticker: p.ticker.trim().toUpperCase(),
        peso: Number(p.peso),
      }))
      const resposta =
        classe === 'acoes'
          ? await analisar({
              ...risco,
              posicoes: acoes,
              valor_carteira: Number(params.valor_carteira),
            })
          : classe === 'renda-fixa'
            ? await analisarRendaFixa({ ...risco, posicoes: params.rendaFixa })
            : await analisarConsolidado({
                ...risco,
                acoes,
                renda_fixa: params.rendaFixa,
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

  // a resposta de ações não traz `classe`; a de renda fixa traz
  const classeDosDados = dados?.classe ?? 'acoes'

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
            {classeDosDados === 'renda-fixa'
              ? dados.marcacao.posicoes
                  .map((p) => `${p.tipo} ${p.vencimento.slice(0, 4)}`)
                  .join(' · ')
              : Object.keys(dados.parametros.pesos).join(' · ')}
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
            classe={classe}
            setClasse={setClasse}
            onCalcular={calcular}
            carregando={carregando}
            dados={dados}
          />
        )}

        {aba === 'vars' &&
          (dados ? (
            <>
              <FaixaClasse dados={dados} classe={classeDosDados} />
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

        {aba === 'risco' &&
          (dados ? (
            <>
              <FaixaClasse dados={dados} classe={classeDosDados} />
              <AbaRiscoRetorno dados={dados} />
            </>
          ) : (
            semDados
          ))}

        {aba === 'fundos' && <AbaFundos />}
      </main>

      {dados && (
        <div className="rodape">
          <span>
            {classeDosDados === 'acoes'
              ? 'Preços: yfinance (fechamento ajustado)'
              : `Preços: ${
                  classeDosDados === 'consolidado' ? 'yfinance (fechamento ajustado) e ' : ''
                }PU de venda do Tesouro Transparente (data base ${dataCurta(
                  dados.marcacao.data_base
                )})`}{' '}
            · taxa livre de risco:{' '}
            {dados.risco_retorno?.fonte_taxa === 'bcb-sgs-11'
              ? 'Selic diária, série 11 do BCB'
              : 'taxa fixa (BCB indisponível)'}
          </span>
          <span>
            {dados.parametros.pregoes}{' '}
            {classeDosDados === 'acoes' ? 'pregões' : 'datas-base'} · carteira de{' '}
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
