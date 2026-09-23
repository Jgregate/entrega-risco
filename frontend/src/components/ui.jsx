/**
 * Primitivas de interface reaproveitadas pelas duas telas.
 *
 * Todas usam as classes que já existiam no guia de estilos (`cartao`, `kpi`,
 * `chip`, `legenda`, `vazio`, `erro`) — nada aqui introduz uma linguagem
 * visual nova, só dá nome aos padrões que o protótipo já tinha.
 */

import { CORES } from '../formato'

/** Cabeçalho de seção, com o mesmo espaçamento do resto da página. */
export function Secao({ titulo, descricao, acao, children }) {
  return (
    <section className="secao">
      <div className="titulo-secao">
        <div className="titulo-secao-linha">
          <h3>{titulo}</h3>
          {acao}
        </div>
        {descricao && <p className="legenda">{descricao}</p>}
      </div>
      {children}
    </section>
  )
}

/** Cartão de indicador. `cor` pinta a barra superior; `destaque` pinta o valor. */
export function Kpi({ rotulo, valor, nota, variacao, destaque = false, cor, titulo }) {
  return (
    <div className="kpi" style={cor ? { borderTop: `2px solid ${cor}` } : undefined} title={titulo}>
      <span className="rotulo">{rotulo}</span>
      <div className="valor" style={destaque && cor ? { color: cor } : undefined}>
        {valor}
      </div>
      {variacao}
      {nota && <div className="nota">{nota}</div>}
    </div>
  )
}

/** Grade de KPIs. `colunas` ajusta a densidade sem sair do grid do sistema. */
export function GradeKpis({ colunas = 3, compacto = false, children }) {
  return (
    <div
      className={`kpis${compacto ? ' kpis-secundario' : ''}`}
      style={{ gridTemplateColumns: `repeat(${colunas}, minmax(0, 1fr))` }}
    >
      {children}
    </div>
  )
}

/**
 * Diferença em relação a um período anterior, em pontos percentuais.
 *
 * `valor` é a DIFERENÇA, não o retorno do período anterior — a seta precisa
 * significar "melhorou/piorou em relação a antes". Mostrar o retorno anterior
 * com uma seta para cima leria como crescimento, que é outra coisa.
 */
export function Variacao({ valor, sufixo = 'vs. período anterior' }) {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return null
  const positivo = valor >= 0
  return (
    <div className={`variacao${positivo ? '' : ' negativa'}`}>
      {positivo ? '▲' : '▼'} {Math.abs(valor * 100).toFixed(2).replace('.', ',')} p.p.
      <span className="variacao-sufixo"> {sufixo}</span>
    </div>
  )
}

/**
 * Par rótulo/valor das fichas cadastrais.
 *
 * `ausente` troca o texto da lacuna: na ficha cadastral ela é sempre "não
 * informado pela CVM" (o campo existe na base e veio vazio), mas em Sobre o
 * fundo há campos que a CVM simplesmente não publica em lugar nenhum.
 */
export function Dado({ rotulo, valor, largo = false, ausente = 'não informado pela CVM' }) {
  const vazio = valor === null || valor === undefined || valor === ''
  return (
    <div className={`dado${largo ? ' dado-largo' : ''}`}>
      <span className="dado-rotulo">{rotulo}</span>
      <span className={`dado-valor${vazio ? ' dado-ausente' : ''}`}>
        {vazio ? ausente : valor}
      </span>
    </div>
  )
}

export function Tag({ children, cor }) {
  return (
    <span className="tag" style={cor ? { borderColor: cor, color: cor } : undefined}>
      {children}
    </span>
  )
}

/** Amostra de cor da legenda — a identidade nunca fica só no texto colorido. */
export function Amostra({ cor }) {
  return <span className="amostra" style={{ background: cor }} aria-hidden="true" />
}

export function Carregando({ texto = 'Carregando…' }) {
  return (
    <p className="aviso-pesos" role="status">
      <span className="carregando" />
      {texto}
    </p>
  )
}

export function Erro({ children }) {
  return (
    <div className="erro" role="alert">
      {children}
    </div>
  )
}

/**
 * Estado vazio. `motivo` explica POR QUE não há dado — a regra do projeto é
 * mostrar a lacuna, nunca preencher com número plausível.
 */
export function Vazio({ children, motivo }) {
  return (
    <div className="vazio">
      {children}
      {motivo && <div className="vazio-motivo">{motivo}</div>}
    </div>
  )
}

/** Aviso discreto para estimativas e coberturas parciais. */
export function Ressalva({ children }) {
  return (
    <p className="ressalva">
      <span aria-hidden="true">ⓘ</span> {children}
    </p>
  )
}

/** Controle segmentado (chips) — o mesmo do protótipo original. */
export function Segmentado({ opcoes, valor, onMudar, aria }) {
  return (
    <div className="segmentado" role="group" aria-label={aria}>
      {opcoes.map((o) => {
        const ativo = valor === o.valor
        return (
          <button
            key={String(o.valor)}
            type="button"
            className={`chip${ativo ? ' ativo' : ''}`}
            disabled={o.desabilitado}
            title={o.titulo}
            aria-pressed={ativo}
            onClick={() => onMudar(o.valor)}
            style={ativo ? { borderColor: CORES.vermelhoClaro, color: CORES.vermelhoClaro } : undefined}
          >
            {o.texto}
          </button>
        )
      })}
    </div>
  )
}

/** Chips de múltipla escolha — usado para ligar/desligar benchmarks. */
export function Alternadores({ opcoes, selecionados, onAlternar, aria }) {
  return (
    <div className="segmentado" role="group" aria-label={aria}>
      {opcoes.map((o) => {
        const ativo = selecionados.includes(o.valor)
        return (
          <button
            key={o.valor}
            type="button"
            className={`chip${ativo ? ' ativo' : ''}`}
            aria-pressed={ativo}
            onClick={() => onAlternar(o.valor)}
            style={ativo && o.cor ? { borderColor: o.cor, color: o.cor } : undefined}
          >
            {ativo && o.cor && <Amostra cor={o.cor} />}
            {o.texto}
          </button>
        )
      })}
    </div>
  )
}
