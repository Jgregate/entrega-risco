const CONFIANCAS = [
  { valor: 0.9, texto: '90%' },
  { valor: 0.95, texto: '95%' },
  { valor: 0.975, texto: '97,5%' },
  { valor: 0.99, texto: '99%' },
]

/**
 * Parâmetros de risco — os mesmos para ações e renda fixa, que é o que torna
 * a comparação entre as duas classes honesta.
 *
 * O valor da carteira só aparece em ações: no book de renda fixa o valor sai
 * da marcação a mercado (quantidade × PU), não de um total informado.
 */
export default function ParametrosRisco({
  params,
  setParams,
  onCalcular,
  carregando,
  valido,
  mostrarValorCarteira = true,
  aviso,
}) {
  const atualizar = (campo, valor) => setParams((p) => ({ ...p, [campo]: valor }))

  return (
    <div className="cartao">
      <h3>Parâmetros de risco</h3>
      <p className="legenda">
        Valem para os três VaRs ao mesmo tempo — é o que torna a comparação entre eles honesta.
      </p>

      {mostrarValorCarteira && (
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
      )}

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
        <div className="campo">
          <label>Projeção (pregões)</label>
          <input
            type="number"
            min="1"
            max="252"
            step="21"
            value={params.horizonte_projecao}
            onChange={(e) => atualizar('horizonte_projecao', Number(e.target.value))}
          />
        </div>
      </div>
      <p className="legenda-mini">
        A projeção é independente do horizonte do VaR: 21 pregões ≈ um mês, 252 ≈ um ano. Ela
        alimenta a aba <strong>Rastreabilidade</strong>.
      </p>

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
      <p className="aviso-pesos">{aviso}</p>
    </div>
  )
}
