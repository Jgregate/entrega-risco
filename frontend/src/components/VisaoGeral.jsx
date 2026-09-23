import { useEffect, useState } from 'react'
import { listarCategorias, listarPeriodos, top10Fundos } from '../api'
import { brlCurto, inteiro, num, pct, pctSinal } from '../formato'
import BuscaFundos from './BuscaFundos'
import { Carregando, Erro, GradeKpis, Kpi, Ressalva, Secao, Segmentado, Vazio } from './ui'

/** `retorno_%` vem em pontos percentuais; os formatadores esperam decimal. */
const decimal = (v) => (v === null || v === undefined ? null : v / 100)

/**
 * Porta de entrada da plataforma.
 *
 * Duas perguntas, nesta ordem: "como está meu book?" e "que fundo eu analiso
 * agora?". O resumo do book é um espelho enxuto do módulo Meu Book — quem
 * quer o detalhe clica e vai para lá; quem só abriu o sistema vê de imediato
 * se precisa olhar alguma coisa.
 *
 * O ranking tem dois filtros, categoria e janela, e os dois recalculam a
 * tabela inteira no backend: retorno, volatilidade, Sharpe e drawdown saem
 * sempre do mesmo recorte que está selecionado.
 */
export default function VisaoGeral({ resumoBook, temBook, onIrParaBook, onEscolherFundo, status }) {
  const [periodo, setPeriodo] = useState('12m')
  const [categoria, setCategoria] = useState(null)
  const [janelas, setJanelas] = useState([])
  const [categorias, setCategorias] = useState([])

  const [top10, setTop10] = useState(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState(null)

  useEffect(() => {
    Promise.all([listarPeriodos('ranking'), listarCategorias()])
      .then(([p, c]) => {
        setJanelas(p)
        setCategorias(c)
      })
      .catch(() => {
        /* o ranking ainda funciona nos padrões; o erro aparece na busca abaixo */
      })
  }, [])

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    setErro(null)
    top10Fundos(periodo, categoria)
      .then((d) => ativo && setTop10(d))
      .catch((e) => ativo && setErro(e.message))
      .finally(() => ativo && setCarregando(false))
    return () => {
      ativo = false
    }
  }, [periodo, categoria])

  const rotuloCategoria = categorias.find((c) => c.chave === categoria)?.rotulo

  return (
    <>
      <Secao
        titulo="Meu book"
        descricao="Resumo da sua carteira de fundos."
        acao={
          temBook ? (
            <button type="button" className="btn-texto btn-estreito" onClick={onIrParaBook}>
              Abrir o book completo →
            </button>
          ) : null
        }
      >
        {!temBook ? (
          <Vazio motivo="Adicione fundos em Meu Book, ou pelo botão na análise de qualquer fundo.">
            Você ainda não montou um book.
          </Vazio>
        ) : !resumoBook ? (
          <Vazio motivo="Abra Meu Book para consolidar as posições.">
            Book montado, ainda sem consolidação nesta sessão.
          </Vazio>
        ) : (
          <GradeKpis colunas={4}>
            <Kpi
              rotulo="Patrimônio"
              valor={brlCurto(resumoBook.resumo.patrimonio)}
              nota={`${resumoBook.resumo.fundos} fundos · ${resumoBook.resumo.gestoras} gestoras`}
            />
            <Kpi
              rotulo={`Rentabilidade · ${resumoBook.periodo.rotulo}`}
              valor={pctSinal(resumoBook.metricas.retorno_acumulado)}
              nota={
                resumoBook.metricas.cdi_acumulado !== null
                  ? `CDI: ${pctSinal(resumoBook.metricas.cdi_acumulado)}`
                  : undefined
              }
            />
            <Kpi
              rotulo="Volatilidade"
              valor={pct(resumoBook.metricas.volatilidade_anualizada, 1)}
              nota={`Sharpe ${num(resumoBook.metricas.sharpe)}`}
            />
            <Kpi
              rotulo="Drawdown atual"
              valor={pct(resumoBook.metricas.drawdown_atual, 2)}
              nota={`máximo ${pct(resumoBook.metricas.drawdown_maximo, 1)}`}
            />
          </GradeKpis>
        )}
      </Secao>

      <Secao
        titulo="Analisar um fundo"
        descricao="Busque por nome, CNPJ, código CVM ou gestora entre as classes ativas na CVM."
      >
        <div className="cartao">
          <BuscaFundos onEscolher={onEscolherFundo} rotulo="Qual fundo você quer analisar?" />
        </div>
      </Secao>

      <Secao
        titulo="Maiores retornos do período"
        descricao="Entre as classes com pelo menos 100 cotistas e sem saltos de cota atípicos — o que costuma indicar desdobramento ou erro de reporte, não performance."
        acao={
          <Segmentado
            aria="Janela do ranking"
            valor={periodo}
            onMudar={setPeriodo}
            opcoes={janelas.map((j) => ({ valor: j.chave, texto: j.rotulo }))}
          />
        }
      >
        <div className="cartao">
          <div className="linha-filtros">
            <span className="rotulo" style={{ margin: 0 }}>
              Categoria
            </span>
            <Segmentado
              aria="Categoria do ranking"
              valor={categoria}
              onMudar={setCategoria}
              opcoes={[
                { valor: null, texto: 'Todas' },
                ...categorias.map((c) => ({ valor: c.chave, texto: c.rotulo })),
              ]}
            />
          </div>

          {carregando && <Carregando texto="Calculando o ranking…" />}
          {erro && <Erro>{erro}</Erro>}

          {top10 && top10.length === 0 && !carregando && (
            <Vazio
              motivo={
                categoria
                  ? 'O ranking é calculado sobre o informe diário da CVM, que cobre as classes de fundos financeiros. FII, ETF, Fiagro e boa parte dos FIDC e FIP não reportam nele — a lacuna é da fonte, não do filtro.'
                  : 'A CVM pode não ter publicado ainda os informes dos meses dessa janela.'
              }
            >
              {categoria
                ? `Nenhum fundo de ${rotuloCategoria} com histórico publicado nessa janela.`
                : 'Não foi possível montar o ranking.'}
            </Vazio>
          )}

          {top10 && top10.length > 0 && (
            <div className="rolagem-horizontal">
              <table>
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Fundo</th>
                    <th scope="col" className="col-num">Retorno</th>
                    <th scope="col" className="col-num">Volatilidade</th>
                    <th scope="col" className="col-num" title="Só é calculado em janelas de 12 meses ou mais: anualizar um período curto viraria projeção.">
                      Sharpe
                    </th>
                    <th scope="col" className="col-num">Drawdown</th>
                    <th scope="col" className="col-num">Patrimônio</th>
                    <th scope="col" className="col-num">Cotistas</th>
                  </tr>
                </thead>
                <tbody>
                  {top10.map((f, i) => (
                    <tr key={f.cnpj}>
                      <td>{i + 1}</td>
                      <td>
                        <button
                          type="button"
                          className="link-fundo"
                          onClick={() => onEscolherFundo({ cnpj: f.cnpj, nome: f.nome })}
                        >
                          {f.nome}
                        </button>
                        {(f.gestora || f.categoria) && (
                          <div className="legenda-mini">
                            {[f.gestora, !categoria && f.categoria].filter(Boolean).join(' · ')}
                          </div>
                        )}
                      </td>
                      <td className="num ganho">{pctSinal(decimal(f['retorno_%']), 1)}</td>
                      <td className="num">{pct(decimal(f['volatilidade_%']), 1)}</td>
                      <td className="num">{num(f.sharpe)}</td>
                      <td className={`num${f['drawdown_%'] < 0 ? ' perda' : ''}`}>
                        {pct(decimal(f['drawdown_%']), 1)}
                      </td>
                      <td className="num">{brlCurto(f.patrimonio_mi * 1e6)}</td>
                      <td className="num">{inteiro(f.cotistas)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <Ressalva>
            Retorno passado no ranking não é recomendação nem previsão. Volatilidade, Sharpe e
            drawdown são calculados sobre as cotas mensais da mesma janela — os números diários,
            mais finos, estão na análise individual de cada fundo.
          </Ressalva>
        </div>
      </Secao>

      {status && (
        <p className="legenda-mini nota-unidade">
          {status.ultima_atualizacao
            ? `Dados da CVM atualizados em ${status.ultima_atualizacao}.`
            : 'Ainda sem dados da CVM em cache nesta instalação.'}
        </p>
      )}
    </>
  )
}
