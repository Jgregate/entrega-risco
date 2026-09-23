import { Dado, Ressalva, Tag } from '../ui'

const AUSENTE = 'Informação não disponível'

/**
 * O fundo em palavras, depois de todos os indicadores.
 *
 * A ficha cadastral acima diz o que está registrado; esta seção diz o que o
 * fundo FAZ com o dinheiro. Os dois primeiros blocos (gestão e o resumo) saem
 * literalmente do cadastro da CVM; estratégia, classe de ativos, mercados,
 * risco e horizonte são leituras da classificação CVM/ANBIMA publicada — e a
 * ressalva no fim diz isso ao usuário, em vez de deixar parecer que a CVM
 * escreveu esse texto.
 *
 * O que não tem fonte aparece como "Informação não disponível", nunca como
 * texto plausível: descrição da gestora e nome do gestor de carteira não
 * existem em nenhum arquivo de dados abertos da CVM.
 */
export default function Sobre({ sobre, fundo }) {
  if (!sobre || Object.keys(sobre).length === 0) return null

  return (
    <div className="cartao">
      <h4>Sobre o fundo</h4>
      <p className="legenda-mini">
        Como o fundo busca gerar retorno, a partir do cadastro da CVM e da classificação
        ANBIMA da classe.
      </p>

      {sobre.resumo && <p className="sobre-resumo">{sobre.resumo}</p>}

      <div className="grupo-dados">
        <span className="grupo-titulo">Gestão</span>
        <div className="grade-dados">
          <Dado rotulo="Gestora" valor={sobre.gestora} ausente={AUSENTE} largo />
          <Dado
            rotulo="Descrição da gestora"
            valor={sobre.descricao_gestora}
            ausente={AUSENTE}
            largo
          />
          <Dado
            rotulo="Gestor ou equipe responsável"
            valor={sobre.equipe_gestao}
            ausente={AUSENTE}
          />
          <Dado
            rotulo="Diretor responsável perante a CVM"
            valor={sobre.responsavel}
            ausente={AUSENTE}
          />
          <Dado rotulo="Administrador" valor={sobre.administrador} ausente={AUSENTE} largo />
        </div>
      </div>

      <div className="grupo-dados">
        <span className="grupo-titulo">Estratégia</span>
        <div className="grade-dados">
          <Dado rotulo="Tipo de estratégia" valor={sobre.estrategia} ausente={AUSENTE} />
          <Dado
            rotulo="Principal classe de ativos"
            valor={sobre.classe_ativos}
            ausente={AUSENTE}
          />
          <Dado rotulo="Mercados de atuação" valor={sobre.mercados} ausente={AUSENTE} />
          <Dado
            rotulo="Investimento no exterior"
            valor={sobre.exterior}
            ausente={AUSENTE}
            largo
          />
          <Dado
            rotulo="Classificação ANBIMA"
            valor={sobre.classificacao_anbima}
            ausente={AUSENTE}
            largo
          />
          <Dado
            rotulo="Como o gestor implementa"
            valor={sobre.implementacao}
            ausente={AUSENTE}
            largo
          />
        </div>
      </div>

      <div className="grupo-dados">
        <span className="grupo-titulo">Risco e público</span>
        <div className="grade-dados">
          <Dado rotulo="Perfil de risco" valor={sobre.perfil_risco} ausente={AUSENTE} />
          <Dado
            rotulo="Benchmark de referência"
            valor={sobre.benchmark || fundo?.benchmark}
            ausente={AUSENTE}
          />
          <Dado
            rotulo="Horizonte de investimento sugerido"
            valor={sobre.horizonte}
            ausente={AUSENTE}
          />
          <Dado rotulo="Público-alvo" valor={sobre.publico_alvo} ausente={AUSENTE} />
        </div>
      </div>

      {sobre.caracteristicas?.length > 0 && (
        <div className="grupo-dados">
          <span className="grupo-titulo">Características da estrutura</span>
          <div className="tags">
            {sobre.caracteristicas.map((c) => (
              <Tag key={c}>{c}</Tag>
            ))}
          </div>
        </div>
      )}

      <Ressalva>
        Gestora, administrador, público-alvo, benchmark e características da estrutura vêm do
        cadastro da CVM. Estratégia, classe de ativos, mercados, perfil de risco e horizonte
        são leituras da classificação CVM/ANBIMA da classe — a CVM não publica descrição
        textual da gestora nem da estratégia, e por isso esses campos aparecem vazios.
      </Ressalva>
    </div>
  )
}
