import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CORES, brl, dataCurta, num, pct } from '../formato'
import { Kpi } from './Kpis'
import CartaoGrafico from './CartaoGrafico'

function DicaCurvas({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-data">{dataCurta(p.data)}</div>
      <div style={{ color: CORES.vermelhoClaro }}>carteira {pct(p.carteira)}</div>
      <div style={{ color: 'rgba(255,255,255,0.75)' }}>Selic {pct(p.selic)}</div>
      <div style={{ color: CORES.vermelho, marginTop: 3 }}>drawdown {pct(p.drawdown)}</div>
    </div>
  )
}

function DicaIndice({ active, payload, campo, rotulo, cor }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-data">{dataCurta(p.data)}</div>
      <div style={{ color: cor }}>
        {rotulo} <strong>{num(p[campo])}</strong>
      </div>
    </div>
  )
}

function PainelIndice({ dados, campo, rotulo, cor, nota, dominio, janela }) {
  return (
    <CartaoGrafico
      titulo={`${rotulo} móvel`}
      cor={cor}
      altura={240}
      subtitulo={`janela de ${janela} pregões · ${nota}`}
    >
      {(altura) => (
      <ResponsiveContainer width="100%" height={altura}>
        <LineChart data={dados} margin={{ top: 6, right: 8, bottom: 0, left: -24 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey="data"
            stroke="rgba(255,255,255,0.35)"
            tick={{ fontSize: 10.5 }}
            tickLine={false}
            minTickGap={42}
            tickFormatter={(v) => v.slice(2, 7)}
          />
          <YAxis
            domain={dominio}
            stroke="rgba(255,255,255,0.35)"
            tick={{ fontSize: 10.5 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            content={<DicaIndice campo={campo} rotulo={rotulo} cor={cor} />}
            cursor={{ stroke: 'rgba(255,255,255,0.2)' }}
          />
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.25)" />
          <Line
            type="monotone"
            dataKey={campo}
            stroke={cor}
            strokeWidth={1.8}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      )}
    </CartaoGrafico>
  )
}

export default function AbaRiscoRetorno({ dados }) {
  const rr = dados.risco_retorno
  if (!rr) {
    return <div className="vazio">Rode a análise no Book para ver a relação risco-retorno.</div>
  }

  const bateuSelic = (rr.excesso_anualizado ?? 0) > 0
  const usouFallback = rr.fonte_taxa !== 'bcb-sgs-11'

  // escala única para Sharpe e Sortino: comparar os dois é o ponto do gráfico
  const valores = rr.indices_moveis.flatMap((p) =>
    [p.sharpe, p.sortino].filter((v) => v !== null && v !== undefined)
  )
  // limites inteiros: com o domínio cru os ticks saem quebrados (−2,9999…)
  const dominioIndices = [
    Math.floor(Math.min(...valores, 0)),
    Math.ceil(Math.max(...valores, 0)),
  ]

  return (
    <>
      <div className="kpis">
        <Kpi
          rotulo="Sharpe (a.a.)"
          valor={num(rr.sharpe)}
          nota="retorno excedente por unidade de risco total"
          destaque
          cor={CORES.vermelhoClaro}
        />
        <Kpi
          rotulo="Sortino (a.a.)"
          valor={num(rr.sortino)}
          nota="mesmo prêmio, punindo só as quedas"
          destaque
          cor={CORES.branco}
        />
        <Kpi
          rotulo="Excesso sobre a Selic"
          valor={pct(rr.excesso_anualizado)}
          nota={bateuSelic ? 'a carteira bateu o CDI do período' : 'a carteira ficou abaixo da Selic'}
          destaque
          cor={bateuSelic ? CORES.vermelhoClaro : CORES.vermelho}
        />
      </div>

      <div className="kpis kpis-secundario">
        <Kpi
          rotulo="Retorno anualizado"
          valor={pct(rr.retorno_anualizado)}
          nota={`acumulado ${pct(rr.retorno_acumulado)}`}
        />
        <Kpi
          rotulo="Selic anualizada"
          valor={pct(rr.selic_anualizada)}
          nota={`acumulada ${pct(rr.selic_acumulada)}`}
        />
        <Kpi
          rotulo="Vol. anualizada"
          valor={pct(rr.vol_anualizada, 1)}
          nota={`downside ${pct(rr.desvio_downside_anualizado, 1)}`}
        />
        <Kpi
          rotulo="Máximo drawdown"
          valor={pct(rr.max_drawdown)}
          nota={`fundo em ${dataCurta(rr.data_max_drawdown)}`}
        />
        <Kpi
          rotulo="Dias positivos"
          valor={pct(rr.dias_positivos / (rr.dias_positivos + rr.dias_negativos), 1)}
          nota={`${rr.dias_positivos} altas · ${rr.dias_negativos} quedas`}
        />
        <Kpi
          rotulo="Taxa livre de risco"
          valor={usouFallback ? 'Taxa fixa' : 'Selic'}
          nota={rr.observacao_taxa}
        />
      </div>

      <CartaoGrafico
        titulo="Carteira contra a Selic"
        altura={280}
        subtitulo="Retorno acumulado das duas pontas. A distância entre as curvas é o prêmio que o risco pagou — e é exatamente esse excesso que entra no numerador do Sharpe e do Sortino."
      >
        {(altura) => (
        <ResponsiveContainer width="100%" height={altura}>
          <AreaChart data={rr.evolucao} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <defs>
              <linearGradient id="grad-carteira" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CORES.vermelho} stopOpacity={0.5} />
                <stop offset="100%" stopColor={CORES.vermelho} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="data"
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              minTickGap={60}
              tickFormatter={(v) => v.slice(0, 7)}
            />
            <YAxis
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            />
            <Tooltip content={<DicaCurvas />} cursor={{ stroke: 'rgba(255,255,255,0.2)' }} />
            <Legend
              wrapperStyle={{ fontSize: 12, paddingTop: 6 }}
              formatter={(v) => <span style={{ color: 'rgba(255,255,255,0.72)' }}>{v}</span>}
            />
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.25)" />
            <Area
              type="monotone"
              dataKey="carteira"
              name="carteira"
              stroke={CORES.vermelhoClaro}
              strokeWidth={1.8}
              fill="url(#grad-carteira)"
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="selic"
              name="Selic acumulada"
              stroke="rgba(255,255,255,0.75)"
              strokeWidth={1.5}
              strokeDasharray="5 4"
              fill="none"
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
        )}
      </CartaoGrafico>

      <section>
        <div className="titulo-secao">
          <h3>Sharpe e Sortino móveis</h3>
          <p className="legenda">
            Índices recalculados em janela de {rr.janela_rolling} pregões. Um número só para o
            período inteiro esconde regime: aqui dá para ver quando a relação risco-retorno
            desandou. Os dois painéis dividem a mesma escala — Sortino acima de Sharpe no mesmo
            ponto significa que a volatilidade da carteira é predominantemente para cima.
          </p>
        </div>
        <div className="duo">
          <PainelIndice
            dados={rr.indices_moveis}
            campo="sharpe"
            rotulo="Sharpe"
            cor={CORES.vermelhoClaro}
            nota="denominador é o desvio de todos os retornos"
            dominio={dominioIndices}
            janela={rr.janela_rolling}
          />
          <PainelIndice
            dados={rr.indices_moveis}
            campo="sortino"
            rotulo="Sortino"
            cor={CORES.branco}
            nota="denominador é só o desvio das quedas"
            dominio={dominioIndices}
            janela={rr.janela_rolling}
          />
        </div>
      </section>

      <CartaoGrafico
        titulo="Drawdown"
        altura={200}
        subtitulo={
          `Queda percentual em relação ao topo anterior. O fundo do gráfico é a pior sequência que um cotista teria atravessado — pior drawdown de ${pct(
            rr.max_drawdown
          )} sobre ${brl(dados.parametros.valor_carteira)}, ou ${brl(
            Math.abs(rr.max_drawdown * dados.parametros.valor_carteira)
          )}.`
        }
      >
        {(altura) => (
        <ResponsiveContainer width="100%" height={altura}>
          <AreaChart data={rr.evolucao} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <defs>
              <linearGradient id="grad-dd" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CORES.vermelho} stopOpacity={0.05} />
                <stop offset="100%" stopColor={CORES.vermelho} stopOpacity={0.55} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="data"
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              minTickGap={60}
              tickFormatter={(v) => v.slice(0, 7)}
            />
            <YAxis
              stroke="rgba(255,255,255,0.35)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            />
            <Tooltip content={<DicaCurvas />} cursor={{ stroke: 'rgba(255,255,255,0.2)' }} />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke={CORES.vermelhoClaro}
              strokeWidth={1.4}
              fill="url(#grad-dd)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
        )}
      </CartaoGrafico>
    </>
  )
}
