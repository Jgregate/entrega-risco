import { COR_METODO, brl, num, pct, rotuloConfianca } from '../formato'

export function Kpi({ rotulo, valor, nota, destaque = false, cor }) {
  return (
    <div className="kpi" style={cor ? { borderTop: `2px solid ${cor}` } : undefined}>
      <span className="rotulo">{rotulo}</span>
      <div className="valor" style={destaque && cor ? { color: cor } : undefined}>
        {valor}
      </div>
      {nota && <div className="nota">{nota}</div>}
    </div>
  )
}

/** Um cartão por método: o VaR lado a lado é a leitura principal desta aba. */
export default function Kpis({ dados }) {
  const { parametros, metodos, ordem_metodos, estatisticas } = dados
  const conf = rotuloConfianca(parametros.confianca)
  const h = parametros.horizonte_dias

  return (
    <>
      <div className="kpis">
        {ordem_metodos.map((nome) => {
          const m = metodos[nome]
          const resumo = m.backtest.resumo
          return (
            <div className="kpi" key={nome} style={{ borderTop: `2px solid ${COR_METODO[nome]}` }}>
              <span className="rotulo">
                VaR {m.rotulo} · {conf} · {h}d
              </span>
              <div className="valor" style={{ color: COR_METODO[nome] }}>
                {pct(m.var_percentual)}
              </div>
              <div className="nota">
                {brl(m.var_monetario)} · ES {pct(m.es_percentual)}
                <br />
                {resumo.violacoes} violações vs. {num(resumo.violacoes_esperadas, 1)} esperadas
              </div>
            </div>
          )
        })}
      </div>

      <div className="kpis kpis-secundario">
        <Kpi
          rotulo="Pior retorno"
          valor={pct(dados.pior_retorno)}
          nota={`janela de ${h} dia${h > 1 ? 's' : ''}`}
        />
        <Kpi
          rotulo="Vol. anualizada"
          valor={pct(estatisticas.vol_anualizada, 1)}
          nota={`${estatisticas.observacoes} observações`}
        />
        <Kpi
          rotulo="Assimetria · curtose"
          valor={`${num(estatisticas.assimetria)} · ${num(estatisticas.curtose_excesso)}`}
          nota="curtose em excesso sobre a normal"
        />
      </div>
    </>
  )
}
