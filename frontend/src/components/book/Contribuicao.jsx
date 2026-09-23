import {
  Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from 'recharts'
import { CORES, num, pct, pctSinal } from '../../formato'
import CartaoGrafico from '../CartaoGrafico'
import {
  CURSOR_BARRA, Dica, MARGEM, PROPS_EIXO_X, PROPS_EIXO_Y, PROPS_GRADE, tickPercentual,
} from '../grafico'
import { Ressalva, Vazio } from '../ui'

/**
 * Quem puxou o retorno e quem carrega o risco.
 *
 * Contribuição para o retorno é uma barra com polaridade (somou ou tirou),
 * então usa a escala divergente: vermelho para quem tirou, claro para quem
 * somou. Contribuição para o risco não tem polaridade — ninguém "tira risco"
 * numa carteira comprada — então é barra de cor única, ordenada.
 */
function rotuloCurto(nome, cnpj) {
  const base = nome || cnpj
  return base.length > 26 ? `${base.slice(0, 25)}…` : base
}

export default function Contribuicao({ dados, nomePorCnpj }) {
  const retorno = dados.contribuicao_retorno || {}
  const risco = dados.risco || {}

  const serieRetorno = (retorno.itens || []).map((i) => ({
    ...i,
    rotulo: rotuloCurto(nomePorCnpj[i.cnpj], i.cnpj),
    nome: nomePorCnpj[i.cnpj] || i.cnpj,
  }))

  const serieRisco = (risco.itens || []).map((i) => ({
    ...i,
    rotulo: rotuloCurto(nomePorCnpj[i.cnpj], i.cnpj),
    nome: nomePorCnpj[i.cnpj] || i.cnpj,
  }))

  const alturaRetorno = Math.max(200, serieRetorno.length * 38 + 48)
  const alturaRisco = Math.max(200, serieRisco.length * 38 + 48)

  // com um fundo so nao ha nada a atribuir: todo o retorno e todo o risco sao
  // dele por definicao, e duas barras de 100% nao respondem pergunta nenhuma
  if (serieRetorno.length < 2) {
    return (
      <Vazio motivo="A decomposição compara fundos entre si — com um único fundo, 100% do retorno e do risco vêm dele por definição. Adicione outro fundo ao book.">
        Sem o que decompor.
      </Vazio>
    )
  }

  return (
    <>
      <div className="duo">
        <CartaoGrafico
          titulo="Contribuição para o retorno"
          altura={alturaRetorno}
          subtitulo="Quanto de todo o retorno do período veio de cada fundo, já considerando o peso que ele tinha a cada dia."
        >
          {(altura) =>
            serieRetorno.length === 0 ? (
              <Vazio>Sem contribuições calculadas.</Vazio>
            ) : (
              <ResponsiveContainer width="100%" height={altura}>
                <BarChart data={serieRetorno} layout="vertical" margin={{ ...MARGEM, left: 8 }}>
                  <CartesianGrid {...PROPS_GRADE} horizontal={false} vertical />
                  <XAxis type="number" {...PROPS_EIXO_X} tickFormatter={tickPercentual(1)} />
                  <YAxis
                    type="category" dataKey="rotulo" {...PROPS_EIXO_Y}
                    width={170} tick={{ fontSize: 10.5 }} interval={0}
                  />
                  <ReferenceLine x={0} stroke="rgba(255,255,255,0.25)" />
                  <Tooltip
                    content={
                      <Dica
                        formatar={(v) => pctSinal(v, 2)}
                        rotularData={(r) => serieRetorno.find((s) => s.rotulo === r)?.nome || r}
                        extra={(_, r) => {
                          const i = serieRetorno.find((s) => s.rotulo === r)
                          return i?.participacao !== null && i?.participacao !== undefined
                            ? `${pct(i.participacao, 1)} do retorno total`
                            : null
                        }}
                      />
                    }
                    cursor={CURSOR_BARRA}
                  />
                  <Bar dataKey="contribuicao" name="Contribuição" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                    {serieRetorno.map((i) => (
                      <Cell
                        key={i.cnpj}
                        fill={i.contribuicao >= 0 ? CORES.branco : CORES.vermelhoClaro}
                        fillOpacity={i.contribuicao >= 0 ? 0.88 : 1}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )
          }
        </CartaoGrafico>

        <CartaoGrafico
          titulo="Contribuição para o risco"
          altura={alturaRisco}
          subtitulo="Que fatia da volatilidade da carteira cada fundo responde, já descontado o efeito de diversificação."
        >
          {(altura) =>
            serieRisco.length === 0 ? (
              <Vazio motivo="É preciso ao menos três pregões em comum entre os fundos.">
                Sem decomposição de risco.
              </Vazio>
            ) : (
              <ResponsiveContainer width="100%" height={altura}>
                <BarChart data={serieRisco} layout="vertical" margin={{ ...MARGEM, left: 8 }}>
                  <CartesianGrid {...PROPS_GRADE} horizontal={false} vertical />
                  <XAxis type="number" {...PROPS_EIXO_X} tickFormatter={tickPercentual(1)} />
                  <YAxis
                    type="category" dataKey="rotulo" {...PROPS_EIXO_Y}
                    width={170} tick={{ fontSize: 10.5 }} interval={0}
                  />
                  <Tooltip
                    content={
                      <Dica
                        formatar={(v) => pct(v, 2)}
                        rotularData={(r) => serieRisco.find((s) => s.rotulo === r)?.nome || r}
                        extra={(_, r) => {
                          const i = serieRisco.find((s) => s.rotulo === r)
                          if (!i) return null
                          return `${pct(i.participacao, 1)} do risco · peso ${pct(
                            i.peso,
                            1
                          )} · vol. própria ${pct(i.volatilidade_individual, 1)}`
                        }}
                      />
                    }
                    cursor={CURSOR_BARRA}
                  />
                  <Bar
                    dataKey="contribuicao" name="Contribuição à volatilidade"
                    fill={CORES.vermelhoClaro} radius={[0, 4, 4, 0]} isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            )
          }
        </CartaoGrafico>
      </div>

      <div className="cartao">
        <h4>Leitura cruzada</h4>
        <p className="legenda-mini">
          Quem entrega retorno acima do risco que traz está na metade de cima. A comparação
          entre as duas colunas é a pergunta que o book existe para responder.
        </p>
        <div className="rolagem-horizontal">
          <table>
            <thead>
              <tr>
                <th scope="col">Fundo</th>
                <th scope="col" className="col-num">Peso</th>
                <th scope="col" className="col-num">Contrib. retorno</th>
                <th scope="col" className="col-num">% do retorno</th>
                <th scope="col" className="col-num">Contrib. risco</th>
                <th scope="col" className="col-num">% do risco</th>
              </tr>
            </thead>
            <tbody>
              {serieRetorno.map((r) => {
                const risc = serieRisco.find((s) => s.cnpj === r.cnpj)
                return (
                  <tr key={r.cnpj}>
                    <td>{r.nome}</td>
                    <td className="num">{pct(risc?.peso, 1)}</td>
                    <td className={`num ${r.contribuicao < 0 ? 'perda' : 'ganho'}`}>
                      {pctSinal(r.contribuicao, 2)}
                    </td>
                    <td className="num">{pct(r.participacao, 1)}</td>
                    <td className="num">{pct(risc?.contribuicao, 2)}</td>
                    <td className="num">{pct(risc?.participacao, 1)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {retorno.residuo_capitalizacao !== null && retorno.residuo_capitalizacao !== undefined && (
          <Ressalva>
            A soma das contribuições ({pctSinal(retorno.soma, 2)}) difere do retorno da carteira
            em {num(retorno.residuo_capitalizacao * 100, 2)} p.p. — é o efeito de capitalização,
            que não pertence a nenhum fundo isolado e por isso não é rateado entre eles.
          </Ressalva>
        )}
      </div>
    </>
  )
}
