# Risco · VaR Empírico

Módulo de **Value at Risk por simulação histórica** para carteiras, com dados de mercado do
`yfinance`. Célula de Risco — Inteli Finance.

Backend em **FastAPI/Python**, front em **React (Vite)**. O VaR paramétrico e o VaR EWMA são
módulos irmãos e entram depois no mesmo contrato de API.

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

12 testes cobrem o núcleo de cálculo com dados sintéticos (sem rede): comparação do VaR com o
quantil do numpy, convergência para o valor teórico da normal, efeito da diversificação,
ausência de look-ahead no backtest e calibragem do teste de Kupiec.

---

## O que a aplicação calcula

| Métrica | O que é |
|---|---|
| **VaR empírico** | Quantil `1 − c` da distribuição observada dos retornos da carteira. Nenhuma hipótese de distribuição. |
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
- **Backtest**: sempre diário (h = 1), que é a convenção regulatória para contagem de exceções.
- **Preços**: fechamento **ajustado** (`auto_adjust=True`), apenas datas em que todos os ativos da
  carteira negociaram.

---

## API

`POST /api/var/empirico`

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

A resposta traz `parametros`, `resultado`, `estatisticas`, `distribuicao`, `backtest`
(`serie` + `resumo`) e `evolucao`.

Outros endpoints: `GET /api/health` e `GET /api/ativo?ticker=PETR4.SA` (valida o ticker e devolve
nome e último preço).

---

## Estrutura

```
backend/
  app/
    main.py           endpoints FastAPI
    schemas.py        validação de entrada (pydantic)
    data.py           yfinance + cache de 15 min
    var_empirico.py   núcleo de cálculo (puro, sem I/O)
  tests/
frontend/
  src/
    App.jsx
    api.js            cliente HTTP
    formato.js        formatação pt-BR e paleta
    styles.css        guia de estilos da liga
    components/       painel, KPIs e gráficos
```

O `var_empirico.py` não faz nenhuma chamada de rede: recebe um DataFrame de preços e devolve o
payload. Isso mantém o cálculo testável e facilita plugar os outros VaRs no mesmo formato.

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
