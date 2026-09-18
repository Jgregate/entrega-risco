import { useMemo } from 'react'
import ParametrosRisco from './ParametrosRisco'
import { brl, pct } from '../formato'

export default function PainelParametros({
  params,
  setParams,
  onCalcular,
  carregando,
  mostrarParametros = true,
}) {
  const { posicoes } = params

  const somaPesos = useMemo(
    () => posicoes.reduce((s, p) => s + (Number(p.peso) || 0), 0),
    [posicoes]
  )

  // valor nominal = fatia do peso sobre o valor total da carteira
  const nominal = (peso) =>
    somaPesos > 0 ? ((Number(peso) || 0) / somaPesos) * Number(params.valor_carteira) : 0

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
    <div className={mostrarParametros ? 'book' : undefined}>
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

      {mostrarParametros && (
        <ParametrosRisco
          params={params}
          setParams={setParams}
          onCalcular={onCalcular}
          carregando={carregando}
          valido={valido}
          aviso="Puxa preços do yfinance e a Selic do Banco Central. A primeira consulta leva alguns segundos."
        />
      )}
    </div>
  )
}
