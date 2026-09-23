import { useMemo, useState } from 'react'
import { brl, dataCurta, num, pct, pctSinal } from '../../formato'
import { Vazio } from '../ui'

/**
 * A tabela que abre o book inteiro, linha a linha.
 *
 * Ordenável por qualquer coluna numérica, com o nome do fundo levando para a
 * análise individual. Colunas que dependem de dado informado pelo usuário
 * (liquidez, taxas) ou de preço médio (resultado) mostram "—" quando falta a
 * informação, nunca zero: zero é um valor, ausência não.
 */
const COLUNAS = [
  { chave: 'nome', rotulo: 'Fundo', tipo: 'texto', fixa: true },
  { chave: 'gestora', rotulo: 'Gestora', tipo: 'texto' },
  { chave: 'classe', rotulo: 'Classe', tipo: 'texto' },
  { chave: 'valor_atual', rotulo: 'Patrimônio', tipo: 'moeda' },
  { chave: 'percentual', rotulo: '% do book', tipo: 'pct1' },
  { chave: 'quantidade_cotas', rotulo: 'Cotas', tipo: 'num4' },
  { chave: 'preco_medio', rotulo: 'Preço médio', tipo: 'num4' },
  { chave: 'cota_atual', rotulo: 'Cota atual', tipo: 'num4' },
  { chave: 'resultado', rotulo: 'Resultado', tipo: 'moeda', sinal: true },
  { chave: 'rentabilidade', rotulo: 'Rentab.', tipo: 'pctSinal', sinal: true },
  { chave: 'vol12', rotulo: 'Vol. 12M', tipo: 'pct1' },
  { chave: 'sharpe12', rotulo: 'Sharpe', tipo: 'num2' },
  { chave: 'liquidez_dias', rotulo: 'Liquidez', tipo: 'liquidez' },
  { chave: 'taxa_administracao', rotulo: 'Taxa adm.', tipo: 'taxa' },
  { chave: 'taxa_performance', rotulo: 'Taxa perf.', tipo: 'taxa' },
  { chave: 'benchmark', rotulo: 'Benchmark', tipo: 'texto' },
  { chave: 'data_entrada', rotulo: 'Entrada', tipo: 'data' },
  { chave: 'cnpj', rotulo: 'CNPJ', tipo: 'texto' },
]

function formata(valor, tipo) {
  if (valor === null || valor === undefined || valor === '') return '—'
  switch (tipo) {
    case 'moeda': return brl(valor, 2)
    case 'pct1': return pct(valor, 1)
    case 'pctSinal': return pctSinal(valor)
    case 'num2': return num(valor, 2)
    case 'num4': return num(valor, 6)
    case 'data': return dataCurta(valor)
    case 'liquidez': return `D+${valor}`
    case 'taxa': return `${num(valor, 2)}%`
    default: return valor
  }
}

export default function TabelaFundos({ fundos, onAbrirFundo, selecionados, onSelecionar }) {
  const [ordem, setOrdem] = useState({ chave: 'valor_atual', desc: true })
  const [filtro, setFiltro] = useState('')

  const linhas = useMemo(() => {
    const enriquecidas = fundos.map((f) => ({
      ...f,
      vol12: f.metricas?.volatilidade_12m ?? f.metricas?.volatilidade_anualizada ?? null,
      sharpe12: f.metricas?.sharpe ?? null,
    }))

    const termo = filtro.trim().toLowerCase()
    const filtradas = termo
      ? enriquecidas.filter((f) =>
          [f.nome, f.gestora, f.cnpj, f.classe]
            .filter(Boolean)
            .some((v) => String(v).toLowerCase().includes(termo))
        )
      : enriquecidas

    const { chave, desc } = ordem
    return [...filtradas].sort((a, b) => {
      const va = a[chave]
      const vb = b[chave]
      // ausência vai sempre para o fim, independente da direção da ordenação
      if (va === null || va === undefined) return 1
      if (vb === null || vb === undefined) return -1
      const cmp = typeof va === 'string' ? va.localeCompare(vb, 'pt-BR') : va - vb
      return desc ? -cmp : cmp
    })
  }, [fundos, ordem, filtro])

  if (!fundos.length) return <Vazio>Nenhum fundo consolidado.</Vazio>

  const alternar = (chave) =>
    setOrdem((o) => (o.chave === chave ? { chave, desc: !o.desc } : { chave, desc: true }))

  return (
    <div className="cartao">
      <div className="cartao-cabecalho">
        <div>
          <h4>Fundos no book</h4>
          <p className="legenda-mini">
            Clique no nome para abrir a análise individual. Clique num cabeçalho para ordenar.
            Marque dois ou mais para comparar.
          </p>
        </div>
        <input
          className="campo-filtro"
          value={filtro}
          placeholder="Filtrar por nome, gestora ou classe"
          aria-label="Filtrar fundos do book"
          onChange={(e) => setFiltro(e.target.value)}
        />
      </div>

      <div className="rolagem-horizontal">
        <table className="tabela-book">
          <thead>
            <tr>
              <th scope="col" className="col-marcar" aria-label="Comparar" />
              {COLUNAS.map((c) => (
                <th
                  key={c.chave}
                  scope="col"
                  className={`${c.tipo === 'texto' || c.tipo === 'data' ? '' : 'col-num'} ordenavel${
                    ordem.chave === c.chave ? ' ordenada' : ''
                  }`}
                  onClick={() => alternar(c.chave)}
                  aria-sort={
                    ordem.chave === c.chave ? (ordem.desc ? 'descending' : 'ascending') : 'none'
                  }
                >
                  {c.rotulo}
                  {ordem.chave === c.chave && (
                    <span aria-hidden="true">{ordem.desc ? ' ▾' : ' ▴'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {linhas.map((f) => (
              <tr key={f.cnpj}>
                <td className="col-marcar">
                  <input
                    type="checkbox"
                    checked={selecionados.includes(f.cnpj)}
                    aria-label={`Comparar ${f.nome || f.cnpj}`}
                    onChange={() => onSelecionar(f.cnpj)}
                  />
                </td>
                {COLUNAS.map((c) => (
                  <td
                    key={c.chave}
                    className={[
                      c.tipo === 'texto' || c.tipo === 'data' ? '' : 'num',
                      c.sinal && f[c.chave] < 0 ? 'perda' : '',
                      c.sinal && f[c.chave] > 0 ? 'ganho' : '',
                    ].filter(Boolean).join(' ')}
                  >
                    {c.chave === 'nome' ? (
                      <button type="button" className="link-fundo" onClick={() => onAbrirFundo(f)}>
                        {f.nome || f.cnpj}
                      </button>
                    ) : (
                      formata(f[c.chave], c.tipo)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {linhas.length === 0 && (
        <p className="aviso-pesos">Nenhum fundo corresponde ao filtro “{filtro}”.</p>
      )}

      <p className="legenda-mini nota-unidade">
        Volatilidade e Sharpe são calculados no período selecionado. Liquidez e taxas são
        informadas por você — a CVM não as publica.
      </p>
    </div>
  )
}
