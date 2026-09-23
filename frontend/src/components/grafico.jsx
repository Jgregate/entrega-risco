/**
 * Peças compartilhadas por todos os gráficos.
 *
 * Centralizar eixos, grade e tooltip aqui é o que garante que um gráfico novo
 * saia igual aos que já existiam: mesma espessura de traço, mesma grade
 * horizontal discreta, mesmo formato de dica. Regras que valem em todos:
 *
 * - grade sólida e recessiva, só horizontal (linha vertical não ajuda a ler
 *   série temporal e polui);
 * - tooltip sempre presente, com data e valor, e o texto em tom neutro — a
 *   identidade da série fica na amostra de cor ao lado, não na cor da letra;
 * - nunca dois eixos Y no mesmo gráfico: escalas diferentes viram dois
 *   gráficos ou uma série indexada à mesma base.
 */

import { CORES } from '../formato'
import { Amostra } from './ui'

export const MARGEM = { top: 8, right: 12, bottom: 0, left: -8 }

export const PROPS_GRADE = {
  stroke: CORES.grade,
  vertical: false,
}

export const PROPS_EIXO_X = {
  stroke: CORES.eixo,
  tick: { fontSize: 10 },
  tickLine: false,
  minTickGap: 36,
}

export const PROPS_EIXO_Y = {
  stroke: CORES.eixo,
  tick: { fontSize: 11 },
  tickLine: false,
  axisLine: false,
}

export const PROPS_LEGENDA = {
  wrapperStyle: { fontSize: 11, paddingTop: 4 },
  iconType: 'plainline',
  iconSize: 14,
}

export const CURSOR_LINHA = { stroke: 'rgba(255,255,255,0.2)' }
export const CURSOR_BARRA = { fill: 'rgba(255,255,255,0.04)' }

/** Eixo Y em percentual, com a unidade explícita no tick. */
export const tickPercentual = (casas = 0) => (v) =>
  `${(v * 100).toFixed(casas).replace('.', ',')}%`

/**
 * Tooltip padrão. `formatar` recebe o valor e devolve o texto já com unidade;
 * `rotularData` traduz a chave do eixo X para algo legível.
 */
export function Dica({ active, payload, label, formatar, rotularData, extra }) {
  if (!active || !payload?.length) return null
  const visiveis = payload.filter((p) => p.value !== null && p.value !== undefined)
  if (!visiveis.length) return null

  return (
    <div className="tooltip">
      <div className="t-data">{rotularData ? rotularData(label) : label}</div>
      {visiveis.map((p) => (
        <div key={p.dataKey} className="t-linha">
          <Amostra cor={p.color} />
          <span className="t-nome">{p.name}</span>
          <strong className="t-valor">{formatar(p.value, p)}</strong>
        </div>
      ))}
      {extra && <div className="t-extra">{extra(visiveis, label)}</div>}
    </div>
  )
}

/**
 * Densidade de pontos no eixo X de uma série temporal: com muitos pregões o
 * rótulo vira mancha, então só alguns são desenhados.
 */
export function intervaloTicks(quantidade, alvo = 6) {
  return Math.max(0, Math.floor(quantidade / alvo) - 1)
}
