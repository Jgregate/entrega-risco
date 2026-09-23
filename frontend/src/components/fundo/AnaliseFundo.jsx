import { useEffect, useState } from 'react'
import { analiseFundo, composicaoFundo } from '../../api'
import { CORES } from '../../formato'
import SeletorPeriodo from '../SeletorPeriodo'
import { Carregando, Erro, Ressalva, Secao, Vazio } from '../ui'
import Cadastro from './Cadastro'
import Composicao from './Composicao'
import Consistencia from './Consistencia'
import Drawdown from './Drawdown'
import Identificacao from './Identificacao'
import KpisFundo from './KpisFundo'
import Patrimonio from './Patrimonio'
import Performance from './Performance'
import Rentabilidade from './Rentabilidade'
import Sobre from './Sobre'
import TabelaMensal from './TabelaMensal'

/**
 * Tela de análise individual, na ordem em que um analista lê um fundo:
 * quem é → como está → quanto rendeu → quando rendeu → que risco carrega →
 * quanto já caiu → com que regularidade → de que tamanho é → no que investe →
 * a ficha cadastral inteira → e, no fim, o fundo em palavras: o que ele faz
 * com o dinheiro, que nenhum indicador acima responde.
 *
 * A composição da carteira é buscada em paralelo e num pedido separado porque
 * a primeira consulta do mês processa o arquivo CDA inteiro da CVM; deixar
 * isso junto da análise faria a página toda esperar por ela.
 */
