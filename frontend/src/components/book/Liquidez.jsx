import { brl, brlCurto, corOrdinal, pct } from '../../formato'
import { Ressalva, Vazio } from '../ui'

const SEM_DADO = 'Não informado'

/**
 * Quanto do book vira caixa em cada horizonte.
 *
 * As faixas têm ordem natural (D+0 é mais líquido que D+90), então a cor é
 * uma RAMPA de um tom só, do claro ao escuro: a ordem se lê na cor sem
 * precisar da legenda. A faixa "Não informado" fica fora da rampa, em
 * cinza tracejado, porque não é um prazo — é uma lacuna.
 */
export default function Liquidez({ dados }) {
  const faixas = dados.liquidez || []
  const total = dados.resumo.patrimonio

  if (!faixas.length) {
    return <Vazio>Sem posições para calcular liquidez.</Vazio>
  }

  const comPrazo = faixas.filter((f) => f.faixa !== SEM_DADO)
  const semPrazo = faixas.find((f) => f.faixa === SEM_DADO)

  // acumulado: "quanto eu tenho em caixa até D+N" é a pergunta real
  let acumulado = 0
  const linhas = comPrazo.map((f, i) => {
    acumulado += f.percentual ?? 0
    return { ...f, acumulado, cor: corOrdinal(i, Math.max(comPrazo.length, 2)) }
  })

  return (
    <div className="cartao">
      <h4>Liquidez da carteira</h4>
      <p className="legenda-mini">
        Patrimônio por prazo de resgate, do mais líquido ao menos líquido, e quanto se
        acumula até cada horizonte.
      </p>

      <div className="barra-empilhada" role="img" aria-label="Distribuição do patrimônio por prazo de resgate">
        {linhas.map((f) => (
          <span
            key={f.faixa}
            className="segmento"
            style={{ width: `${(f.percentual ?? 0) * 100}%`, background: f.cor }}
            title={`${f.faixa}: ${pct(f.percentual, 1)} · ${brlCurto(f.valor)}`}
          />
        ))}
        {semPrazo && (
          <span
            className="segmento segmento-ausente"
            style={{ width: `${(semPrazo.percentual ?? 0) * 100}%` }}
            title={`${SEM_DADO}: ${pct(semPrazo.percentual, 1)}`}
          />
        )}
      </div>

      <table className="tabela-liquidez">
        <thead>
          <tr>
            <th scope="col">Prazo</th>
            <th scope="col" className="col-num">Valor</th>
            <th scope="col" className="col-num">% do book</th>
            <th scope="col" className="col-num">Acumulado até o prazo</th>
            <th scope="col" className="col-num">Fundos</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((f) => (
            <tr key={f.faixa}>
              <th scope="row">
                <span className="amostra" style={{ background: f.cor }} aria-hidden="true" />
                {f.faixa}
              </th>
              <td className="num">{brl(f.valor, 2)}</td>
              <td className="num">{pct(f.percentual, 1)}</td>
              <td className="num destaque-suave">{pct(f.acumulado, 1)}</td>
              <td className="num">{f.fundos}</td>
            </tr>
          ))}
          {semPrazo && (
            <tr className="linha-ausente">
              <th scope="row">
                <span className="amostra amostra-ausente" aria-hidden="true" />
                {SEM_DADO}
              </th>
              <td className="num">{brl(semPrazo.valor, 2)}</td>
              <td className="num">{pct(semPrazo.percentual, 1)}</td>
              <td className="num">—</td>
              <td className="num">{semPrazo.fundos}</td>
            </tr>
          )}
        </tbody>
      </table>

      {semPrazo && (
        <Ressalva>
          {pct(semPrazo.percentual, 0)} do book está sem prazo de resgate informado. A CVM não
          publica esse dado nos arquivos abertos — preencha a coluna <strong>Resgate D+</strong>
          {' '}nas posições para completar a visão de liquidez.
        </Ressalva>
      )}
      <p className="legenda-mini nota-unidade">
        Total: {brl(total, 2)}. Prazos informados por você, não verificados no regulamento.
      </p>
    </div>
  )
}
