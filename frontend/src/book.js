/**
 * Persistência do book no navegador.
 *
 * O book é a carteira do usuário e não existe login nesta aplicação, então
 * guardá-lo em `localStorage` é o que mantém a posição dele entre sessões sem
 * inventar um conceito de conta. O que fica salvo é só o que o usuário digitou
 * — CNPJ, cotas, valor, data, liquidez e taxas. Nenhum número calculado é
 * persistido: cota, patrimônio e rentabilidade são sempre recalculados a
 * partir dos dados da CVM, para uma posição salva ontem não exibir o preço de
 * ontem como se fosse o de hoje.
 */

const CHAVE = 'inteli-finance:book:v1'

/** Campos que o usuário informa — e os únicos que são gravados. */
export const CAMPOS_POSICAO = [
  'cnpj',
  'nome',
  'quantidade_cotas',
  'valor_investido',
  'preco_medio',
  'data_entrada',
  'liquidez_dias',
  'taxa_administracao',
  'taxa_performance',
]

const vazio = (v) => v === '' || v === null || v === undefined

function limpa(posicao) {
  const saida = {}
  for (const campo of CAMPOS_POSICAO) {
    if (!vazio(posicao[campo])) saida[campo] = posicao[campo]
  }
  return saida
}

export function carregar() {
  try {
    const bruto = localStorage.getItem(CHAVE)
    if (!bruto) return []
    const dados = JSON.parse(bruto)
    return Array.isArray(dados) ? dados.map(limpa).filter((p) => p.cnpj) : []
  } catch {
    // localStorage bloqueado (modo privado, política do navegador) ou JSON
    // corrompido: o book começa vazio em vez de a tela inteira quebrar
    return []
  }
}

export function salvar(posicoes) {
  try {
    localStorage.setItem(CHAVE, JSON.stringify(posicoes.map(limpa)))
  } catch {
    /* sem persistência: a sessão atual continua funcionando normalmente */
  }
}

/** Converte a posição da interface no payload numérico que a API espera. */
export function paraApi(posicao) {
  const numero = (v) => (vazio(v) ? undefined : Number(v))
  return {
    cnpj: posicao.cnpj,
    quantidade_cotas: numero(posicao.quantidade_cotas),
    valor_investido: numero(posicao.valor_investido),
    preco_medio: numero(posicao.preco_medio),
    data_entrada: vazio(posicao.data_entrada) ? undefined : posicao.data_entrada,
    liquidez_dias: numero(posicao.liquidez_dias),
    taxa_administracao: numero(posicao.taxa_administracao),
    taxa_performance: numero(posicao.taxa_performance),
  }
}

/**
 * Uma posição só é calculável com quantidade de cotas OU valor investido —
 * a mesma regra do backend, replicada aqui só para avisar antes de enviar.
 */
export function posicaoIncompleta(posicao) {
  return vazio(posicao.quantidade_cotas) && vazio(posicao.valor_investido)
}