export default function AnaliseFundo({ fundo, periodos, benchmarks, onAdicionarAoBook, noBook }) {
  const [periodo, setPeriodo] = useState('12m')
  const [intervalo, setIntervalo] = useState(null)
  const [benchmark, setBenchmark] = useState(null)

  const [dados, setDados] = useState(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState(null)

  const [composicao, setComposicao] = useState(null)
  const [carregandoComp, setCarregandoComp] = useState(false)
  const [erroComp, setErroComp] = useState(null)

  // trocar de fundo zera os controles: período e benchmark do fundo anterior
  // não têm por que valer para o próximo
  useEffect(() => {
    setPeriodo('12m')
    setIntervalo(null)
    setBenchmark(null)
    setDados(null)
    setComposicao(null)
    setErroComp(null)
  }, [fundo.cnpj])

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    setErro(null)

    analiseFundo(fundo.cnpj, { periodo, benchmark, ...(intervalo || {}) })
      .then((d) => {
        if (ativo) setDados(d)
      })
      .catch((e) => {
        if (ativo) {
          setErro(e.message)
          setDados(null)
        }
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })

    return () => {
      ativo = false
    }
  }, [fundo.cnpj, periodo, benchmark, intervalo])

  useEffect(() => {
    let ativo = true
    setCarregandoComp(true)
    setErroComp(null)
    composicaoFundo(fundo.cnpj)
      .then((c) => ativo && setComposicao(c))
      .catch((e) => ativo && setErroComp(e.message))
      .finally(() => ativo && setCarregandoComp(false))
    return () => {
      ativo = false
    }
  }, [fundo.cnpj])

  if (erro && !dados) {
    return (
      <>
        <div className="titulo-secao">
          <h3>{fundo.nome}</h3>
          <p className="legenda">CNPJ {fundo.cnpj}</p>
        </div>
        <Erro>{erro}</Erro>
      </>
    )
  }

  if (!dados) {
    return (
      <Vazio motivo="A primeira consulta de um fundo baixa e processa os informes diários da CVM, o que pode levar alguns minutos. As consultas seguintes são instantâneas.">
        <Carregando texto={`Carregando ${fundo.nome}…`} />
      </Vazio>
    )
  }

  const opcoesBenchmark = (benchmarks || []).map((b) => ({
    valor: b.chave,
    texto: b.rotulo,
  }))

  return (
    // durante um refetch a tela anterior fica visível, só esmaecida: sem
    // esqueleto piscando e sem salto de layout
    <div className={carregando ? 'recarregando' : undefined}>
      <Identificacao fundo={dados.fundo} benchmark={dados.benchmark} />

      <div className="acoes-fundo">
        <div>
          <span className="rotulo">Comparar com</span>
          <div className="segmentado" role="group" aria-label="Benchmark de comparação">
            {opcoesBenchmark.map((o) => {
              const ativo = dados.benchmark.chave === o.valor
              return (
                <button
                  key={o.valor}
                  type="button"
                  className={`chip${ativo ? ' ativo' : ''}`}
                  aria-pressed={ativo}
                  onClick={() => setBenchmark(o.valor)}
                  style={ativo ? { borderColor: CORES.vermelhoClaro, color: CORES.vermelhoClaro } : undefined}
                >
                  {o.texto}
                </button>
              )
            })}
          </div>
        </div>

        <button
          type="button"
          className="btn-principal btn-estreito"
          onClick={() => onAdicionarAoBook(dados.fundo)}
          disabled={noBook}
        >
          {noBook ? 'Já está no seu book' : '+ Adicionar ao meu book'}
        </button>
      </div>

      <SeletorPeriodo
        periodos={periodos}
        valor={periodo}
        onMudar={setPeriodo}
        intervalo={intervalo}
        onIntervalo={setIntervalo}
        inicio={dados.periodo.inicio}
        fim={dados.periodo.fim}
        historicoDesde={dados.periodo.historico_desde}
        descricao="Recorta os gráficos e os índices de risco. A tabela de retorno por janela é sempre contada a partir do último pregão."
      />

      {carregando && <Carregando texto="Recalculando…" />}
      {erro && <Erro>{erro}</Erro>}

      {dados.avisos?.map((a) => (
        <Ressalva key={a}>{a}</Ressalva>
      ))}

      <Secao titulo="Principais indicadores">
        <KpisFundo dados={dados} />
      </Secao>

      <Secao
        titulo="Rentabilidade"
        descricao={`Desempenho do fundo contra o ${dados.benchmark.rotulo}, no período selecionado e em cada janela rápida.`}
      >
        <Rentabilidade dados={dados} />
      </Secao>

      <Secao titulo="Rentabilidade histórica">
        <TabelaMensal linhas={dados.tabela_mensal} rotuloBenchmark={dados.benchmark.rotulo} />
      </Secao>

      <Secao
        titulo="Risco e volatilidade"
        descricao="Os índices que resumem o quanto de oscilação o fundo cobrou para entregar o retorno acima."
      >
        <Performance dados={dados} />
      </Secao>

      <Secao
        titulo="Drawdown"
        descricao="Quanto o fundo já caiu a partir de cada topo, e quanto tempo levou para voltar."
      >
        <Drawdown dados={dados} />
      </Secao>

      <Secao
        titulo="Consistência"
        descricao="Com que regularidade o fundo entrega — mês a mês, não só no acumulado."
      >
        <Consistencia dados={dados} rotuloBenchmark={dados.benchmark.rotulo} />
      </Secao>

      <Secao
        titulo="Patrimônio"
        descricao="Tamanho do fundo ao longo do tempo: patrimônio e número de cotistas."
      >
        <Patrimonio dados={dados} />
      </Secao>

      <Secao
        titulo="Composição da carteira"
        descricao="Onde o dinheiro do fundo está alocado, segundo o último formulário CDA publicado pela CVM."
      >
        <Composicao composicao={composicao} carregando={carregandoComp} erro={erroComp} />
      </Secao>

      <Secao titulo="Informações cadastrais">
        <Cadastro fundo={dados.fundo} cotistas={dados.patrimonio.cotistas} />
      </Secao>

      <Secao
        titulo="Sobre o fundo"
        descricao="Quem gere, que estratégia usa e como ela é implementada — a leitura qualitativa que fecha a análise."
      >
        <Sobre sobre={dados.sobre} fundo={dados.fundo} />
      </Secao>
    </div>
  )
}
