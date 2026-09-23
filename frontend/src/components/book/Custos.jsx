import { brl, num, pct } from '../../formato'
import { GradeKpis, Kpi, Ressalva, Vazio } from '../ui'

/**
 * Quanto o book paga por ano em taxa de administração.
 *
 * Só entra no total o fundo cuja taxa o usuário informou — e o cartão diz
 * sobre que fatia do patrimônio a conta foi feita. Um custo parcial
 * apresentado como total seria pior do que não mostrar custo nenhum: daria a
 * impressão de que o book é mais barato do que é.
 */
export default function Custos({ dados }) {
  const c = dados.custos || {}
  const total = dados.resumo.patrimonio

  if (!c.fundos_com_taxa) {
    return (
      <Vazio motivo="A base de cadastro da CVM posterior à Resolução 175 não publica taxa de administração. Preencha a coluna “Taxa adm. (%)” nas posições para ver o custo do book.">
        Nenhum fundo do book tem taxa de administração informada.
      </Vazio>
    )
  }

  const parcial = (c.cobertura ?? 1) < 0.999

  return (
    <>
      <GradeKpis colunas={3} compacto>
        <Kpi
          rotulo="Custo estimado por ano"
          valor={brl(c.custo_administracao_ano, 2)}
          nota={`taxa de administração sobre o patrimônio atual`}
        />
        <Kpi
          rotulo="Taxa média ponderada"
          valor={c.taxa_media_ponderada === null ? '—' : `${num(c.taxa_media_ponderada * 100, 2)}% a.a.`}
          nota="média pelo peso de cada fundo com taxa conhecida"
        />
        <Kpi
          rotulo="Custo como % do book"
          valor={pct(c.percentual_do_book, 2)}
          nota={
            parcial
              ? `calculado sobre ${pct(c.cobertura, 0)} do patrimônio`
              : 'sobre o patrimônio total'
          }
        />
      </GradeKpis>

      <div className="cartao">
        <h4>Custo por fundo</h4>
        <p className="legenda-mini">
          Taxa de administração aplicada ao patrimônio atual de cada posição — uma projeção
          de 12 meses mantendo o book como está hoje.
        </p>
        <table>
          <thead>
            <tr>
              <th scope="col">Fundo</th>
              <th scope="col" className="col-num">Taxa adm.</th>
              <th scope="col" className="col-num">Taxa perf.</th>
              <th scope="col" className="col-num">Custo estimado/ano</th>
              <th scope="col" className="col-num">% do book</th>
            </tr>
          </thead>
          <tbody>
            {(c.por_fundo || []).map((f) => {
              const fundo = dados.fundos.find((x) => x.cnpj === f.cnpj)
              return (
                <tr key={f.cnpj}>
                  <td>{fundo?.nome || f.cnpj}</td>
                  <td className="num">{num(f.taxa_administracao, 2)}%</td>
                  <td className="num">
                    {f.taxa_performance === null || f.taxa_performance === undefined
                      ? '—'
                      : `${num(f.taxa_performance, 2)}%`}
                  </td>
                  <td className="num destaque-suave">{brl(f.custo_ano, 2)}</td>
                  <td className="num">{pct(f.custo_ano / total, 3)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {(parcial || c.fundos_sem_taxa > 0) && (
        <Ressalva>
          {c.fundos_sem_taxa} {c.fundos_sem_taxa === 1 ? 'fundo está' : 'fundos estão'} sem taxa
          informada e {c.fundos_sem_taxa === 1 ? 'ficou' : 'ficaram'} de fora do total. O custo
          real do book é maior que o exibido.
        </Ressalva>
      )}
      <Ressalva>
        Taxa de performance não entra no custo estimado: ela depende do resultado futuro
        contra o benchmark, que o sistema não projeta.
      </Ressalva>
    </>
  )
}
