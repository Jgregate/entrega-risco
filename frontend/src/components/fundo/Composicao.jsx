import { useMemo } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { brlCurto, corCategoria, dobraCategorias, pct } from '../../formato'
import CartaoGrafico from '../CartaoGrafico'
import { Amostra, Carregando, Ressalva, Vazio } from '../ui'

/**
 * Composição da carteira, do arquivo CDA da CVM.
 *
 * A rosca mostra no máximo seis fatias: acima disso as fatias finas ficam
 * indistinguíveis e a cor deixa de identificar. A cauda vira "Outros" e o
 * detalhe completo fica na lista ao lado, que traz valor em reais e
 * percentual de cada classe — a rosca é a leitura de relance, a lista é a
 * leitura exata.
 */
function ListaBarras({ itens, titulo, legenda, vazio }) {
  if (!itens?.length) {
    return (
      <div className="cartao">
        <h4>{titulo}</h4>
        <Vazio motivo={vazio}>Sem dados.</Vazio>
      </div>
    )
  }

  const maior = Math.max(...itens.map((i) => Math.abs(i.percentual ?? 0)), 0.0001)

  return (
    <div className="cartao">
      <h4>{titulo}</h4>
      {legenda && <p className="legenda-mini">{legenda}</p>}
      <ul className="barras">
        {itens.map((item, i) => (
          <li key={`${item.rotulo}-${i}`}>
            <div className="barra-topo">
              <span className="barra-rotulo" title={item.titulo || item.rotulo}>
                {item.rotulo}
              </span>
              <span className="barra-valor">
                {pct(item.percentual, 2)}
                <span className="barra-absoluto"> · {brlCurto(item.valor)}</span>
              </span>
            </div>
            <div className="barra-trilho">
              <div
                className={`barra-preenchida${(item.percentual ?? 0) < 0 ? ' negativa' : ''}`}
                style={{ width: `${(Math.abs(item.percentual ?? 0) / maior) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function Composicao({ composicao, carregando, erro }) {
  const fatias = useMemo(() => {
    if (!composicao?.por_classe) return []
    const positivas = composicao.por_classe
      .filter((c) => (c.valor ?? 0) > 0)
      .map((c) => ({ nome: c.classe, valor: c.valor, percentual: c.percentual }))
      .sort((a, b) => b.valor - a.valor)
    return dobraCategorias(positivas)
  }, [composicao])

  if (carregando) {
    return (
      <div className="cartao">
        <Carregando texto="Processando a carteira do mês na CVM — a primeira consulta pode demorar." />
      </div>
    )
  }

  if (erro) {
    return (
      <Vazio motivo={erro}>Não foi possível carregar a composição da carteira.</Vazio>
    )
  }

  if (!composicao?.disponivel) {
    return (
      <Vazio motivo={composicao?.motivo}>
        Composição de carteira indisponível.
      </Vazio>
    )
  }

  const totalFatias = fatias.reduce((s, f) => s + f.valor, 0)

  return (
    <>
      <div className="duo">
        <CartaoGrafico
          titulo="Distribuição por classe de ativo"
          altura={280}
          subtitulo={`Posição de ${composicao.referencia}, a partir do formulário CDA da CVM.`}
        >
          {(altura) => (
            <div className="rosca">
              <ResponsiveContainer width="100%" height={altura}>
                <PieChart>
                  <Pie
                    data={fatias}
                    dataKey="valor"
                    nameKey="nome"
                    innerRadius="56%"
                    outerRadius="84%"
                    paddingAngle={2}
                    stroke="none"
                    isAnimationActive={false}
                  >
                    {fatias.map((f, i) => (
                      <Cell key={f.nome} fill={corCategoria(i)} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const p = payload[0]
                      return (
                        <div className="tooltip">
                          <div className="t-linha">
                            <Amostra cor={p.payload.fill} />
                            <span className="t-nome">{p.name}</span>
                          </div>
                          <div className="t-extra">
                            {pct(p.value / totalFatias, 2)} · {brlCurto(p.value)}
                          </div>
                        </div>
                      )
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>

              <ul className="legenda-rosca">
                {fatias.map((f, i) => (
                  <li key={f.nome}>
                    <Amostra cor={corCategoria(i)} />
                    <span className="legenda-rosca-nome">
                      {f.nome}
                      {f.agrupado ? ` (${f.agrupado})` : ''}
                    </span>
                    <span className="legenda-rosca-valor">
                      {pct(f.valor / totalFatias, 1)}
                      <span className="barra-absoluto"> · {brlCurto(f.valor)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CartaoGrafico>

        <ListaBarras
          titulo="Maiores posições"
          legenda="As maiores exposições individuais em módulo — posição vendida grande pesa tanto quanto comprada."
          vazio="A CVM não abriu posições individuais desse fundo no mês."
          itens={(composicao.posicoes || []).slice(0, 12).map((p) => ({
            rotulo: p.descricao || p.tipo || p.classe,
            titulo: [p.descricao, p.tipo, p.emissor].filter(Boolean).join(' · '),
            valor: p.valor,
            percentual: p.percentual,
          }))}
        />
      </div>

      <div className="duo">
        <ListaBarras
          titulo="Maiores emissores"
          legenda="Concentração por emissor entre as posições abertas — leitura de risco de crédito e de contraparte."
          vazio="As posições desse fundo não trazem emissor identificado (comum em fundos que investem via cotas ou títulos públicos)."
          itens={(composicao.emissores || []).slice(0, 10).map((e) => ({
            rotulo: e.emissor,
            valor: e.valor,
            percentual: e.percentual,
          }))}
        />

        <ListaBarras
          titulo="Exposição por país"
          legenda="Só os ativos declarados no formulário de investimento no exterior."
          vazio="O fundo não declara posições no exterior com país identificado."
          itens={(composicao.paises || []).slice(0, 10).map((p) => ({
            rotulo: p.pais,
            valor: p.valor,
            percentual: p.percentual,
          }))}
        />
      </div>

      <Ressalva>
        Percentuais calculados sobre a soma das posições ativas do mês. A CVM publica a
        carteira com defasagem e permite sigilo temporário sobre parte das posições, então
        a soma pode não fechar exatamente com o patrimônio líquido da mesma data. Exposição
        por moeda e por setor não constam do formulário CDA.
      </Ressalva>
    </>
  )
}
