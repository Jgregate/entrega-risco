# Risco · Painel de risco de carteira

Aplicação de risco de carteira com ações (preços do `yfinance`), títulos públicos (preços do
Tesouro Transparente) e taxa livre de risco do Banco Central. Célula de Risco — Inteli Finance.

Backend em **FastAPI/Python**, front em **React (Vite)**, organizado em cinco abas:

| Aba | O que traz |
|---|---|
| **VaRs** | Os três métodos lado a lado — empírico, paramétrico e EWMA — com as curvas no tempo, distribuição, histórico de violações, violações por ano, teste de aderência e evolução da carteira. |
| **Risco e retorno** | Sharpe e Sortino contra a Selic, curva da carteira vs. Selic, índices móveis e drawdown. |
| **Book** | Onde a carteira é montada e todos os parâmetros são manipulados. Um seletor **Ações \| Renda Fixa \| Ambos** escolhe a classe: em ações, ativos, peso e valor nominal; em renda fixa, títulos do Tesouro Direto com quantidade, data e PU de aquisição, e a marcação a mercado com P&L; em ambos, os dois books na mesma análise. Período, confiança, horizonte e janela do backtest valem para todas. |
| **Rastreabilidade** | Da compra até a projeção. Responde “comprei há X dias, quanto valorizou ou desvalorizou, e qual a projeção” para cada posição e para o book inteiro — nas três classes. Traço por posição: data e preço de compra, tempo de posse em dias corridos e em pregões, valorização em reais, em percentual e anualizada, pico, fundo e queda desde o pico. Projeção: valor esperado pela deriva da janela e piso/teto pelos três VaRs, com o nível de confiabilidade declarado. Portada do playground `Playground-Portifolio-Finance` (Streamlit), reescrita nesta arquitetura. |
| **Fundos** | Busca (ou Top 10 por retorno) entre fundos de investimento ativos na CVM, com crescimento acumulado vs. CDI, heatmap de retornos mensais, comparativo com Ibovespa e Sharpe/Sortino por janela. Integração do antigo sistema FUNDOS (Streamlit), reescrito nesta arquitetura — ver seção própria abaixo. |

---

## Como rodar

Precisa de **Python 3.10+** e **Node 18+**. São **dois terminais**, ambos abertos na raiz do
repositório (`entrega-risco/`): um para o backend, outro para o frontend. Suba o backend primeiro.

Nenhuma dependência nova foi adicionada para a renda fixa — se o ambiente já estava instalado,
basta subir os servidores (passo 3 de cada bloco).

### 1. Backend — terminal 1

**Windows (PowerShell)** — chamando o Python do venv direto, sem `activate`, que é onde
a política de execução do PowerShell costuma atrapalhar:

```powershell
cd backend

# 1. só na primeira vez: cria o ambiente
python -m venv .venv

# 2. só na primeira vez (ou quando o requirements.txt mudar): instala as dependências
.venv\Scripts\python.exe -m pip install --upgrade pip
# 3. sempre: sobe a API
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Se preferir ativar o ambiente: `.\.venv\Scripts\Activate.ps1` (o `.\` é obrigatório). Se o
PowerShell bloquear o script, rode antes
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

**macOS / Linux:**

```bash
cd backend
python3 -m venv .venv                 # só na primeira vez
source .venv/bin/activate
pip install -r requirements.txt       # só na primeira vez
uvicorn app.main:app --reload
```

API em `http://127.0.0.1:8000` · documentação interativa em `http://127.0.0.1:8000/docs`.

O backend está no ar quando aparece `Application startup complete.` Para conferir de outro
terminal:

```powershell
curl.exe http://127.0.0.1:8000/api/health
curl.exe http://127.0.0.1:8000/api/titulos-publicos/disponiveis
```

A **primeira** chamada de renda fixa baixa o histórico do Tesouro Direto (~14 MB) e leva de 5 a
20 segundos. O resultado fica em cache por 12 horas, em memória e em `backend/.cache/` (ignorado
pelo git), então as chamadas seguintes e os próximos `--reload` respondem na hora. Se o download
falhar, a API serve o cache anterior em vez de cair.

