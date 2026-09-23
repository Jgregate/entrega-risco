import { brl, dataCurta, inteiro, num } from '../../formato'
import { Dado, Ressalva } from '../ui'

/**
 * Ficha cadastral completa da classe.
 *
 * Diferente do cabeçalho, aqui TODO campo aparece, inclusive os que a CVM não
 * publica — com "não informado pela CVM" no lugar do valor. Um campo que some
 * deixa o usuário sem saber se ele não existe ou se o sistema não foi buscar.
 *
 * Descrição da gestora e descrição da estratégia não constam de nenhum dos
 * arquivos de dados abertos da CVM; o mesmo vale para taxa de administração,
 * taxa de performance e prazo de resgate na base pós-RCVM 175. Por isso a
 * ressalva no fim, e por isso as taxas são informadas pelo usuário no Book.
 */
export default function Cadastro({ fundo, cotistas }) {
  const semTaxas = !fundo.taxa_administracao && !fundo.taxa_performance

  return (
    <div className="cartao">
      <h4>Informações do fundo</h4>
      <p className="legenda-mini">
        Cadastro de classes e fundos da CVM (dados abertos), combinado com o informe
        diário mais recente.
      </p>

      <div className="grupo-dados">
        <span className="grupo-titulo">Identificação</span>
        <div className="grade-dados">
          <Dado rotulo="Nome do fundo" valor={fundo.nome} largo />
          <Dado rotulo="CNPJ da classe" valor={fundo.cnpj_fmt} />
          <Dado rotulo="Código CVM" valor={fundo.codigo_cvm} />
          <Dado rotulo="CNPJ do fundo" valor={fundo.cnpj_fundo} />
          <Dado rotulo="Tipo de fundo" valor={fundo.tipo_fundo} />
          <Dado rotulo="Tipo de classe" valor={fundo.tipo_classe} />
          <Dado rotulo="Status da classe" valor={fundo.situacao} />
        </div>
      </div>

      <div className="grupo-dados">
        <span className="grupo-titulo">Gestão e administração</span>
        <div className="grade-dados">
          <Dado rotulo="Gestora" valor={fundo.gestora} largo />
          <Dado rotulo="Administrador" valor={fundo.administrador} largo />
          <Dado rotulo="Diretor responsável" valor={fundo.diretor} />
          <Dado rotulo="Custodiante" valor={fundo.custodiante} />
          <Dado rotulo="Auditor" valor={fundo.auditor} largo />
          <Dado rotulo="Descrição da gestora" valor={null} largo />
          <Dado rotulo="Descrição da estratégia" valor={null} largo />
        </div>
      </div>

      <div className="grupo-dados">
        <span className="grupo-titulo">Classificação e política</span>
        <div className="grade-dados">
          <Dado rotulo="Categoria CVM" valor={fundo.classificacao_cvm} />
          <Dado rotulo="Categoria ANBIMA" valor={fundo.classificacao_anbima} largo />
          <Dado rotulo="Benchmark (indicador CVM)" valor={fundo.benchmark} />
          <Dado rotulo="Forma de condomínio" valor={fundo.forma_condominio} />
          <Dado rotulo="Classe de cotas" valor={fundo.classe_cotas} />
          <Dado rotulo="Tipo de investidor" valor={fundo.publico_alvo} />
          <Dado rotulo="Fundo exclusivo" valor={fundo.exclusivo} />
          <Dado rotulo="Previdência" valor={fundo.previdenciario} />
          <Dado rotulo="Investe 100% no exterior" valor={fundo.cem_por_cento_exterior} />
          <Dado rotulo="Tributação de longo prazo" valor={fundo.tributacao_longo_prazo} />
          <Dado rotulo="Entidade de investimento" valor={fundo.entidade_investimento} />
          <Dado rotulo="Classe ESG" valor={fundo.classe_esg} />
        </div>
      </div>

      <div className="grupo-dados">
        <span className="grupo-titulo">Datas e números</span>
        <div className="grade-dados">
          <Dado
            rotulo="Data da primeira cota"
            valor={fundo.data_inicio ? dataCurta(fundo.data_inicio) : null}
          />
          <Dado
            rotulo="Data de registro"
            valor={fundo.data_registro ? dataCurta(fundo.data_registro) : null}
          />
          <Dado
            rotulo="Constituição do fundo"
            valor={fundo.data_constituicao_fundo ? dataCurta(fundo.data_constituicao_fundo) : null}
          />
          <Dado
            rotulo="Adaptação à RCVM 175"
            valor={fundo.data_adaptacao_rcvm175 ? dataCurta(fundo.data_adaptacao_rcvm175) : null}
          />
          <Dado rotulo="Número de cotistas" valor={cotistas ? inteiro(cotistas) : null} />
          <Dado
            rotulo="PL no cadastro"
            valor={
              fundo.patrimonio_liquido_cad
                ? `${brl(Number(fundo.patrimonio_liquido_cad), 2)}${
                    fundo.data_patrimonio_cad ? ` (${dataCurta(fundo.data_patrimonio_cad)})` : ''
                  }`
                : null
            }
            largo
          />
        </div>
      </div>

      <div className="grupo-dados">
        <span className="grupo-titulo">Custos</span>
        <div className="grade-dados">
          <Dado
            rotulo="Taxa de administração"
            valor={fundo.taxa_administracao !== null && fundo.taxa_administracao !== undefined
              ? `${num(fundo.taxa_administracao)}% a.a.`
              : null}
          />
          <Dado
            rotulo="Taxa de performance"
            valor={fundo.taxa_performance !== null && fundo.taxa_performance !== undefined
              ? `${num(fundo.taxa_performance)}%`
              : null}
          />
        </div>
      </div>

      {semTaxas && (
        <Ressalva>
          A base de cadastro da CVM posterior à Resolução 175 não publica taxa de
          administração, taxa de performance nem prazo de resgate. Esses três campos podem
          ser informados por você ao adicionar o fundo ao <strong>Meu Book</strong>, onde
          entram no cálculo de custo e de liquidez da carteira.
        </Ressalva>
      )}
    </div>
  )
}
