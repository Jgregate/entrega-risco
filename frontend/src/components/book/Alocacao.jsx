import { useMemo } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { CORES, brl, brlCurto, corCategoria, dobraCategorias, pct } from '../../formato'
import CartaoGrafico from '../CartaoGrafico'
import { Amostra, Vazio } from '../ui'

/**
 * Onde o patrimônio está: por classe de ativo e por gestora.
 *
 * Duas formas diferentes de propósito. Classe é um punhado de categorias
 * fechadas e a pergunta é part-to-whole — rosca, com no máximo seis fatias.
 * Gestora é uma lista aberta que pode ter vinte nomes, e a pergunta é
 * "estou concentrado demais em alguém?" — barras ordenadas, todas na mesma
 * cor, que respondem isso de relance e não gastam cor com identidade que o
 * rótulo já dá.
 */
function Rosca({ itens, total }) {
  const fatias = useMemo(
    () => dobraCategorias(itens.filter((i) => i.valor > 0).sort((a, b) => b.valor - a.valor)),
    [itens]
  )

  return (
    <div className="rosca">
      <ResponsiveContainer width="100%" height={240}>
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
                    {pct(p.value / total, 2)} · {brl(p.value, 2)}
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
              {pct(f.valor / total, 1)}
              <span className="barra-absoluto"> · {brlCurto(f.valor)}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Lista de barras sem rosca — para quando há poucas categorias. */
function BarrasSimples({ itens, total }) {
  const maior = Math.max(...itens.map((i) => i.valor), 1)
  return (
    <ul className="barras">
      {itens.map((c, i) => (
        <li key={c.nome}>
          <div className="barra-topo">
            <span className="barra-rotulo">
              {c.nome}
              <span className="barra-detalhe">
                {' '}
                · {c.fundos} {c.fundos === 1 ? 'fundo' : 'fundos'}
              </span>
            </span>
            <span className="barra-valor">
              {pct(c.valor / total, 1)}
              <span className="barra-absoluto"> · {brl(c.valor, 2)}</span>
            </span>
          </div>
          <div className="barra-trilho">
            <div
              className="barra-preenchida"
              style={{ width: `${(c.valor / maior) * 100}%`, background: corCategoria(i) }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}


function BarrasGestoras({ itens, total, hhi }) {
  if (!itens.length) {
    return <Vazio motivo="Nenhum fundo do book tem gestora identificada na CVM.">Sem dados.</Vazio>
  }

  const maior = Math.max(...itens.map((i) => i.valor), 1)
  const concentrado = hhi !== null && hhi !== undefined && hhi > 0.25

  return (
    <>
      <ul className="barras">
        {itens.map((g) => (
          <li key={g.nome}>
            <div className="barra-topo">
              <span className="barra-rotulo" title={g.nome}>
                {g.nome}
                <span className="barra-detalhe">
                  {' '}
                  · {g.fundos} {g.fundos === 1 ? 'fundo' : 'fundos'}
                </span>
              </span>
              <span className="barra-valor">
                {pct(g.valor / total, 1)}
                <span className="barra-absoluto"> · {brlCurto(g.valor)}</span>
              </span>
            </div>
            <div className="barra-trilho">
              <div
                className="barra-preenchida"
                style={{
                  width: `${(g.valor / maior) * 100}%`,
                  background: CORES.vermelhoClaro,
                }}
              />
            </div>
          </li>
        ))}
      </ul>
      <p className="legenda-mini nota-unidade">
        Índice de concentração (HHI): <strong>{hhi === null ? '—' : hhi.toFixed(2).replace('.', ',')}</strong>
        {concentrado
          ? ' — acima de 0,25 o book depende fortemente de poucas gestoras.'
          : ' — abaixo de 0,25, distribuição considerada pulverizada.'}
      </p>
    </>
  )
}

export default function Alocacao({ dados }) {
  const total = dados.resumo.patrimonio
  const classes = (dados.alocacao?.por_classe || []).map((c) => ({
    nome: c.nome,
    valor: c.valor,
    percentual: c.percentual,
    fundos: c.fundos,
  }))
  const gestoras = dados.alocacao?.por_gestora || []

  return (
    <div className="duo">
      <CartaoGrafico
        titulo="Alocação por classe de ativo"
        altura={240}
        subtitulo="Classe derivada da classificação CVM/ANBIMA de cada fundo."
      >
        {() =>
          !classes.length ? (
            <Vazio motivo="Nenhum fundo do book pôde ser classificado.">Sem dados.</Vazio>
          ) : classes.length < 3 ? (
            // rosca de uma ou duas fatias nao informa nada que o numero ja nao
            // diga; com poucas classes a barra e a leitura honesta
            <BarrasSimples itens={classes} total={total} />
          ) : (
            <Rosca itens={classes} total={total} />
          )
        }
      </CartaoGrafico>

      <div className="cartao">
        <h4>Alocação por gestora</h4>
        <p className="legenda-mini">
          Quanto do patrimônio está com cada gestora — a leitura de concentração que a
          classe de ativo não mostra.
        </p>
        <BarrasGestoras
          itens={gestoras}
          total={total}
          hhi={dados.risco?.concentracao_gestora?.hhi}
        />
      </div>
    </div>
  )
}
