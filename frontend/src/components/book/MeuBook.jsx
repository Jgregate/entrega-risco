import { useEffect, useMemo, useState } from 'react'
import { analiseBook } from '../../api'
import { paraApi, posicaoIncompleta } from '../../book'
import SeletorPeriodo from '../SeletorPeriodo'
import { Carregando, Erro, Ressalva, Secao, Vazio } from '../ui'
import Alocacao from './Alocacao'
import Comparador from './Comparador'
import Contribuicao from './Contribuicao'
import Custos from './Custos'
import EditorPosicoes from './EditorPosicoes'
import KpisBook from './KpisBook'
import Liquidez from './Liquidez'
import PerformanceBook from './PerformanceBook'
import RiscoBook from './RiscoBook'
import TabelaFundos from './TabelaFundos'
import Tributacao from './Tributacao'

/**
 * Meu Book: de uma lista de posições para a leitura consolidada da carteira,
 * na ordem quanto tenho → como rendeu → onde está → que risco carrega →
 * quando vira caixa → quem puxa o resultado → o detalhe fundo a fundo →
 * quanto custa → quanto o fisco leva.
 *
 * A consolidação roda com um atraso curto depois de cada edição: o usuário
 * digita valor e data numa sequência rápida, e disparar a análise a cada
 * tecla faria o servidor reprocessar séries diárias sem necessidade.
 */
const ESPERA_EDICAO = 600

