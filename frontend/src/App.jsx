import { useCallback, useEffect, useState } from 'react'
import { atualizarFundos, listarBenchmarks, listarPeriodos, statusFundos } from './api'
import logo from './assets/logo.png'
import { carregar, salvar } from './book'
import BuscaFundos from './components/BuscaFundos'
import VisaoGeral from './components/VisaoGeral'
import MeuBook from './components/book/MeuBook'
import AnaliseFundo from './components/fundo/AnaliseFundo'
import { Erro, Vazio } from './components/ui'

/**
 * Plataforma de fundos de investimento — Inteli Finance.
 *
 * Três áreas, e nada além disso: a visão consolidada, a análise de um fundo e
 * o book do usuário. O estado que atravessa as três é pequeno de propósito —
 * o fundo aberto e as posições do book — e mora aqui, para clicar num fundo
 * dentro do book levar direto à análise dele sem recarregar nada.
 */
const ABAS = [
  { id: 'geral', titulo: 'Visão Geral', sub: 'book e descoberta' },
  { id: 'fundos', titulo: 'Analisar Fundos', sub: 'análise individual' },
  { id: 'book', titulo: 'Meu Book', sub: 'carteira consolidada' },
]

export default function App() {
  const [aba, setAba] = useState('geral')
  const [fundo, setFundo] = useState(null)
  const [posicoes, setPosicoes] = useState(carregar)

  const [periodos, setPeriodos] = useState(null)
  const [benchmarks, setBenchmarks] = useState(null)
  const [status, setStatus] = useState(null)
  const [erroCatalogo, setErroCatalogo] = useState(null)
  const [atualizando, setAtualizando] = useState(false)

  // resumo da última consolidação, para a Visão Geral não refazer a conta
  const [resumoBook, setResumoBook] = useState(null)

  useEffect(() => {
    Promise.all([listarPeriodos(), listarBenchmarks()])
      .then(([p, b]) => {
        setPeriodos(p)
        setBenchmarks(b)
      })
      .catch((e) => setErroCatalogo(e.message))
    statusFundos().then(setStatus).catch(() => setStatus(null))
  }, [])

  useEffect(() => {
    salvar(posicoes)
  }, [posicoes])

  const abrirFundo = useCallback((f) => {
    setFundo({ cnpj: f.cnpj || f.cnpj_fmt, nome: f.nome })
    setAba('fundos')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const adicionarAoBook = useCallback((f) => {
    const cnpj = f.cnpj || f.cnpj_fmt
    setPosicoes((atual) =>
      atual.some((p) => p.cnpj === cnpj) ? atual : [...atual, { cnpj, nome: f.nome }]
    )
    setAba('book')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const mudarPosicao = useCallback((indice, campo, valor) => {
    setPosicoes((atual) =>
      atual.map((p, i) => (i === indice ? { ...p, [campo]: valor } : p))
    )
  }, [])

  const removerPosicao = useCallback((indice) => {
    setPosicoes((atual) => atual.filter((_, i) => i !== indice))
  }, [])

  const atualizar = () => {
    setAtualizando(true)
    atualizarFundos()
      .then(statusFundos)
      .then(setStatus)
      .catch(() => {})
      .finally(() => setAtualizando(false))
  }

  const noBook = fundo ? posicoes.some((p) => p.cnpj === fundo.cnpj) : false

  return (
    <div className="app">
      <header className="topo">
        <div className="marca">
          <img className="selo" src={logo} alt="Inteli Finance" />
          <div>
            <div className="olho">Inteli Finance</div>
            <h1>Plataforma de fundos de investimento</h1>
          </div>
        </div>
        <p className="subtitulo">
          Análise individual e book consolidado, sobre os dados abertos da CVM,
          do Banco Central e do Yahoo Finance.
        </p>
      </header>

      <nav className="abas">
        {ABAS.map((a) => (
          <button
            key={a.id}
            type="button"
            className={`aba${aba === a.id ? ' ativa' : ''}`}
            aria-current={aba === a.id ? 'page' : undefined}
            onClick={() => setAba(a.id)}
          >
            <span className="aba-titulo">{a.titulo}</span>
            <span className="aba-sub">{a.sub}</span>
          </button>
        ))}
      </nav>

      <main>
        {erroCatalogo && (
          <Erro>
            Não foi possível falar com a API ({erroCatalogo}). Verifique se o backend está
            rodando em <code>http://127.0.0.1:8000</code>.
          </Erro>
        )}

        {aba === 'geral' && (
          <VisaoGeral
            resumoBook={resumoBook}
            temBook={posicoes.length > 0}
            onIrParaBook={() => setAba('book')}
            onEscolherFundo={abrirFundo}
            status={status}
          />
        )}

        {aba === 'fundos' &&
          (fundo ? (
            <AnaliseFundo
              fundo={fundo}
              periodos={periodos}
              benchmarks={benchmarks}
              onAdicionarAoBook={adicionarAoBook}
              noBook={noBook}
            />
          ) : (
            <>
              <div className="cartao">
                <h3>Analisar fundos</h3>
                <p className="legenda">
                  Busque entre as classes de fundos ativas na CVM por nome, CNPJ, código CVM
                  ou gestora.
                </p>
                <BuscaFundos autoFoco onEscolher={abrirFundo} />
              </div>
              <Vazio motivo="A busca cobre as classes em funcionamento normal que reportaram cota nos últimos meses fechados.">
                Escolha um fundo para ver a análise completa: rentabilidade, risco, drawdown,
                consistência, patrimônio e composição da carteira.
              </Vazio>
            </>
          ))}

        {aba === 'book' && (
          <MeuBook
            posicoes={posicoes}
            onMudar={mudarPosicao}
            onRemover={removerPosicao}
            onAdicionar={adicionarAoBook}
            periodos={periodos}
            benchmarks={benchmarks}
            onAbrirFundo={abrirFundo}
            onConsolidar={setResumoBook}
          />
        )}

        {aba === 'fundos' && fundo && (
          <div className="troca-fundo">
            <BuscaFundos
              onEscolher={abrirFundo}
              cnpjAtual={fundo.cnpj}
              rotulo="Analisar outro fundo"
            />
          </div>
        )}
      </main>

      <div className="rodape">
        <span>
          Fontes: informes diários e cadastro de fundos da CVM (dados abertos), CDI/Selic/IPCA
          do Banco Central (SGS) e índices de mercado do Yahoo Finance.
        </span>
        <span>
          {status?.ultima_atualizacao
            ? `CVM atualizada em ${status.ultima_atualizacao}`
            : 'sem cache da CVM'}{' '}
          <button
            type="button"
            className="btn-texto btn-inline"
            onClick={atualizar}
            disabled={atualizando}
          >
            {atualizando ? 'atualizando…' : 'atualizar agora'}
          </button>
        </span>
      </div>
    </div>
  )
}
