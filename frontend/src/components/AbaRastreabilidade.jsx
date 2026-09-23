import GraficoPosse from './GraficoPosse'
import GraficoProjecao from './GraficoProjecao'
import GraficoValorizacao from './GraficoValorizacao'
import TabelaRastreabilidade from './TabelaRastreabilidade'
import { Kpi } from './Kpis'
import {
  COR_METODO,
  CORES,
  SELO_CONFIABILIDADE,
  brl,
  dataCurta,
  haQuantoTempo,
  pct,
} from '../formato'

const SEVERIDADE = { erro: 'perda', aviso: 'destaque-suave' }

const ROTULO_CLASSE = {
  acoes: 'Renda Variável',
  'renda-fixa': 'Renda Fixa',
  consolidado: 'Ambos',
}

/**
 * Cabeçalho da aba: sobre qual book a rastreabilidade foi calculada e quanto
 * confiar na projeção.
 *
 * O selo de confiabilidade aparece sempre; os motivos, só quando existem. É a
 * regra herdada do playground: um aviso permanente vira papel de parede e
 * deixa de ser lido justamente quando passa a importar.
 */
function Cabecalho({ rastreabilidade, classe }) {
  const { totais, projecao } = rastreabilidade
  const saude = projecao?.confiabilidade

  return (
    <div className="barra-janela">
      <div>
        <span className="rotulo" style={{ margin: 0 }}>
          Rastreabilidade do book de {ROTULO_CLASSE[classe] || classe}
        </span>
        <p className="legenda-mini" style={{ margin: '5px 0 0' }}>
          {totais.posicoes} {totais.posicoes === 1 ? 'posição' : 'posições'} · compra mais antiga
          em {dataCurta(totais.compra_mais_antiga)} ({haQuantoTempo(totais.dias_corridos)}) ·
          preços de {dataCurta(rastreabilidade.data_referencia)} · projeção de{' '}
          {rastreabilidade.horizonte_projecao} pregões.
        </p>
        {saude?.motivos?.length > 0 && (
          <ul className="avisos">
            {saude.motivos.map((m, i) => (
              <li key={i} className="destaque-suave">
                {m}
              </li>
            ))}
          </ul>
        )}
      </div>
      {saude && (
        <span
          className={`selo-teste ${SELO_CONFIABILIDADE[saude.nivel] || 'ok'}`}
          title="Confiabilidade da projeção, pelo tamanho e pela qualidade da janela de estimação."
        >
          projeção {saude.rotulo.toLowerCase()}
        </span>
      )}
    </div>
  )
}

/** O que a posse rendeu até agora: fato, não estimativa. */
function Realizado({ totais }) {
  const ganhou = (totais.valorizacao_reais ?? 0) >= 0

  return (
    <div className="kpis">
      <Kpi
        rotulo="Valor investido"
        valor={brl(totais.valor_compra)}
        nota={`${totais.posicoes} ${totais.posicoes === 1 ? 'posição' : 'posições'} · compra mais antiga em ${dataCurta(
          totais.compra_mais_antiga
        )}`}
      />
      <Kpi
        rotulo="Valor hoje"
        valor={brl(totais.valor_atual)}
        nota={`preços de ${dataCurta(totais.data_referencia)}`}
      />
      <div
        className="kpi"
        style={{ borderTop: `2px solid ${ganhou ? CORES.branco : CORES.vermelho}` }}
      >
        <span className="rotulo">{ganhou ? 'Valorizou' : 'Desvalorizou'}</span>
        <div className="valor" style={{ color: ganhou ? CORES.branco : CORES.vermelhoClaro }}>
          {pct(totais.valorizacao_percentual)}
        </div>
        <div className="nota">
          {brl(totais.valorizacao_reais)} · {pct(totais.retorno_anualizado, 1)} ao ano ·{' '}
          {totais.pregoes} pregões de posse
        </div>
      </div>
    </div>
  )
}

