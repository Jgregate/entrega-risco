import { CORES, corDivergente, corTextoLegivel, num, pct } from '../../formato'
import { GradeKpis, Kpi, Ressalva, Vazio } from '../ui'

/**
 * Risco consolidado: volatilidade, concentração e correlação.
 *
 * A matriz de correlação usa uma escala DIVERGENTE com o vermelho no lado da
 * correlação ALTA — que é o lado ruim para quem diversifica. Isso mantém o
 * vermelho com o mesmo significado que ele tem no resto do sistema ("olhe para
 * cá") em vez de trocar o sentido da cor de uma tela para outra. Zero fica
 * cinza neutro e some no fundo; correlação negativa (o par que se protege)
 * aparece claro.
 */
function Concentracao({ titulo, dados, unidade }) {
  if (!dados || dados.hhi === null) {
    return <Kpi rotulo={titulo} valor="—" nota="sem itens suficientes" />
  }
  const alto = dados.hhi > 0.25
  return (
    <Kpi
      rotulo={titulo}
      valor={num(dados.hhi)}
      cor={alto ? CORES.vermelhoClaro : undefined}
      nota={`maior fatia ${pct(dados.maior, 1)} · ${dados.itens} ${unidade}`}
      titulo="Índice de Herfindahl: soma dos quadrados dos pesos. 1,00 = tudo num item só."
    />
  )
}

function MatrizCorrelacao({ correlacao, nomePorCnpj }) {
  if (!correlacao || correlacao.fundos.length < 2) {
    return (
      <Vazio motivo="A matriz precisa de pelo menos dois fundos com histórico no mesmo período.">
        Sem matriz de correlação.
      </Vazio>
    )
  }

  const { fundos, valores } = correlacao
  const curto = (cnpj) => (nomePorCnpj[cnpj] || cnpj).slice(0, 22)

  return (
    <div className="rolagem-horizontal">
      <table className="matriz">
        <thead>
          <tr>
            <th scope="col" className="matriz-canto" />
            {fundos.map((f, i) => (
              <th key={f} scope="col" className="matriz-topo" title={nomePorCnpj[f] || f}>
                F{i + 1}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {fundos.map((f, i) => (
            <tr key={f}>
              <th scope="row" className="matriz-lado" title={nomePorCnpj[f] || f}>
                <span className="matriz-indice">F{i + 1}</span>
                {curto(f)}
              </th>
              {fundos.map((g, j) => {
                const v = valores[i][j]
                const cor = v === null ? null : corDivergente(-v, 1)
                return (
                  <td
                    key={g}
                    className="matriz-celula"
                    style={cor ? { background: cor, color: corTextoLegivel(cor) } : undefined}
                    title={`${nomePorCnpj[f] || f} × ${nomePorCnpj[g] || g}: ${num(v)}`}
                  >
                    {v === null ? '—' : num(v)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function RiscoBook({ dados, nomePorCnpj }) {
  const risco = dados.risco || {}
  const m = dados.metricas || {}

  return (
    <>
      <GradeKpis colunas={3} compacto>
        <Kpi
          rotulo="Volatilidade consolidada"
          valor={pct(risco.volatilidade ?? m.volatilidade_anualizada, 2)}
          nota="anualizada, já líquida do efeito de diversificação"
        />
        <Kpi rotulo="Índice de Sharpe" valor={num(m.sharpe)} nota="excesso sobre o CDI" />
        <Kpi
          rotulo="Drawdown atual · máximo"
          valor={`${pct(m.drawdown_atual, 1)} · ${pct(m.drawdown_maximo, 1)}`}
        />
      </GradeKpis>

      <GradeKpis colunas={3} compacto>
        <Concentracao titulo="Concentração por fundo" dados={risco.concentracao_fundo} unidade="fundos" />
        <Concentracao titulo="Concentração por gestora" dados={risco.concentracao_gestora} unidade="gestoras" />
        <Concentracao titulo="Concentração por classe" dados={risco.concentracao_classe} unidade="classes" />
      </GradeKpis>

      <div className="cartao">
        <h4>Matriz de correlação</h4>
        <p className="legenda-mini">
          Correlação dos retornos diários no período. Vermelho forte marca os pares que
          andam juntos — dois fundos muito correlacionados ocupam espaço no book sem
          diversificar nada.
        </p>
        <MatrizCorrelacao correlacao={risco.correlacao} nomePorCnpj={nomePorCnpj} />
        <div className="legenda-escala">
          <span className="legenda-escala-rotulo">−1 (se protegem)</span>
          <span className="legenda-escala-barra invertida" />
          <span className="legenda-escala-rotulo">+1 (andam juntos)</span>
        </div>
        <Ressalva>
          Correlação é medida sobre os pregões em que os dois fundos publicaram cota.
          Fundos com histórico curto no período têm estimativa menos confiável.
        </Ressalva>
      </div>
    </>
  )
}
