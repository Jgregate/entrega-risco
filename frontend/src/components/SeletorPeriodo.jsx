import { useState } from 'react'
import { dataCurta } from '../formato'
import { Segmentado } from './ui'

/**
 * Controle único de período da tela.
 *
 * Fica acima de tudo que ele recorta — um filtro por cartão faria cada gráfico
 * contar uma história de um recorte diferente. Os períodos rápidos vêm do
 * backend; o intervalo personalizado é opcional e, quando preenchido,
 * prevalece sobre o período rápido (é o que o usuário acabou de pedir).
 */
export default function SeletorPeriodo({
  periodos,
  valor,
  onMudar,
  intervalo,
  onIntervalo,
  descricao,
  inicio,
  fim,
  historicoDesde,
}) {
  const [abertoPersonalizado, setAberto] = useState(Boolean(intervalo?.inicio))

  const opcoes = (periodos || []).map((p) => ({
    valor: p.chave,
    texto: p.rotulo,
  }))

  const limpar = () => {
    setAberto(false)
    onIntervalo(null)
  }

  return (
    <div className="barra-janela">
      <div>
        <span className="rotulo" style={{ margin: 0 }}>
          Período de análise
        </span>
        <p className="legenda-mini" style={{ margin: '5px 0 0' }}>
          {descricao || 'Recorta todos os gráficos e indicadores abaixo.'}{' '}
          {inicio && fim && (
            <>
              Exibindo <strong>{dataCurta(inicio)}</strong> a <strong>{dataCurta(fim)}</strong>.
            </>
          )}{' '}
          {historicoDesde && (
            <>Histórico disponível desde {dataCurta(historicoDesde)}.</>
          )}
        </p>
      </div>

      <div className="controles-periodo">
        <Segmentado
          opcoes={opcoes}
          valor={intervalo ? null : valor}
          onMudar={(v) => {
            onIntervalo(null)
            setAberto(false)
            onMudar(v)
          }}
          aria="Período de análise"
        />

        <button
          type="button"
          className={`chip${intervalo ? ' ativo' : ''}`}
          aria-expanded={abertoPersonalizado}
          onClick={() => setAberto((a) => !a)}
        >
          Personalizado
        </button>

        {abertoPersonalizado && (
          <form
            className="intervalo"
            onSubmit={(e) => {
              e.preventDefault()
              const dados = new FormData(e.currentTarget)
              const de = dados.get('de')
              const ate = dados.get('ate')
              if (de && ate) onIntervalo({ inicio: de, fim: ate })
            }}
          >
            <input type="date" name="de" defaultValue={intervalo?.inicio || ''} aria-label="De" required />
            <span className="intervalo-ate">até</span>
            <input type="date" name="ate" defaultValue={intervalo?.fim || ''} aria-label="Até" required />
            <button className="chip" type="submit">
              Aplicar
            </button>
            {intervalo && (
              <button className="chip" type="button" onClick={limpar}>
                Limpar
              </button>
            )}
          </form>
        )}
      </div>
    </div>
  )
}
