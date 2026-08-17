import { CORES, dataCurta } from '../formato'
import { JANELAS } from '../janela'

/**
 * Controle único da aba de VaRs: recorta o período exibido em todos os
 * gráficos da seção de uma vez.
 */
export default function SeletorJanela({ valor, onMudar, disponiveis, corte, fim }) {
  return (
    <div className="barra-janela">
      <div>
        <span className="rotulo" style={{ margin: 0 }}>
          Janela dos gráficos
        </span>
        <p className="legenda-mini" style={{ margin: '5px 0 0' }}>
          Recorta o período de todos os gráficos abaixo.{' '}
          {corte
            ? `Exibindo ${dataCurta(corte)} a ${dataCurta(fim)}.`
            : 'Exibindo o histórico completo.'}{' '}
          Os cartões acima e o teste de aderência seguem o período inteiro.
        </p>
      </div>
      <div className="segmentado" style={{ margin: 0 }}>
        {JANELAS.map((j) => (
          <button
            key={j.texto}
            className={`chip${valor === j.anos ? ' ativo' : ''}`}
            disabled={j.anos !== null && j.anos > disponiveis}
            onClick={() => onMudar(j.anos)}
            style={
              valor === j.anos
                ? { borderColor: CORES.vermelhoClaro, color: CORES.vermelhoClaro }
                : undefined
            }
          >
            {j.texto}
          </button>
        ))}
      </div>
    </div>
  )
}
