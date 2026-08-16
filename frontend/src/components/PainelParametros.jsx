import { useMemo } from 'react'
import { brl, pct } from '../formato'

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

  // valor nominal = fatia do peso sobre o valor total da carteira
  const nominal = (peso) =>
    somaPesos > 0 ? ((Number(peso) || 0) / somaPesos) * Number(params.valor_carteira) : 0

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
    <div className="book">
      <div className="cartao">
        <h3>Carteira</h3>
        <p className="legenda">
          Tickers do yfinance — ações da B3 usam sufixo <strong>.SA</strong>. O peso é relativo:
          a soma é normalizada para 100% e o valor nominal sai da fatia sobre o total da carteira.
        </p>

        <table className="tabela-book">
          <thead>
            <tr>
              <th>Ativo</th>
              <th style={{ width: 96 }}>Peso</th>
              <th style={{ width: 128, textAlign: 'right' }}>Valor nominal</th>
              <th style={{ width: 74, textAlign: 'right' }}>Part.</th>
              <th style={{ width: 38 }} />
            </tr>
          </thead>
          <tbody>
            {posicoes.map((pos, i) => (
              <tr key={i}>
                <td>
                  <input
                    value={pos.ticker}
                    placeholder="PETR4.SA"
                    onChange={(e) => atualizarPosicao(i, 'ticker', e.target.value.toUpperCase())}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={pos.peso}
                    onChange={(e) => atualizarPosicao(i, 'peso', e.target.value)}
                  />
                </td>
                <td className="num destaque-suave">{brl(nominal(pos.peso))}</td>
                <td className="num">
                  {somaPesos > 0 ? pct((Number(pos.peso) || 0) / somaPesos, 1) : '—'}
                </td>
                <td>
                  <button
                    className="btn-icone"
                    onClick={() => remover(i)}
                    disabled={posicoes.length === 1}
                    title="Remover ativo"
                  >
                    −
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={2}>Total</td>
              <td className="num">{brl(Number(params.valor_carteira))}</td>
              <td className="num">100%</td>
              <td />
            </tr>
          </tfoot>
        </table>

        <button className="btn-texto" onClick={adicionar}>
          + adicionar ativo
        </button>
      </div>

      <div className="cartao">
        <h3>Parâmetros de risco</h3>
        <p className="legenda">
          Valem para os três VaRs ao mesmo tempo — é o que torna a comparação entre eles honesta.
        </p>

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

        <div className="campo">
          <label>Janela do backtest (pregões)</label>
          <input
            type="number"
            min="30"
            max="1500"
            step="21"
            value={params.janela}
            onChange={(e) => atualizar('janela', Number(e.target.value))}
          />
        </div>

        <div className="separador" />

        <button className="btn-principal" onClick={onCalcular} disabled={!valido || carregando}>
          {carregando ? (
            <>
              <span className="carregando" />
              calculando…
            </>
          ) : (
            'Rodar análise'
          )}
        </button>
        <p className="aviso-pesos">
          Puxa preços do yfinance e a Selic do Banco Central. A primeira consulta leva alguns
          segundos.
        </p>
      </div>
    </div>
  )
}
