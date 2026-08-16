import { brl, num, pct } from '../formato'

function Kpi({ rotulo, valor, nota, destaque = false, faixa = false }) {
  return (
    <div className={`kpi${faixa ? ' faixa' : ''}`}>
      <span className="rotulo">{rotulo}</span>
      <div className={`valor${destaque ? ' destaque' : ''}`}>{valor}</div>
      {nota && <div className="nota">{nota}</div>}
    </div>
  )
}

export default function Kpis({ dados }) {
  const { parametros, resultado, estatisticas, backtest } = dados
  const conf = `${(parametros.confianca * 100).toFixed(parametros.confianca === 0.975 ? 1 : 0)}%`
  const h = parametros.horizonte_dias
  const resumo = backtest.resumo

  return (
    <div className="kpis">
      <Kpi
        rotulo={`VaR ${conf} · ${h}d`}
        valor={pct(resultado.var_percentual)}
        nota={`perda esperada ser superada em ${pct(1 - parametros.confianca, 1)} dos períodos`}
        destaque
        faixa
      />
      <Kpi
        rotulo="VaR em reais"
        valor={brl(resultado.var_monetario)}
        nota={`sobre ${brl(parametros.valor_carteira)}`}
        faixa
      />
      <Kpi
        rotulo="Expected shortfall"
        valor={pct(resultado.es_percentual)}
        nota={`média das perdas além do VaR · ${brl(resultado.es_monetario)}`}
      />
      <Kpi
        rotulo="Pior retorno"
        valor={pct(resultado.pior_retorno)}
        nota={`janela de ${h} dia${h > 1 ? 's' : ''}`}
      />
      <Kpi
        rotulo="Vol. anualizada"
        valor={pct(estatisticas.vol_anualizada, 1)}
        nota={`assimetria ${num(estatisticas.assimetria)} · curtose exc. ${num(
          estatisticas.curtose_excesso
        )}`}
      />
      <Kpi
        rotulo="Violações no backtest"
        valor={`${resumo.violacoes} / ${resumo.violacoes_esperadas}`}
        nota={`observadas vs. esperadas em ${resumo.observacoes} pregões`}
      />
    </div>
  )
}
