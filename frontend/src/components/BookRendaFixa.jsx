import { useEffect, useMemo, useState } from 'react'
import ParametrosRisco from './ParametrosRisco'
import { titulosDisponiveis } from '../api'
import { brl, dataCurta, haQuantoTempo, num, pct } from '../formato'

/** Dias corridos entre a data informada e hoje, sem passar pelo backend. */
const diasDePosse = (iso) =>
  Math.max(0, Math.round((Date.now() - new Date(`${iso}T00:00:00`)) / 86_400_000))

/**
 * A taxa do Tesouro Selic no arquivo é o SPREAD sobre a Selic, não um
 * rendimento absoluto como nos demais papéis. Mostrar "0,04%" ao lado de um
 * prefixado a "13,52%" sem essa distinção induziria a erro.
 */
const rotuloTaxa = (t) =>
  t.tipo_slug === 'tesouro_selic' ? `SELIC + ${pct(t.taxa_venda)}` : `${pct(t.taxa_venda)} a.a.`

export default function BookRendaFixa({
  params,
  setParams,
  onCalcular,
  carregando,
  mostrarParametros = true,
}) {
  const [titulos, setTitulos] = useState([])
  const [dataBase, setDataBase] = useState(null)
  const [erro, setErro] = useState(null)
  const [buscando, setBuscando] = useState(true)

  const [escolhido, setEscolhido] = useState('')
  const [quantidade, setQuantidade] = useState(1)
  const [puAquisicao, setPuAquisicao] = useState('')
  const [dataAquisicao, setDataAquisicao] = useState('')

  const posicoes = params.rendaFixa

  useEffect(() => {
    let ativo = true
    titulosDisponiveis()
      .then((r) => {
        if (!ativo) return
        setTitulos(r.titulos)
        setDataBase(r.data_base)
      })
      .catch((e) => ativo && setErro(e.message))
      .finally(() => ativo && setBuscando(false))
    return () => {
      ativo = false
    }
  }, [])

  const jaNoBook = useMemo(() => new Set(posicoes.map((p) => p.titulo_id)), [posicoes])

  // a API já devolve ordenado por tipo e vencimento; aqui só agrupamos
  const grupos = useMemo(() => {
    const mapa = new Map()
    for (const t of titulos) {
      if (jaNoBook.has(t.id)) continue
      if (!mapa.has(t.tipo)) mapa.set(t.tipo, [])
      mapa.get(t.tipo).push(t)
    }
    return [...mapa.entries()]
  }, [titulos, jaNoBook])

  const catalogo = useMemo(() => new Map(titulos.map((t) => [t.id, t])), [titulos])

  // o papel escolhido no primeiro container é quem preenche os outros três
  const papel = escolhido ? catalogo.get(escolhido) : null

  /**
   * Trocar o papel repõe o PU de aquisição com o PU de venda de hoje. Ele
   * continua obrigatório e editável — quem comprou em outra data digita o PU
   * daquela data por cima; quem está montando a posição agora não digita nada.
   */
  const escolher = (id) => {
    setEscolhido(id)
    const t = catalogo.get(id)
    setPuAquisicao(t ? String(t.pu_venda) : '')
  }

  const adicionar = () => {
    if (!podeAdicionar) return
    setParams((p) => ({
      ...p,
      rendaFixa: [
        ...p.rendaFixa,
        {
          titulo_id: escolhido,
          quantidade: Number(quantidade),
          pu_aquisicao: Number(puAquisicao),
          // omitida, a marcação trata a posição como montada na data base e o
          // P&L nasce zerado — é o comportamento de quem está comprando agora
          ...(dataAquisicao ? { data_aquisicao: dataAquisicao } : {}),
        },
      ],
    }))
    setEscolhido('')
    setQuantidade(1)
    setPuAquisicao('')
    setDataAquisicao('')
  }

  const remover = (i) =>
    setParams((p) => ({ ...p, rendaFixa: p.rendaFixa.filter((_, j) => j !== i) }))

  const podeAdicionar =
    escolhido !== '' && Number(quantidade) > 0 && Number(puAquisicao) > 0

  const valido = posicoes.length > 0 && params.inicio < params.fim

  return (
    <div className={mostrarParametros ? 'book' : undefined}>
      <div className="cartao">
        <h3>Títulos públicos</h3>
        <p className="legenda">
          Universo do Tesouro Direto no último dia útil publicado
          {dataBase ? <strong> · {dataCurta(dataBase)}</strong> : null}. A marcação usa o{' '}
          <strong>PU de venda</strong> — o preço pelo qual o Tesouro recompra o papel. Escolher o
          papel já preenche taxa, valor e vencimento: esses três campos vêm da fonte e não são
          editáveis.
        </p>

        {erro && <div className="erro">{erro}</div>}
        {buscando && <p className="legenda-mini">Carregando títulos…</p>}

        {!buscando && !erro && (
          <>
            <div className="dupla">
              <div className="campo">
                <label>Título</label>
                <select value={escolhido} onChange={(e) => escolher(e.target.value)}>
                  <option value="">selecione um papel…</option>
                  {grupos.map(([tipo, lista]) => (
                    <optgroup key={tipo} label={tipo}>
                      {lista.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.rotulo}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
              <div className="campo">
                <label>Taxa de rendimento</label>
                <input
                  className="travado"
                  readOnly
                  tabIndex={-1}
                  value={papel ? rotuloTaxa(papel) : '—'}
                />
              </div>
            </div>

            <div className="dupla">
              <div className="campo">
                <label>Valor do título (PU de venda)</label>
                <input
                  className="travado"
                  readOnly
                  tabIndex={-1}
                  value={papel ? brl(papel.pu_venda, 2) : '—'}
                />
              </div>
              <div className="campo">
                <label>Vencimento</label>
                <input
                  className="travado"
                  readOnly
                  tabIndex={-1}
                  value={papel ? dataCurta(papel.vencimento) : '—'}
                />
              </div>
            </div>

            <div className="dupla">
              <div className="campo">
                <label>Quantidade</label>
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={quantidade}
                  onChange={(e) => setQuantidade(e.target.value)}
                />
              </div>
              <div className="campo">
                <label>PU de aquisição</label>
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={puAquisicao}
                  onChange={(e) => setPuAquisicao(e.target.value)}
                />
              </div>
            </div>

            <div className="dupla">
              <div className="campo">
                <label>Data de aquisição</label>
                <input
                  type="date"
                  max={dataBase || undefined}
                  value={dataAquisicao}
                  onChange={(e) => setDataAquisicao(e.target.value)}
                />
              </div>
              <div className="campo">
                <label>Tempo de posse</label>
                <input
                  className="travado"
                  readOnly
                  tabIndex={-1}
                  value={dataAquisicao ? haQuantoTempo(diasDePosse(dataAquisicao)) : '—'}
                />
              </div>
            </div>

            <p className="legenda-mini">
              A data de aquisição alimenta a aba <strong>Rastreabilidade</strong>: é ela que
              responde “comprei este título há quantos dias, quanto ele valorizou e qual a
              projeção”. Sem ela, a posição é tratada como montada na data base e o P&amp;L nasce
              zerado.
            </p>

            <button className="btn-texto" onClick={adicionar} disabled={!podeAdicionar}>
              + adicionar ao book
            </button>
          </>
        )}

        {posicoes.length > 0 && (
          <table className="tabela-book" style={{ marginTop: 14 }}>
            <thead>
              <tr>
                <th>Papel</th>
                <th style={{ width: 70, textAlign: 'right' }}>Qtde.</th>
                <th style={{ width: 96 }}>Vencimento</th>
                <th style={{ width: 96 }}>Aquisição</th>
                <th style={{ width: 92, textAlign: 'right' }}>PU aquis.</th>
                <th style={{ width: 38 }} />
              </tr>
            </thead>
            <tbody>
              {posicoes.map((pos, i) => {
                const t = catalogo.get(pos.titulo_id)
                return (
                  <tr key={pos.titulo_id}>
                    <td style={{ color: '#fff' }}>
                      {t ? t.rotulo : pos.titulo_id}
                      <span className="legenda-mini" style={{ display: 'block', margin: 0 }}>
                        {t ? t.tipo : ''}
                      </span>
                    </td>
                    <td className="num">{num(pos.quantidade)}</td>
                    <td className="num">{t ? dataCurta(t.vencimento) : '—'}</td>
                    <td className="num">
                      {pos.data_aquisicao ? dataCurta(pos.data_aquisicao) : 'data base'}
                    </td>
                    <td className="num">{brl(pos.pu_aquisicao, 2)}</td>
                    <td>
                      <button
                        className="btn-icone"
                        onClick={() => remover(i)}
                        title="Remover título"
                      >
                        −
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {mostrarParametros && (
        <ParametrosRisco
          params={params}
          setParams={setParams}
          onCalcular={onCalcular}
          carregando={carregando}
          valido={valido}
          mostrarValorCarteira={false}
          aviso="O valor da carteira sai da marcação a mercado (quantidade × PU de venda), não de um total informado."
        />
      )}
    </div>
  )
}
