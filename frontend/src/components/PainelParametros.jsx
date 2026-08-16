import { useMemo } from 'react'

const CONFIANCAS = [
  { valor: 0.9, texto: '90%' },
  { valor: 0.95, texto: '95%' },
  { valor: 0.975, texto: '97,5%' },
  { valor: 0.99, texto: '99%' },
]

export default function PainelParametros({ params, setParams, onCalcular, carregando }) {
  const { posicoes } = params

  const somaPesos = useMemo(
    () => posicoes.reduce((s, p) => s + (Number(p.peso) || 0), 0),
    [posicoes]
  )

  const atualizar = (campo, valor) => setParams((p) => ({ ...p, [campo]: valor }))

  const atualizarPosicao = (i, campo, valor) =>
    setParams((p) => ({
      ...p,
      posicoes: p.posicoes.map((pos, j) => (j === i ? { ...pos, [campo]: valor } : pos)),
    }))

  const adicionar = () =>
    setParams((p) => ({ ...p, posicoes: [...p.posicoes, { ticker: '', peso: 10 }] }))

  const remover = (i) =>
    setParams((p) => ({ ...p, posicoes: p.posicoes.filter((_, j) => j !== i) }))

  const valido =
    posicoes.length > 0 &&
    posicoes.every((p) => p.ticker.trim() !== '' && Number(p.peso) > 0) &&
    params.inicio < params.fim

  return (
    <div className="cartao painel">
      <h3>Parâmetros</h3>
      <p className="legenda">
        Preços de fechamento ajustado vindos do yfinance. Tickers da B3 usam sufixo{' '}
        <strong>.SA</strong>.
      </p>

      <span className="rotulo">Carteira</span>
      {posicoes.map((pos, i) => (
        <div className="linha-posicao" key={i}>
          <input
            value={pos.ticker}
            placeholder="PETR4.SA"
            onChange={(e) => atualizarPosicao(i, 'ticker', e.target.value.toUpperCase())}
          />
          <input
            type="number"
            min="0"
            step="1"
            value={pos.peso}
            onChange={(e) => atualizarPosicao(i, 'peso', e.target.value)}
          />
          <button
            className="btn-icone"
            onClick={() => remover(i)}
            disabled={posicoes.length === 1}
            title="Remover ativo"
          >
            −
          </button>
        </div>
      ))}
      <button className="btn-texto" onClick={adicionar}>
        + adicionar ativo
      </button>
      <p className="aviso-pesos">
        Soma dos pesos: {somaPesos.toFixed(0)} — os pesos são normalizados para 100%.
      </p>

      <div className="separador" />

      <div className="dupla">
        <div className="campo">
          <label>Início</label>
          <input
            type="date"
            value={params.inicio}
            onChange={(e) => atualizar('inicio', e.target.value)}
          />
        </div>
        <div className="campo">
          <label>Fim</label>
          <input
            type="date"
            value={params.fim}
            onChange={(e) => atualizar('fim', e.target.value)}
          />
        </div>
      </div>

      <div className="dupla">
        <div className="campo">
          <label>Confiança</label>
          <select
            value={params.confianca}
            onChange={(e) => atualizar('confianca', Number(e.target.value))}
          >
            {CONFIANCAS.map((c) => (
              <option key={c.valor} value={c.valor}>
                {c.texto}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label>Horizonte (dias)</label>
          <input
            type="number"
            min="1"
            max="60"
            value={params.horizonte}
            onChange={(e) => atualizar('horizonte', Number(e.target.value))}
          />
        </div>
      </div>

      <div className="dupla">
        <div className="campo">
          <label>Janela do backtest</label>
          <input
            type="number"
            min="30"
            max="1500"
            step="21"
            value={params.janela}
            onChange={(e) => atualizar('janela', Number(e.target.value))}
          />
        </div>
        <div className="campo">
          <label>Valor da carteira</label>
          <input
            type="number"
            min="1"
            step="1000"
            value={params.valor_carteira}
            onChange={(e) => atualizar('valor_carteira', Number(e.target.value))}
          />
        </div>
      </div>

      <button className="btn-principal" onClick={onCalcular} disabled={!valido || carregando}>
        {carregando ? (
          <>
            <span className="carregando" />
            calculando…
          </>
        ) : (
          'Calcular VaR empírico'
        )}
      </button>
    </div>
  )
}
