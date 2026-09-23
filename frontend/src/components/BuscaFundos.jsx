import { useEffect, useRef, useState } from 'react'
import { buscarFundos } from '../api'
import { Carregando, Erro } from './ui'

/**
 * Barra de busca de fundos.
 *
 * Um campo só para nome, CNPJ, código CVM e gestora: o usuário raramente sabe
 * de antemão qual desses ele tem em mãos, e o formato do que ele digita já
 * diz quase sempre o que ele quis dizer — quem decide é o backend.
 *
 * A busca dispara sozinha depois de uma pausa na digitação (e também no
 * Enter), porque pesquisar fundo é exploratório: o usuário digita um pedaço
 * do nome e quer ver a lista encolher.
 */
export default function BuscaFundos({ onEscolher, cnpjAtual, autoFoco = false, rotulo }) {
  const [termo, setTermo] = useState('')
  const [resultados, setResultados] = useState(null)
  const [buscando, setBuscando] = useState(false)
  const [erro, setErro] = useState(null)
  const campo = useRef(null)
  const pedido = useRef(0)

  useEffect(() => {
    if (autoFoco) campo.current?.focus()
  }, [autoFoco])

  useEffect(() => {
    const q = termo.trim()
    if (q.length < 2) {
      setResultados(null)
      setErro(null)
      return undefined
    }

    const atual = ++pedido.current
    const timer = setTimeout(() => {
      setBuscando(true)
      setErro(null)
      buscarFundos(q)
        .then((achados) => {
          // resposta de uma digitação antiga não pode sobrescrever a atual
          if (atual === pedido.current) setResultados(achados)
        })
        .catch((e) => {
          if (atual === pedido.current) setErro(e.message)
        })
        .finally(() => {
          if (atual === pedido.current) setBuscando(false)
        })
    }, 350)

    return () => clearTimeout(timer)
  }, [termo])

  return (
    <div className="busca">
      <label className="rotulo" htmlFor="busca-fundo">
        {rotulo || 'Buscar fundo'}
      </label>
      <input
        id="busca-fundo"
        ref={campo}
        value={termo}
        autoComplete="off"
        placeholder="Nome do fundo, CNPJ, código CVM ou gestora"
        onChange={(e) => setTermo(e.target.value)}
      />

      {buscando && <Carregando texto="Procurando…" />}
      {erro && <Erro>{erro}</Erro>}

      {resultados && resultados.length === 0 && !buscando && (
        <p className="aviso-pesos">
          Nenhuma classe de fundo ativa na CVM corresponde a “{termo.trim()}”.
        </p>
      )}

      {resultados && resultados.length > 0 && (
        <div className="lista-busca" role="listbox" aria-label="Resultados da busca">
          {resultados.map((f) => (
            <button
              key={f.cnpj}
              type="button"
              role="option"
              aria-selected={cnpjAtual === f.cnpj}
              className={`item-busca${cnpjAtual === f.cnpj ? ' ativo' : ''}`}
              onClick={() => onEscolher(f)}
            >
              <span className="item-nome">{f.nome}</span>
              <span className="item-meta">
                {f.cnpj}
                {f.gestora ? ` · ${f.gestora}` : ''}
                {f.codigo_cvm ? ` · CVM ${f.codigo_cvm}` : ''}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