export default function MeuBook({
  posicoes,
  onMudar,
  onRemover,
  onAdicionar,
  periodos,
  benchmarks,
  onAbrirFundo,
  onConsolidar,
}) {
  const [periodo, setPeriodo] = useState('12m')
  const [selecionadosBench, setSelecionadosBench] = useState(['cdi'])
  const [dados, setDados] = useState(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState(null)
  const [comparando, setComparando] = useState([])
  const [modalAberto, setModalAberto] = useState(false)

  const calculaveis = useMemo(() => posicoes.filter((p) => !posicaoIncompleta(p)), [posicoes])

  // a assinatura serializa só o que muda o resultado: sem isso, qualquer
  // re-render do pai dispararia uma nova consolidação
  const assinatura = useMemo(
    () => JSON.stringify([calculaveis.map(paraApi), periodo, [...selecionadosBench].sort()]),
    [calculaveis, periodo, selecionadosBench]
  )

  useEffect(() => {
    if (!calculaveis.length) {
      setDados(null)
      setErro(null)
      return undefined
    }

    let ativo = true
    const timer = setTimeout(() => {
      setCarregando(true)
      setErro(null)
      analiseBook(calculaveis.map(paraApi), periodo, selecionadosBench)
        .then((d) => {
          if (!ativo) return
          setDados(d)
          // a Visão Geral reaproveita este resultado em vez de refazer a conta
          onConsolidar?.(d)
        })
        .catch((e) => {
          if (ativo) {
            setErro(e.message)
            setDados(null)
          }
        })
        .finally(() => ativo && setCarregando(false))
    }, ESPERA_EDICAO)

    return () => {
      ativo = false
      clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assinatura])

  const nomePorCnpj = useMemo(
    () => Object.fromEntries((dados?.fundos || []).map((f) => [f.cnpj, f.nome || f.cnpj])),
    [dados]
  )

  const alternarComparacao = (cnpj) =>
    setComparando((atual) =>
      atual.includes(cnpj) ? atual.filter((c) => c !== cnpj) : [...atual, cnpj]
    )

  const fundosComparados = (dados?.fundos || []).filter((f) => comparando.includes(f.cnpj))

  const editor = (
    <EditorPosicoes
      posicoes={posicoes}
      onMudar={onMudar}
      onRemover={onRemover}
      onAdicionar={onAdicionar}
    />
  )

  if (!posicoes.length) {
    return (
      <>
        {editor}
        <Vazio motivo="Adicione fundos acima — ou use o botão “Adicionar ao meu book” na tela de análise de qualquer fundo.">
          Monte seu book para ver a consolidação: patrimônio, rentabilidade, risco,
          liquidez, custos e tributação.
        </Vazio>
      </>
    )
  }

  return (
    <>
      {editor}

      {!calculaveis.length && (
        <Vazio motivo="Informe a quantidade de cotas ou o valor investido em pelo menos um fundo.">
          Nenhuma posição pode ser consolidada ainda.
        </Vazio>
      )}

      {erro && <Erro>{erro}</Erro>}

      {calculaveis.length > 0 && !dados && !erro && (
        <Vazio motivo="A primeira consolidação baixa e processa os informes diários da CVM de cada fundo; as seguintes são instantâneas.">
          <Carregando texto="Consolidando o book…" />
        </Vazio>
      )}

      {dados && (
        <div className={carregando ? 'recarregando' : undefined}>
          <SeletorPeriodo
            periodos={periodos}
            valor={periodo}
            onMudar={setPeriodo}
            intervalo={null}
            onIntervalo={() => {}}
            inicio={dados.periodo.inicio}
            fim={dados.periodo.fim}
            descricao="Recorta a performance, o risco e as contribuições do book."
          />

          {carregando && <Carregando texto="Recalculando…" />}

          {dados.ignorados?.length > 0 && (
            <Ressalva>
              Fora da consolidação:{' '}
              {dados.ignorados.map((i) => `${nomePorCnpj[i.cnpj] || i.cnpj} (${i.motivo})`).join(' · ')}
            </Ressalva>
          )}

          <Secao titulo="Visão geral do book">
            <KpisBook dados={dados} />
          </Secao>

          <Secao
            titulo="Performance consolidada"
            descricao="Como a carteira inteira se comportou, contra os benchmarks que você escolher."
          >
            <PerformanceBook
              dados={dados}
              benchmarks={benchmarks}
              selecionados={selecionadosBench}
              onAlternar={(chave) =>
                setSelecionadosBench((atual) =>
                  atual.includes(chave)
                    ? atual.filter((c) => c !== chave)
                    : [...atual, chave]
                )
              }
            />
          </Secao>

          <Secao
            titulo="Alocação"
            descricao="Onde o patrimônio está distribuído — e onde ele está concentrado."
          >
            <Alocacao dados={dados} />
          </Secao>

          <Secao
            titulo="Risco consolidado"
            descricao="Volatilidade da carteira, concentração e o quanto os fundos se repetem entre si."
          >
            <RiscoBook dados={dados} nomePorCnpj={nomePorCnpj} />
          </Secao>

          <Secao
            titulo="Liquidez"
            descricao="Quanto do book vira caixa em cada horizonte de resgate."
          >
            <Liquidez dados={dados} />
          </Secao>

          <Secao
            titulo="Contribuição para retorno e risco"
            descricao="Quem está puxando o resultado e quem está trazendo a oscilação."
          >
            <Contribuicao dados={dados} nomePorCnpj={nomePorCnpj} />
          </Secao>

          <Secao
            titulo="Fundos no book"
            acao={
              comparando.length >= 2 ? (
                <button
                  type="button"
                  className="btn-principal btn-estreito"
                  onClick={() => setModalAberto(true)}
                >
                  Comparar {comparando.length} fundos
                </button>
              ) : comparando.length === 1 ? (
                <span className="legenda-mini">Marque mais um fundo para comparar.</span>
              ) : null
            }
          >
            <TabelaFundos
              fundos={dados.fundos}
              onAbrirFundo={onAbrirFundo}
              selecionados={comparando}
              onSelecionar={alternarComparacao}
            />
          </Secao>

          <Secao
            titulo="Custos"
            descricao="O que as taxas consomem do book por ano."
          >
            <Custos dados={dados} />
          </Secao>

          <Secao
            titulo="Tributação"
            descricao="Quanto sobraria se você resgatasse o book hoje — uma estimativa, não o informe oficial."
          >
            <Tributacao dados={dados} />
          </Secao>
        </div>
      )}

      {modalAberto && fundosComparados.length >= 2 && (
        <Comparador
          fundos={fundosComparados}
          serieFundos={dados.serie_fundos}
          onFechar={() => setModalAberto(false)}
        />
      )}
    </>
  )
}