/**
 * A projeção nos três métodos.
 *
 * O valor esperado é um só — ele vem da deriva da janela, que não depende do
 * método. O que muda entre os três é a LARGURA do intervalo, e é por isso que
 * o número em destaque de cada cartão é o piso: é ali que os métodos
 * discordam, e é a discordância que informa.
 */
function Projetado({ projecao, confianca }) {
  if (!projecao) return null

  if (!projecao.disponivel) {
    return (
      <div className="cartao">
        <h3>Projeção</h3>
        <p className="legenda">{projecao.observacao}</p>
      </div>
    )
  }

  const ordem = ['empirico', 'parametrico', 'ewma']
  const conf = `${(confianca * 100).toFixed(0)}%`

  return (
    <>
      <div className="kpis kpis-secundario">
        <Kpi
          rotulo={`Valor esperado em ${projecao.horizonte_pregoes} pregões`}
          valor={brl(projecao.valor_esperado)}
          nota={`${pct(projecao.variacao_esperada_percentual)} · ${brl(
            projecao.variacao_esperada_reais
          )} · até ${dataCurta(projecao.data_alvo)}`}
        />
        <Kpi
          rotulo="Deriva diária da janela"
          valor={pct(projecao.deriva_diaria, 3)}
          nota={`média dos últimos ${projecao.observacoes_janela} retornos`}
        />
        <Kpi
          rotulo="Partida da projeção"
          valor={dataCurta(projecao.data_partida)}
          nota="última observação conhecida — a janela nunca vê o dia projetado"
        />
      </div>

      <div className="kpis">
        {ordem.map((nome) => {
          const m = projecao.metodos[nome]
          return (
            <div className="kpi" key={nome} style={{ borderTop: `2px solid ${COR_METODO[nome]}` }}>
              <span className="rotulo">
                Piso {m.rotulo} · {conf}
              </span>
              <div className="valor" style={{ color: COR_METODO[nome] }}>
                {brl(m.piso)}
              </div>
              <div className="nota">
                teto {brl(m.teto)} · VaR {pct(m.var_percentual)} ({brl(m.var_monetario)})
                <br />
                {m.sem_perda_na_confianca ? (
                  <>
                    VaR negativo: a {conf}, nem o pior cenário da janela é de perda — típico
                    de papel pós-fixado.
                  </>
                ) : (
                  <>
                    ES {pct(m.es_percentual)} ({brl(m.es_monetario)})
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <p className="legenda-mini" style={{ marginTop: -8, marginBottom: 20 }}>
        {projecao.observacao}
      </p>
    </>
  )
}

/**
 * Aba Rastreabilidade: da compra até a projeção, para os três books.
 *
 * Serve ações, renda fixa e consolidado sem ramificar o cálculo — o backend
 * entrega o mesmo contrato nas três rotas, e a única diferença aqui é mostrar
 * a coluna de classe quando as duas convivem no mesmo book.
 */
export default function AbaRastreabilidade({ dados }) {
  const rast = dados.rastreabilidade
  const classe = dados.classe ?? 'acoes'

  if (!rast || !rast.posicoes.length) {
    return (
      <div className="vazio">
        A análise não devolveu posições rastreáveis.
        <br />
        Confira o book na aba <strong>Book</strong> e rode a análise de novo.
      </div>
    )
  }

  return (
    <>
      <Cabecalho rastreabilidade={rast} classe={classe} />
      <Realizado totais={rast.totais} />
      <Projetado projecao={rast.projecao} confianca={rast.confianca} />

      {rast.avisos?.length > 0 && (
        <div className="cartao">
          <h3>Avisos</h3>
          <ul className="avisos">
            {rast.avisos.map((a, i) => (
              <li key={i} className={SEVERIDADE[a.severidade] || ''}>
                {a.mensagem}
              </li>
            ))}
          </ul>
        </div>
      )}

      <GraficoProjecao rastreabilidade={rast} />
      <GraficoPosse rastreabilidade={rast} />
      <GraficoValorizacao rastreabilidade={rast} />
      <TabelaRastreabilidade
        rastreabilidade={rast}
        mostrarClasse={classe === 'consolidado'}
      />
    </>
  )
}
