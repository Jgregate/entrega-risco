import { dataCurta } from '../../formato'
import { Tag } from '../ui'

/**
 * Cabeçalho da análise: quem é o fundo, em uma olhada.
 *
 * Só as etiquetas que existem de verdade no cadastro aparecem — uma tag
 * "não informado" não ajuda ninguém a identificar o fundo, e o detalhe
 * completo (com as lacunas explícitas) fica na ficha cadastral no fim da
 * página.
 */
export default function Identificacao({ fundo, benchmark }) {
  const tags = [
    fundo.classificacao_cvm,
    fundo.classificacao_anbima,
    fundo.forma_condominio && `Condomínio ${fundo.forma_condominio.toLowerCase()}`,
    fundo.publico_alvo,
    fundo.previdenciario === 'Sim' && 'Previdência',
    fundo.exclusivo === 'Sim' && 'Exclusivo',
    fundo.cem_por_cento_exterior === 'Sim' && '100% exterior',
  ].filter(Boolean)

  return (
    <div className="cartao identificacao">
      <div className="identificacao-topo">
        <div>
          <div className="olho">{fundo.gestora || 'Gestora não informada'}</div>
          <h2>{fundo.nome}</h2>
          <p className="legenda-mini identificacao-meta">
            CNPJ {fundo.cnpj_fmt}
            {fundo.codigo_cvm && <> · Código CVM {fundo.codigo_cvm}</>}
            {fundo.data_inicio && <> · Primeira cota em {dataCurta(fundo.data_inicio)}</>}
          </p>
        </div>

        <div className="identificacao-situacao">
          <span className="rotulo">Situação da classe</span>
          <strong>{fundo.situacao || '—'}</strong>
          <span className="legenda-mini">
            Benchmark: {benchmark?.rotulo || '—'}
            {benchmark && !benchmark.do_cadastro && fundo.benchmark && (
              <>
                {' '}
                <span title={`A CVM registra "${fundo.benchmark}", que não é uma série comparável.`}>
                  (CVM: {fundo.benchmark})
                </span>
              </>
            )}
          </span>
        </div>
      </div>

      {tags.length > 0 && (
        <div className="tags">
          {tags.map((t) => (
            <Tag key={t}>{t}</Tag>
          ))}
        </div>
      )}
    </div>
  )
}
