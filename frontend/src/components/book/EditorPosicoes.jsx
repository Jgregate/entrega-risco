import { useState } from 'react'
import { posicaoIncompleta } from '../../book'
import BuscaFundos from '../BuscaFundos'
import { Ressalva, Vazio } from '../ui'

/**
 * Onde o book é montado.
 *
 * A regra de preenchimento é a mesma do backend, e a interface a torna
 * explícita: basta informar a QUANTIDADE DE COTAS ou o VALOR INVESTIDO. Os
 * outros campos refinam o cálculo — data de entrada dá preço médio e prazo
 * para o IR; preço médio dá o resultado financeiro; liquidez e taxas não
 * existem nos dados abertos da CVM e só chegam por aqui.
 */
const CAMPOS = [
  {
    chave: 'quantidade_cotas',
    rotulo: 'Cotas',
    tipo: 'number',
    passo: 'any',
    dica: 'Quantidade de cotas do seu extrato.',
  },
  {
    chave: 'valor_investido',
    rotulo: 'Valor (R$)',
    tipo: 'number',
    passo: '0.01',
    dica: 'Use no lugar das cotas se não souber a quantidade.',
  },
  {
    chave: 'data_entrada',
    rotulo: 'Entrada',
    tipo: 'date',
    dica: 'Data da aplicação. Sem ela não há preço médio nem estimativa de IR.',
  },
  {
    chave: 'preco_medio',
    rotulo: 'Preço médio',
    tipo: 'number',
    passo: 'any',
    dica: 'Custo médio da cota. Sem ele, vale a cota da data de entrada.',
  },
  {
    chave: 'liquidez_dias',
    rotulo: 'Resgate D+',
    tipo: 'number',
    passo: '1',
    dica: 'Prazo de resgate em dias. Não é publicado pela CVM.',
  },
  {
    chave: 'taxa_administracao',
    rotulo: 'Taxa adm. (%)',
    tipo: 'number',
    passo: '0.01',
    dica: 'Taxa de administração ao ano. Não é publicada pela CVM.',
  },
  {
    chave: 'taxa_performance',
    rotulo: 'Taxa perf. (%)',
    tipo: 'number',
    passo: '0.01',
    dica: 'Taxa de performance sobre o que exceder o benchmark.',
  },
]

export default function EditorPosicoes({ posicoes, onMudar, onRemover, onAdicionar }) {
  const [adicionando, setAdicionando] = useState(false)

  const jaTem = (cnpj) => posicoes.some((p) => p.cnpj === cnpj)

  return (
    <div className="cartao">
      <div className="cartao-cabecalho">
        <div>
          <h4>Posições do book</h4>
          <p className="legenda-mini">
            Informe a quantidade de cotas <strong>ou</strong> o valor investido em cada fundo.
            O resto é opcional e deixa o cálculo mais preciso.
          </p>
        </div>
        <button
          type="button"
          className="btn-texto btn-estreito"
          onClick={() => setAdicionando((a) => !a)}
        >
          {adicionando ? 'Fechar busca' : '+ Adicionar fundo'}
        </button>
      </div>

      {adicionando && (
        <div className="busca-embutida">
          <BuscaFundos
            autoFoco
            rotulo="Qual fundo entra no book?"
            onEscolher={(f) => {
              if (!jaTem(f.cnpj)) onAdicionar(f)
              setAdicionando(false)
            }}
          />
        </div>
      )}

      {posicoes.length === 0 ? (
        <Vazio motivo="Use “Adicionar fundo” acima, ou o botão do book na tela de análise de um fundo.">
          Seu book está vazio.
        </Vazio>
      ) : (
        <div className="rolagem-horizontal">
          <table className="tabela-posicoes">
            <thead>
              <tr>
                <th scope="col">Fundo</th>
                {CAMPOS.map((c) => (
                  <th key={c.chave} scope="col" className="col-num" title={c.dica}>
                    {c.rotulo}
                  </th>
                ))}
                <th scope="col" aria-label="Remover" />
              </tr>
            </thead>
            <tbody>
              {posicoes.map((p, i) => (
                <tr key={p.cnpj} className={posicaoIncompleta(p) ? 'linha-incompleta' : undefined}>
                  <td className="celula-fundo">
                    <span className="posicao-nome">{p.nome || p.cnpj}</span>
                    <span className="posicao-cnpj">{p.cnpj}</span>
                  </td>
                  {CAMPOS.map((c) => (
                    <td key={c.chave} className="celula-campo">
                      <input
                        type={c.tipo}
                        step={c.passo}
                        min={c.tipo === 'number' ? '0' : undefined}
                        value={p[c.chave] ?? ''}
                        aria-label={`${c.rotulo} — ${p.nome || p.cnpj}`}
                        title={c.dica}
                        onChange={(e) => onMudar(i, c.chave, e.target.value)}
                      />
                    </td>
                  ))}
                  <td>
                    <button
                      type="button"
                      className="btn-icone"
                      aria-label={`Remover ${p.nome || p.cnpj}`}
                      onClick={() => onRemover(i)}
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {posicoes.some(posicaoIncompleta) && (
        <Ressalva>
          As linhas destacadas ainda não têm quantidade de cotas nem valor investido, então
          ficam de fora da consolidação.
        </Ressalva>
      )}

      <Ressalva>
        O book fica salvo apenas neste navegador. Cota, patrimônio e rentabilidade são
        sempre recalculados com os dados da CVM — nada de valor é gravado.
      </Ressalva>
    </div>
  )
}
