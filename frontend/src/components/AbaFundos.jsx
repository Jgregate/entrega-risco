import { useCallback, useEffect, useState } from 'react'
import { atualizarFundos, listarBenchmarks, listarPeriodos, statusFundos } from '../api'
import '../fundos.css'
import { carregar, salvar } from '../book'
import BuscaFundos from './BuscaFundos'
import VisaoGeral from './VisaoGeral'
import MeuBook from './book/MeuBook'
import AnaliseFundo from './fundo/AnaliseFundo'
import { Erro, Vazio } from './ui'

/**
 * Aba Fundos: a plataforma de fundos em três áreas — a visão consolidada, a
 * análise de um fundo e o book do usuário. O estado que atravessa as três é
 * pequeno de propósito (o fundo aberto e as posições do book) e mora aqui,
 * para clicar num fundo dentro do book levar direto à análise dele.
 *
 * Tudo dentro de `.fundos`: o CSS da plataforma (fundos.css) é escopado nessa
 * classe para não mexer no visual das abas de VaR.
 */
const AREAS = [
  { id: 'geral', titulo: 'Visão Geral', sub: 'book e descoberta' },
  { id: 'fundos', titulo: 'Analisar Fundos', sub: 'análise individual' },
  { id: 'book', titulo: 'Meu Book', sub: 'carteira consolidada' },
]

export default function AbaFundos() {
  const [area, setArea] = useState('geral')
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
    setArea('fundos')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const adicionarAoBook = useCallback((f) => {
    const cnpj = f.cnpj || f.cnpj_fmt
    setPosicoes((atual) =>
      atual.some((p) => p.cnpj === cnpj) ? atual : [...atual, { cnpj, nome: f.nome }]
    )
    setArea('book')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const mudarPosicao = useCallback((indice, campo, valor) => {
    setPosicoes((atual) => atual.map((p, i) => (i === indice ? { ...p, [campo]: valor } : p)))
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
    <div className="fundos">
      <nav className="abas">
        {AREAS.map((a) => (
          <button
            key={a.id}
            type="button"
            className={`aba${area === a.id ? ' ativa' : ''}`}
            aria-current={area === a.id ? 'page' : undefined}
            onClick={() => setArea(a.id)}
          >
            <span className="aba-titulo">{a.titulo}</span>
            <span className="aba-sub">{a.sub}</span>
          </button>
        ))}
      </nav>

      {erroCatalogo && (
        <Erro>
          Não foi possível falar com a API ({erroCatalogo}). Verifique se o backend está rodando
          em <code>http://127.0.0.1:8000</code>.
        </Erro>
      )}

      {area === 'geral' && (
        <VisaoGeral
          resumoBook={resumoBook}
          temBook={posicoes.length > 0}
          onIrParaBook={() => setArea('book')}
          onEscolherFundo={abrirFundo}
          status={status}
        />
      )}

      {area === 'fundos' &&
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
                Busque entre as classes de fundos ativas na CVM por nome, CNPJ, código CVM ou
                gestora.
              </p>
              <BuscaFundos autoFoco onEscolher={abrirFundo} />
            </div>
            <Vazio motivo="A busca cobre as classes em funcionamento normal que reportaram cota nos últimos meses fechados.">
              Escolha um fundo para ver a análise completa: rentabilidade, risco, drawdown,
              consistência, patrimônio e composição da carteira.
            </Vazio>
          </>
        ))}

      {area === 'book' && (
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

      {area === 'fundos' && fundo && (
        <div className="troca-fundo">
          <BuscaFundos onEscolher={abrirFundo} cnpjAtual={fundo.cnpj} rotulo="Analisar outro fundo" />
        </div>
      )}

      <div className="rodape">
        <span>
          Fontes: informes diários e cadastro de fundos da CVM (dados abertos), CDI/Selic/IPCA do
          Banco Central (SGS) e índices de mercado do Yahoo Finance.
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
