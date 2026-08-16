# Risco · Painel de risco de carteira

Aplicação de risco de carteira com dados de mercado do `yfinance` e taxa livre de risco do
Banco Central. Célula de Risco — Inteli Finance.

Backend em **FastAPI/Python**, front em **React (Vite)**, organizado em três abas:

| Aba | O que traz |
|---|---|
| **VaRs** | Os três métodos lado a lado — empírico, paramétrico e EWMA — com as curvas no tempo, distribuição, histórico de violações, violações por ano, teste de aderência e evolução da carteira. |
| **Risco e retorno** | Sharpe e Sortino contra a Selic, curva da carteira vs. Selic, índices móveis e drawdown. |
| **Book** | Onde a carteira é montada e todos os parâmetros são manipulados: ativos, peso, valor nominal, período, confiança, horizonte, janela do backtest e valor total. |

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

36 testes cobrem o núcleo de cálculo com dados sintéticos (sem rede): comparação do VaR com o
quantil do numpy, convergência para o valor teórico da normal, equivalência entre empírico e
paramétrico sob normalidade, divergência dos dois sob cauda gorda, reação do EWMA a choque de
volatilidade, ausência de look-ahead nos três backtests, calibragem do Kupiec e as fórmulas de
Sharpe, Sortino, downside e drawdown.

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
  tests/
frontend/
  src/
    App.jsx            abas e estado da análise
    api.js             cliente HTTP
    formato.js         formatação pt-BR, paleta e cor de cada método
    styles.css         guia de estilos da liga
    components/        book, KPIs e gráficos
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