### 2. Frontend — terminal 2

```bash
cd frontend
npm install      # só na primeira vez (ou quando o package.json mudar)
npm run dev      # sempre
```

Aplicação em `http://localhost:5173`. O Vite encaminha `/api` para o FastAPI em
`127.0.0.1:8000` — por isso o backend precisa estar de pé antes. Na aba **Book**, o seletor
**Ações | Renda Fixa** escolhe sobre qual book a análise roda.

### Parar os servidores

`Ctrl+C` em cada terminal. Fechar a janela do terminal nem sempre encerra o processo do Python
ou do Node no Windows — e aí a porta fica presa (veja abaixo).

### Se o backend não sobe: porta 8000 ocupada

Sintoma: `[WinError 10048] error while attempting to bind on address ('127.0.0.1', 8000)` ou
`Address already in use`. Sobrou um uvicorn de uma execução anterior segurando a porta. No
PowerShell, descubra quem é e encerre:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Get-Process -Id $_.OwningProcess }
Stop-Process -Id <PID-que-apareceu-acima> -Force
```

macOS / Linux: `lsof -i :8000` e `kill <PID>`. O mesmo vale para o frontend na porta `5173` —
com ela ocupada, o Vite sobe silenciosamente na `5174`, então confira o endereço que ele imprime.

Outros tropeços comuns:

- `No module named 'app'` — o uvicorn foi rodado fora da pasta `backend`. Rode `cd backend` antes.
- `No module named uvicorn` (ou `fastapi`, `pandas`…) — o venv não foi criado ou as dependências
  não foram instaladas. Refaça os passos 1 e 2 do backend.
- `.venv\Scripts\python.exe não é reconhecido` — o venv não existe nesta pasta; rode o passo 1.

### Testes

```powershell
cd backend
.venv\Scripts\python.exe -m pytest      # Windows
# pytest                                # macOS / Linux com o venv ativo
```

143 testes, todos com dados sintéticos e **sem rede** — o download do Tesouro e o yfinance são
sempre substituídos. Cobrem o núcleo de cálculo (comparação do VaR com o quantil do numpy,
convergência para a normal teórica, empírico × paramétrico sob normalidade e sob cauda gorda,
reação do EWMA a choque de volatilidade, ausência de look-ahead nos três backtests, calibragem
do Kupiec, Sharpe, Sortino, downside e drawdown) e a renda fixa: parsing do CSV do Tesouro,
cache e degradação, derivação do universo disponível, marcação a mercado e P&L, identidade das
métricas com o motor de ações, avisos de amostra curta e as rotas da API.

---

## O que a aplicação calcula

| Métrica | O que é |
|---|---|
| **VaR empírico** | Quantil `1 − c` da distribuição observada. Nenhuma hipótese de forma: não subestima cauda gorda, mas só enxerga o que já aconteceu. |
| **VaR paramétrico** | Normal de média e desvio estimados: `VaR = −(μ + z·σ)`. Analítico e rápido; subestima a ponta quando há curtose. |
| **VaR EWMA** | RiskMetrics, `σ²ₜ = λσ²ₜ₋₁ + (1−λ)r²ₜ₋₁` com λ = 0,94. Reage rápido a mudança de regime de volatilidade. |
| **Sharpe / Sortino** | Retorno excedente à Selic por unidade de risco — total no Sharpe, só das quedas no Sortino. Anualizados por √252. |
| **Drawdown** | Queda percentual sobre o topo anterior, com o máximo e a data do fundo. |
| **Expected shortfall (CVaR)** | Perda média condicional a ter estourado o VaR. |
| **Backtest rolling** | VaR recalculado a cada pregão com a janela móvel anterior, sem look-ahead. |
| **Histórico de violações** | Dias em que a perda realizada furou o limite: contagem, taxa, agrupamento por ano, maior sequência consecutiva e os 10 maiores excessos. |
| **Teste de Kupiec (POF)** | Cobertura incondicional. H₀: taxa de violações = `1 − c`. p-valor por qui-quadrado com 1 g.l. |
| **Distribuição** | Histograma de densidade dos retornos com a normal equivalente sobreposta, só como referência visual. |

### Decisões de modelagem

- **Sinal**: o VaR é reportado como **perda positiva**. `VaR = 0,032` a 95% significa "em 5% dos
  dias a perda supera 3,2%".
- **Retorno da carteira**: combinação linear dos retornos simples com rebalanceamento diário para
  os pesos alvo — o padrão em mensuração de risco de curto prazo. Os pesos informados são
  normalizados para 100%.
- **Horizonte > 1 dia**: o VaR é calculado direto sobre retornos acumulados de `h` dias em janelas
  sobrepostas, em vez de escalar por √h. Assim não se assume independência serial nem variância
  constante — coerente com a proposta do método empírico.
- **Horizonte no paramétrico e no EWMA**: escala pela raiz do tempo, coerente com a hipótese
  i.i.d. que os dois já assumem. Só o empírico usa retornos acumulados de verdade.
- **Backtest**: sempre diário (h = 1), que é a convenção regulatória para contagem de exceções.
  Os três métodos começam no mesmo pregão — sem isso a comparação de violações seria injusta.
- **EWMA e a janela**: o EWMA não tem janela fixa (a memória decai exponencialmente); a janela
  serve só para alinhar o início do backtest com os outros dois métodos.
- **Valor nominal**: derivado do peso — `peso normalizado × valor da carteira`. Uma fonte de
  verdade só, para peso e valor nunca se contradizerem.
- **Taxa livre de risco**: Selic diária, série 11 do SGS do Banco Central
  (`api.bcb.gov.br`, pública e sem chave), reindexada no calendário da bolsa com forward fill.
  Se o SGS estiver fora do ar ou bloqueado pela rede, a aplicação cai para uma taxa anual fixa
  (campo `selic_anual` do pedido, ou 15% a.a.) e sinaliza isso no payload e na interface.
- **Preços**: fechamento **ajustado** (`auto_adjust=True`), apenas datas em que todos os ativos da
  carteira negociaram.

### Renda fixa

- **Fonte**: CSV público do Tesouro Transparente (`PrecoTaxaTesouroDireto.csv`), histórico desde
  2002, em cache por 12 h com degradação para o cache anterior se o download falhar.
- **Universo disponível**: papéis na última `Data Base` publicada e com vencimento depois de hoje.
  Não há flag no arquivo — é derivado.
- **Marcação a mercado**: pelo **`PU Venda Manha`**, o preço pelo qual o Tesouro recompra o papel.
  `PU Compra Manha` é preço de emissão e não entra na marcação. A data-base é sempre o último dia
  útil publicado (normalmente D-1) e aparece explícita na interface.
- **PU de aquisição**: se não for informado, usa o PU de venda da data da compra (recuando para o
  último dia publicado) e marca a linha como estimada.
- **Métricas**: a série de PU de venda de cada título é uma série de preços e entra no **mesmo
  motor** das ações — nenhum cálculo novo. Anualização em 252 dias úteis, como no resto do projeto.
- **Pesos**: no book de renda fixa o dado primário é a quantidade; o peso sai do valor marcado a
  mercado sobre o total marcado.
- **Amostra curta**: título de emissão recente pode não cobrir a janela do backtest. Nesse caso o
  Kupiec vem nulo e a resposta traz um aviso estruturado em `avisos`, em vez de um p-valor sem
  significado.
- **Taxa do Tesouro Selic**: no arquivo é o spread sobre a Selic, não rendimento absoluto — a
  interface mostra `SELIC + x%`.

---

## API

`POST /api/analise` — payload completo das três abas

```json
{
  "posicoes": [
    { "ticker": "PETR4.SA", "peso": 40 },
    { "ticker": "VALE3.SA", "peso": 35 },
    { "ticker": "ITUB4.SA", "peso": 25 }
  ],
  "inicio": "2021-08-16",
  "fim": "2026-08-16",
  "confianca": 0.95,
  "horizonte": 1,
  "janela": 252,
  "valor_carteira": 100000
}
```

A resposta traz:

- `parametros` — o que foi efetivamente usado (datas reais, pregões, pesos normalizados);
- `book` — uma linha por ativo com peso, **valor nominal**, preços inicial e final, quantidade
  aproximada e retorno no período;
- `metodos.{empirico,parametrico,ewma}` — VaR e ES em % e em reais, mais `backtest.serie`
  (data, retorno, var, violação) e `backtest.resumo` (contagem, taxa, maior sequência, Kupiec);
- `estatisticas`, `distribuicao`, `evolucao`;
- `risco_retorno` — Sharpe, Sortino, retornos e Selic anualizados, drawdown, curvas acumuladas,
  índices móveis e a origem da taxa (`fonte_taxa`).

Campo opcional no pedido: `selic_anual` (ex.: `0.15`), usado só se o BCB estiver indisponível.

Outros endpoints: `POST /api/var/empirico` (contrato antigo, só o empírico), `GET /api/health` e
`GET /api/ativo?ticker=PETR4.SA`.

### Endpoints de renda fixa

| Endpoint | O que faz |
|---|---|
| `GET /api/titulos-publicos/disponiveis` | Universo do último dia útil publicado: `id`, tipo, vencimento, taxa e PU de venda, mais a `data_base` e a procedência do cache. |
| `POST /api/renda-fixa/marcacao` | Só a marcação a mercado: PU de aquisição e de marcação, valor marcado, P&L em R$ e %, data-base. |
| `POST /api/analise/renda-fixa` | Mesmo contrato de `/api/analise`, mais `marcacao`, `por_titulo` (métricas de cada papel) e `avisos`. |
| `POST /api/analise/consolidado` | Ações e renda fixa no mesmo book, ponderados por valor. Ainda sem entrada na interface. |

```json
{
  "posicoes": [
    { "titulo_id": "tesouro_ipca_2035-05-15", "quantidade": 10, "data_aquisicao": "2024-03-15" },
    { "titulo_id": "tesouro_prefixado_2029-01-01", "quantidade": 5, "pu_aquisicao": 700.0 }
  ],
  "confianca": 0.95,
  "horizonte": 1,
  "janela": 252,
  "inicio": "2022-01-01"
}
```

O `titulo_id` vem de `/api/titulos-publicos/disponiveis` e segue o formato
`{tipo}_{vencimento}`. `data_aquisicao` e `pu_aquisicao` são opcionais.

---

## Fundos

Integração do sistema FUNDOS (originalmente um app Streamlit à parte) como uma aba nativa —
mesmo backend, mesmo front, mesma identidade visual. Busca fundos ativos na CVM (dados abertos,
`dados.cvm.gov.br/dados/FI`), calcula retorno/volatilidade/Sharpe/Sortino contra o CDI (série 12
do SGS/BCB) e compara com Ibovespa (Yahoo Finance).

| Endpoint | O que faz |
|---|---|
| `GET /api/fundos/buscar?q=` | Fundos ativos cujo nome contém `q`. |
| `GET /api/fundos/top10?anos=1\|2\|3` | Top 10 por retorno acumulado, entre fundos com ≥ 100 cotistas e sem saltos mensais suspeitos (> 80% — proxy de desdobramento/erro de reporte, não performance real). |
| `GET /api/fundos/analise?cnpj=&meses=` | Métricas por janela (6/12/24/36 meses), série mensal (fundo/CDI/Ibovespa) e resumo do período pedido. |
| `POST /api/fundos/atualizar` | Força a próxima consulta a reprocessar o que pode ter mudado na CVM. |
| `GET /api/fundos/status` | Data/hora do último download do mês mais recente. |

**Cache**: os informes diários da CVM chegam em um ZIP por mês (todos os fundos juntos). Em vez
de reparsear esse ZIP a cada consulta (como o Streamlit original fazia, num dict em memória que
não sobrevive a restart), cada mês fechado é parseado **uma única vez** e persistido em
`backend/data/fundos_cache.db` (SQLite, modo WAL para suportar as gravações concorrentes do
`ThreadPoolExecutor` que baixa vários meses em paralelo). Meses antigos nunca mais são
reprocessados; só o mês corrente e o anterior são revistos a cada 6h, porque são os únicos que a
CVM ainda pode retificar.

---

## Estrutura

```
backend/
  app/
    main.py            endpoints FastAPI
    schemas.py         validação de entrada (pydantic)
    data.py            yfinance + cache de 15 min
    selic.py           série 11 do BCB + fallback de taxa fixa
    var_core.py        retornos, backtest, Kupiec, histograma  (compartilhado)
    var_empirico.py    simulação histórica
    var_parametrico.py normal
    var_ewma.py        RiskMetrics
    risco_retorno.py   Sharpe, Sortino, drawdown
    analise.py         orquestra o payload das três abas
    titulos_publicos.py  CSV do Tesouro: download, cache 12 h, parsing, universo disponível
    renda_fixa.py      marcação a mercado, matriz de PUs, métricas por título, avisos, consolidado
    rastreabilidade.py posse desde a compra, projeção no horizonte e confiabilidade da janela
    fundos/
      cvm_data.py      registro, cotas mensais, CDI, Ibovespa (cache SQLite em backend/data/)
      metrics.py       retorno, vol., Sharpe, Sortino de um fundo
      router.py        endpoints /api/fundos/*
  .cache/              histórico do Tesouro em cache (gerado na primeira chamada, fora do git)
  tests/
frontend/
  src/
    App.jsx            abas, classe de ativo e estado da análise
    api.js             cliente HTTP
    formato.js         formatação pt-BR, paleta e cor de cada método/série
    fundos.js          rótulo de mês e escala de cor do heatmap
    styles.css         guia de estilos da liga
    components/        book, KPIs, gráficos e a aba Fundos (AbaFundos.jsx)
      AbaBook.jsx        seletor Ações | Renda Fixa | Ambos
      BookRendaFixa.jsx  seleção de títulos públicos
      TabelaMarcacao.jsx marcação a mercado e P&L
      ParametrosRisco.jsx parâmetros compartilhados pelas duas classes
      AbaFundos.jsx      busca, Top 10 e análise de fundos da CVM
      AbaRastreabilidade.jsx  posse, valorização e projeção nas três classes
      TabelaRastreabilidade.jsx  uma linha por posição, da compra à projeção
      GraficoProjecao.jsx  realizado + cone de projeção
      GraficoPosse.jsx     valor do book desde a compra
      GraficoValorizacao.jsx  valorização por posição
```

### Contrato entre os métodos de VaR

Os três módulos expõem exatamente a mesma interface, e é só isso que `analise.py` e o front
conhecem:

```python
NOME, ROTULO, DESCRICAO                              # identificação
pontual(retornos, confianca, horizonte) -> {"var", "es"}
rolling(retornos, confianca, janela)    -> Backtest  # datas, retorno, var, violação
```

Trocar a implementação de qualquer um deles — pela versão oficial da célula, por um GARCH, pelo
que for — não exige tocar em mais nada: os gráficos, o backtest e o teste de aderência continuam
funcionando. Nenhum dos módulos faz chamada de rede; recebem uma Series de retornos e devolvem
números, o que os mantém testáveis sem depender do yfinance.

---

## Identidade visual

Paleta: `#000000` `#ffffff` `#ff4545` `#ad2727` `#130000` `#580000` `#360100` `#850000` `#c00000`.
Tipografia **Poppins** (Google Fonts). Os tokens estão em `frontend/src/styles.css` como variáveis
CSS.

---

## Notas

- Tickers da B3 exigem sufixo `.SA` (`PETR4.SA`). Índices e ativos internacionais entram no formato
  do Yahoo (`^BVSP`, `AAPL`, `BTC-USD`).
- O período precisa ser bem maior que a janela do backtest: com janela de 252 pregões, use pelo
  menos 3 anos de histórico.
- O yfinance é uma API não oficial e ocasionalmente aplica rate limit. A camada de dados guarda
  cada consulta em cache por 15 minutos.

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
