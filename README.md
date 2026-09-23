# Inteli Finance · Plataforma de Fundos de Investimento

Plataforma exclusivamente voltada para análise de fundos de investimento e montagem de
carteiras de fundos. Dados abertos da CVM (cadastro, informes diários e composição de
carteira), CDI/Selic/IPCA do Banco Central e índices de mercado do Yahoo Finance.

Backend em **FastAPI/Python**, front em **React (Vite)**, organizado em três áreas:

| Área | O que traz |
|---|---|
| **Visão Geral** | Resumo do book do usuário e descoberta: busca de fundos e ranking dos maiores retornos. |
| **Analisar Fundos** | Análise individual completa de um fundo — identificação, KPIs, rentabilidade, tabela mensal, risco/volatilidade, drawdown, consistência, patrimônio, composição de carteira e ficha cadastral. |
| **Meu Book** | Onde o usuário monta e acompanha sua carteira de fundos — alocação, risco consolidado, liquidez, contribuição de retorno/risco, custos, tributação estimada e comparação entre fundos. |

---

## Como rodar

Precisa de **Python 3.10+** e **Node 18+**. Dois terminais.

### 1. Backend

**Windows (PowerShell)** — chamando o Python do venv direto, sem `activate`, que é onde
a política de execução do PowerShell costuma atrapalhar:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Se preferir ativar o ambiente: `.\.venv\Scripts\Activate.ps1` (o `.\` é obrigatório). Se o
PowerShell bloquear o script, rode antes
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

**macOS / Linux:**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API em `http://127.0.0.1:8000` · documentação interativa em `http://127.0.0.1:8000/docs`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Aplicação em `http://localhost:5173`. O Vite já encaminha `/api` para o FastAPI.

### Testes

```powershell
cd backend
.venv\Scripts\python.exe -m pytest      # Windows
# pytest                                # macOS / Linux com o venv ativo
```

Testes cobrem o núcleo de cálculo com dados sintéticos (sem rede): retorno acumulado
composto (não somado), drawdown e recuperação, consistência mensal e frente ao
benchmark, Sharpe/Sortino sobre o CDI, anualização por tempo de calendário (não por
contagem de pregões — um fundo não reporta todo dia útil), rentabilidade time-weighted
do book (aporte não vira valorização), contribuição de retorno e de risco (MCTR, que
fecha exatamente na volatilidade da carteira), tabela regressiva de IR e o filtro de
cotas zeradas/negativas nos informes da CVM.

---

## Fundos — o que a análise individual calcula

A unidade do sistema é a **classe de fundo** (`CNPJ_FUNDO_CLASSE`), que é a granularidade
do informe diário da CVM desde a Resolução CVM 175. A série de referência é sempre a
**cota**, nunca o patrimônio: cota já é líquida de taxas e imune a captação/resgate, o
que patrimônio não é.

| Bloco | Conteúdo |
|---|---|
| **Identificação** | Nome, gestora, CNPJ, código CVM, classificação CVM/ANBIMA, benchmark do cadastro, situação da classe. |
| **KPIs principais** | PL atual, PL médio 12M, cotistas, rentabilidade no período e em 12M, volatilidade, Sharpe, drawdown atual, retorno desde o início. |
| **Rentabilidade** | Retorno acumulado vs. benchmark (indexado a zero), retorno por janela rápida (1m/3m/6m/12m/24m/36m/5a/desde o início) e tabela de rentabilidade histórica mensal (ano × mês, com escala de cor divergente). |
| **Risco** | Rentabilidade/volatilidade anualizadas, Sharpe, Sortino, drawdown máximo, excesso sobre o benchmark, % de meses acima do benchmark, consistência em janelas móveis de 12 meses. |
| **Drawdown** | Atual, máximo, data do fundo, tempo de recuperação, e o histórico completo em gráfico de área. |
| **Consistência** | Meses positivos/negativos, maior sequência de cada lado, e uma faixa mês a mês com escala divergente. |
| **Patrimônio** | Evolução do PL, patrimônio total aplicado e número de cotistas. |
| **Composição** | Distribuição por classe de ativo (Renda Fixa, Ações, Crédito, Derivativos, Fundos, Exterior, Caixa), maiores posições, maiores emissores e exposição por país — do formulário CDA da CVM. |
| **Cadastro** | Ficha institucional completa. Campo que a CVM não publica aparece como lacuna explícita, nunca como número inventado — é o caso de taxa de administração/performance e prazo de resgate na base pós-RCVM 175: eles são informados pelo usuário no Book. |
| **Sobre o fundo** | Leitura qualitativa que fecha a página: gestora, administrador e público-alvo (registrais), e estratégia, classe de ativos, mercados, perfil de risco e horizonte sugerido — estes últimos traduzidos da classificação CVM/ANBIMA da classe, com a origem declarada na própria seção. Descrição da gestora e nome do gestor de carteira não existem em nenhum arquivo de dados abertos e aparecem como "Informação não disponível". |

Período de análise: janelas rápidas (1 mês a "desde o início", até 10 anos de histórico)
ou um intervalo personalizado por data. Todo gráfico e indicador reage ao período
selecionado.

## Ranking — maiores retornos do período

A Visão Geral traz o Top 10 por retorno acumulado, com dois filtros: a **categoria**
(Renda Fixa, Ações, Multimercado, Cambiais, FII, ETF, Previdência, FIDC, FIP e Fiagro —
derivada do tipo de fundo e da classificação CVM/ANBIMA do cadastro) e a **janela**
(1 mês, 6 meses, 12, 24 ou 36 meses). Retorno, volatilidade, Sharpe e drawdown máximo
saem todos do mesmo recorte selecionado.

Duas ressalvas que a interface também declara: as métricas do ranking vêm das cotas
**mensais** (varrer 25 mil fundos em série diária custaria minutos por consulta — os
números finos estão na análise individual), e o Sharpe só é calculado em janelas de 12
meses ou mais, porque anualizar um período curto produziria um número que se lê como
projeção. A fonte é o informe diário, que cobre as classes de fundos financeiros: FII,
ETF, Fiagro e boa parte dos FIDC/FIP não reportam nele e por isso saem com poucos
fundos ou vazios.

## Book — o que a consolidação calcula

O usuário informa a posição em cada fundo (quantidade de cotas **ou** valor investido,
mais data de entrada, preço médio, liquidez e taxas — todos opcionais além do primeiro
par) e a plataforma consolida:

- **Rentabilidade time-weighted** — aporte novo não vira valorização do dia; é assim que
  o gráfico do book não dá um salto artificial quando um fundo é adicionado.
- **Alocação** por classe de ativo e por gestora, com concentração (índice de
  Herfindahl).
- **Risco consolidado** — volatilidade da carteira (já líquida do efeito de
  diversificação), Sharpe, drawdown e matriz de correlação entre os fundos.
- **Liquidez** — patrimônio por faixa de prazo de resgate (D+0 a acima de D+90),
  informado pelo usuário.
- **Contribuição de retorno** — decomposição aritmética por peso diário de cada fundo,
  com o resíduo de capitalização explicitado (não rateado).
- **Contribuição de risco** — MCTR (marginal contribution to risk), que soma
  exatamente a volatilidade da carteira e por isso é o único jeito honesto de responder
  "de onde vem o risco" levando correlação em conta.
- **Custos** — custo anual estimado a partir da taxa de administração informada,
  com a cobertura (% do book com taxa conhecida) sempre explícita.
- **Tributação** — IR estimado pela tabela regressiva legal, aplicada ao prazo desde a
  data de entrada informada. É estimativa declarada como tal: não considera come-cotas
  já recolhido, prejuízo a compensar, nem substitui o informe do administrador.
- **Comparação** — até vários fundos lado a lado, com a curva de cada um no mesmo eixo
  indexado a zero.

O book persiste apenas no `localStorage` do navegador (posição informada, nunca valor
calculado); não há login. Isso reflete a fronteira de dados do sistema: tudo que a CVM
publica é buscado ao vivo, e só o que ela não publica é responsabilidade do usuário
informar.

---

## API

Prefixo `/api/fundos/*` (análise individual) e `/api/book/*` (consolidação).

| Endpoint | O que faz |
|---|---|
| `GET /api/fundos/periodos?escopo=` | Catálogo de janelas rápidas (`escopo=ranking` traz o subconjunto que o ranking calcula). |
| `GET /api/fundos/categorias` | Catálogo de categorias de fundo (filtro do ranking). |
| `GET /api/fundos/benchmarks` | Catálogo de benchmarks (CDI, Ibovespa, IPCA, Selic, S&P 500, Dólar). |
| `GET /api/fundos/buscar?q=` | Busca por nome, CNPJ, código CVM ou gestora. |
| `GET /api/fundos/top10?periodo=&categoria=` | Top 10 por retorno acumulado na janela escolhida, com volatilidade, Sharpe e drawdown da mesma janela; filtra fundos com poucos cotistas ou saltos de cota suspeitos. |
| `GET /api/fundos/cadastro?cnpj=` | Ficha institucional completa da classe. |
| `GET /api/fundos/analise?cnpj=&periodo=&benchmark=&inicio=&fim=` | Payload completo da análise individual. |
| `GET /api/fundos/composicao?cnpj=` | Composição de carteira do mês mais recente do CDA. |
| `POST /api/fundos/atualizar` | Força o reprocessamento do cadastro e dos meses ainda sujeitos a revisão da CVM. |
| `GET /api/fundos/status` | Data/hora do último download. |
| `POST /api/book/analise` | Consolida uma lista de posições numa carteira única. |

Ver `http://127.0.0.1:8000/docs` para o schema completo de cada payload.

---

## Fontes de dados e cache

| Fonte | O que fornece | Cache |
|---|---|---|
| `dados.cvm.gov.br/dados/FI/CAD` | Cadastro de fundo/classe/subclasse — nome, gestora, administrador, classificação, benchmark declarado. | SQLite, TTL 6h. |
| `dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO` | Cota, PL, patrimônio total, captação, resgate e cotistas por pregão. | SQLite; meses fechados antigos nunca são reparseados, só os 2 meses mais recentes são revistos periodicamente. |
| `dados.cvm.gov.br/dados/FI/DOC/CDA` | Composição de carteira (classe de ativo, posições, emissores, países). | SQLite; só o mês mais recente é mantido — carteira é uma foto, não uma série. |
| `api.bcb.gov.br` (SGS) | CDI (série 12), Selic (série 11), IPCA (série 433). | Memória, TTL 6h. |
| Yahoo Finance | Ibovespa, S&P 500, Dólar. | Memória, TTL 6h. |

O que a CVM **não publica** nos dados abertos pós-Resolução 175 — taxa de administração,
taxa de performance e prazo de resgate — nunca é preenchido com um valor inventado.
Esses campos aparecem como lacuna na análise individual e são informados pelo usuário
no Book, onde entram no cálculo de custo, tributação e liquidez.

Cada mês do informe diário chega num ZIP com todos os fundos juntos (~500 mil linhas).
Em vez de reparsear isso a cada consulta, o resultado já parseado fica em SQLite
(`backend/data/fundos_cache.db`, modo WAL) — meses fechados antigos nunca são
reprocessados; a leitura da série diária de um fundo específico é indexada por
`(cnpj, ano, mes)` para não custar mais que os meses realmente pedidos.

### Decisões de cálculo

- **Anualização por tempo de calendário, não por contagem de pregões.** Um fundo não
  reporta cota todo dia útil; uma janela de "12 meses" costuma trazer 245–251 pregões, e
  um corte em 252 apagaria Sharpe e rentabilidade anualizada justamente na janela mais
  usada da interface. `(1+acumulado)^(365,25/dias_corridos) - 1`.
- **Sharpe/Sortino no padrão do mercado de fundos brasileiro**: excesso anualizado sobre
  o CDI dividido pela volatilidade (total no Sharpe, só das quedas no Sortino) —
  comparável com o que a lâmina do fundo publica.
- **Cota zero ou negativa nunca é dado válido.** A CVM publica isso ocasionalmente (visto
  em produção: um `CNPJ_FUNDO_CLASSE` reportando `VL_QUOTA=0` por semanas, artefato de
  migração de classe), e sem filtro esse zero é tratado como preço real — derruba a
  posição a zero no valor do book e produz um salto de centenas de % quando o valor
  volta. Filtrado na origem (`_read_informe`), antes de qualquer cálculo.
- **"Desde o início" não usa a data de registro da classe como atalho.** Um
  `CNPJ_FUNDO_CLASSE` pode ter informe diário publicado antes da própria data de
  registro no cadastro; confiar nela já truncou incorretamente o histórico de um fundo
  em produção. A busca sempre vai até o teto de histórico (10 anos), cacheado depois da
  primeira consulta.
- **Book: rentabilidade time-weighted.** Retorno do dia = `(V_t − aporte_t)/V_{t-1} − 1`;
  dinheiro que entra não conta como valorização daquele dia.
- **Preços do Yahoo Finance**: fechamento ajustado.

---

## Estrutura

```
backend/
  app/
    main.py              endpoints legados de VaR/risco de carteira (ver nota abaixo)
    fundos/
      router.py           endpoints /api/fundos/* e /api/book/*
      cadastro.py          cadastro CVM (fundo + classe + subclasse), uma linha por classe
      cvm_data.py           registro, busca, serie diaria, ranking Top N, cache SQLite
      carteira.py            composicao de carteira (CDA) - agregado por fundo
      indices.py               benchmarks diarios (CDI, Ibovespa, IPCA, Selic...)
      analytics.py               metricas de performance/risco de um fundo (modulo puro)
      sobre.py                    ficha qualitativa do fundo a partir do cadastro (modulo puro)
      book.py                     consolidacao do book (TWR, MCTR, custos, tributacao)
      metrics.py                  metricas mensais legadas (top10/ranking)
      schemas.py                  validacao de entrada do book (pydantic)
  tests/
frontend/
  src/
    App.jsx              as tres areas e o estado que atravessa (fundo aberto, book)
    api.js               cliente HTTP
    book.js              persistencia do book no localStorage
    formato.js            formatacao pt-BR, tokens de cor e paletas validadas
    styles.css             guia de estilos (Inteli Finance)
    components/
      ui.jsx, grafico.jsx  primitivas compartilhadas (KPI, tooltip, eixos...)
      BuscaFundos.jsx, SeletorPeriodo.jsx, VisaoGeral.jsx
      fundo/                 telas da analise individual
      book/                  telas do book consolidado
```

**Nota sobre `app/main.py`**: os endpoints de VaR/risco de carteira de ações
(`/api/analise`, `/api/var/empirico`) da versão anterior deste projeto continuam no
backend por não quebrar integrações existentes, mas **não fazem mais parte da
interface** — a plataforma é hoje exclusivamente de fundos de investimento, conforme o
escopo do produto.

### Módulo Fundos: contrato entre as camadas

```
cvm_data.py    rede + SQLite → DataFrames de cota/PL/cotistas por dia
carteira.py    rede + SQLite → composição agregada por classe de ativo/emissor/país
analytics.py   DataFrame de retornos → dict de métricas (puro, sem rede/banco, testável)
book.py        posições + séries → consolidação (puro, mesma natureza de analytics.py)
router.py      orquestra os quatro acima e monta o payload JSON de cada endpoint
```

Trocar a fonte de dados (outro provedor, outro formato de arquivo da CVM) não exige
tocar em `analytics.py` nem `book.py`: os dois só conhecem Series/DataFrames do pandas.

---

## Identidade visual

Paleta base: `#000000` `#ffffff` `#ff4545` `#ad2727` `#130000` `#580000` `#360100`
`#850000` `#c00000`. Tipografia **Poppins** (Google Fonts). Tokens em
`frontend/src/styles.css`.

As paletas de gráfico (categórica de 6 cores e rampa ordinal vermelha) são extensões
validadas dessa base — cada uma passou pelas checagens de acessibilidade (banda de
luminosidade, piso de croma, separação sob protanopia/deuteranopia, piso de visão
normal, contraste) contra a superfície escura da aplicação; ver os comentários em
`frontend/src/formato.js`.

---

## Notas

- O yfinance/Yahoo Finance é API não oficial e ocasionalmente aplica rate limit; as
  chamadas de benchmark ficam em cache de 6h.
- A primeira análise de um fundo (ou a primeira composição de carteira do mês) pode
  levar alguns minutos, porque processa o informe diário ou o CDA da CVM inteiros pela
  primeira vez; consultas seguintes são instantâneas graças ao cache em SQLite.

### Se o pip tentar compilar o pandas do fonte

Sintoma: `Preparing metadata (pyproject.toml) ... error` com `meson` e `Could not parse
vswhere.exe output`. Isso acontece quando **não existe wheel pronta** do pandas para a sua versão
do Python — normalmente uma versão muito nova (3.13+ recém-lançada). O pip então tenta compilar,
e para isso precisaria do Visual Studio Build Tools.

Duas saídas, na ordem de preferência:

1. As versões deste `requirements.txt` são faixas abertas justamente para o pip escolher uma wheel
   compatível. Rode `python --version` e confira; se já estiver com faixas abertas e ainda assim
   compilar, vá para a opção 2.
2. Instale o **Python 3.12** (`winget install Python.Python.3.12`) e crie o venv com ele:
   `py -3.12 -m venv .venv`. Toda a stack tem wheel para 3.12.
