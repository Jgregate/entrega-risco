import { useEffect, useState } from 'react'

/**
 * Cartão de gráfico que amplia em tela cheia ao ser clicado.
 *
 * `children` é uma função que recebe a altura e devolve o gráfico, para o
 * mesmo componente ser renderizado nos dois tamanhos sem duplicar código:
 *
 *   <CartaoGrafico titulo="Empírico">{(altura) => <Grafico altura={altura} />}</CartaoGrafico>
 */
export default function CartaoGrafico({
  titulo,
  cor,
  subtitulo,
  altura = 240,
  children,
}) {
  const [aberto, setAberto] = useState(false)

  useEffect(() => {
    if (!aberto) return undefined
    const aoTeclar = (e) => {
      if (e.key === 'Escape') setAberto(false)
    }
    window.addEventListener('keydown', aoTeclar)
    // trava o scroll do fundo enquanto a lupa está aberta
    const overflowAnterior = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', aoTeclar)
      document.body.style.overflow = overflowAnterior
    }
  }, [aberto])

  const cabecalho = (
    <>
      {titulo && (
        <h4 style={cor ? { color: cor } : undefined}>{titulo}</h4>
      )}
      {subtitulo && <p className="legenda-mini">{subtitulo}</p>}
    </>
  )

  return (
    <>
      <div
        className="cartao cartao-grafico"
        role="button"
        tabIndex={0}
        title="Clique para ampliar"
        onClick={() => setAberto(true)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setAberto(true)
          }
        }}
      >
        <span className="lupa" aria-hidden="true">
          ⤢
        </span>
        {cabecalho}
        {children(altura)}
      </div>

      {aberto && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={titulo || 'Gráfico ampliado'}
          onClick={() => setAberto(false)}
        >
          <div className="lightbox-caixa" onClick={(e) => e.stopPropagation()}>
            <div className="lightbox-topo">
              <div>{cabecalho}</div>
              <button
                className="btn-fechar"
                onClick={() => setAberto(false)}
                aria-label="Fechar"
              >
                ✕
              </button>
            </div>
            <div className="lightbox-corpo">{children('100%')}</div>
            <p className="lightbox-dica">Clique fora ou pressione Esc para fechar.</p>
          </div>
        </div>
      )}
    </>
  )
}
