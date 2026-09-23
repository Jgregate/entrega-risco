# Fundamentação teórica

Referência conceitual e matemática de tudo que a aplicação calcula e mostra.
Célula de Risco — Inteli Finance.

---

## 1. A matéria-prima: de preço para retorno

Risco não se mede sobre preço, e sim sobre **retorno**. Preço não é estacionário — a série
sobe ou desce com o tempo e sua média não significa nada. Retorno é aproximadamente
estacionário, e é sobre ele que quantil, desvio e correlação fazem sentido.

**Retorno simples** (o que a aplicação usa):

$$r_t = \frac{P_t}{P_{t-1}} - 1$$

**Retorno logarítmico** (alternativa comum):

$$r^{log}_t = \ln\!\left(\frac{P_t}{P_{t-1}}\right)$$

Por que **simples** aqui: o retorno de uma carteira é a média ponderada dos retornos simples
dos ativos — exatamente, sem aproximação. Com log-retorno essa soma só vale aproximadamente,
e o erro cresce quando os retornos são grandes (justamente na cauda, que é o que o VaR mede).
O log-retorno tem a vantagem de ser aditivo no tempo, o que importa mais para agregação de
horizonte do que para agregação de carteira.

**Preço ajustado.** A aplicação usa fechamento ajustado (`auto_adjust=True`). Sem ajuste, um
desdobramento (split) de 1:2 apareceria como uma queda de 50% e viraria uma violação
espetacular do VaR que nunca existiu. Dividendos idem, na direção contrária.

**Retorno da carteira:**

$$r_{p,t} = \sum_{i=1}^{n} w_i \, r_{i,t}, \qquad \sum_i w_i = 1$$

A hipótese embutida é **rebalanceamento diário** para os pesos alvo. Sem ela, os pesos
derivariam com o desempenho de cada ativo e $w_i$ seria função do tempo. É a convenção padrão
em risco de curto prazo, mas note que é uma hipótese: uma carteira comprada e esquecida tem
outro perfil.

**Anualização.** Volatilidade escala com a raiz do tempo sob independência serial:

$$\sigma_{ano} = \sigma_{dia} \sqrt{252}$$

252 é o número aproximado de pregões no ano. Retorno, ao contrário, é composto:

$$r_{ano} = \left(\prod_t (1 + r_t)\right)^{252/T} - 1$$

---

## 2. VaR — o conceito

**Value at Risk** responde: *qual perda não será superada em $c$ dos casos, num horizonte de
$h$ dias?*

Formalmente, é o quantil da distribuição de retornos:

$$\mathbb{P}(r_p \le -\text{VaR}_c) = 1 - c$$

Um VaR de 95% igual a 1,75% significa: **em 5% dos dias, a perda supera 1,75%**. Em uma
carteira de R$ 100 mil, R$ 1.747.

### Convenção de sinal

Nesta aplicação o VaR é sempre **perda positiva**. Nos gráficos ele aparece como linha
negativa porque está no mesmo eixo dos retornos — a linha marca o piso abaixo do qual o
retorno caracteriza violação.

### Os três parâmetros

| Parâmetro | O que controla | Efeito |
|---|---|---|
| **Confiança $c$** | Quão longe na cauda se olha | Maior $c$ → maior VaR. 99% pega eventos ~2× mais raros que 95% |
| **Horizonte $h$** | Prazo da perda | Maior $h$ → maior VaR, aproximadamente com $\sqrt{h}$ |
| **Janela** | Quantos dias de história alimentam a estimativa | Janela curta → reage rápido, mas ruidosa. Longa → estável, mas lenta |

Basileia usa tipicamente 99% e 10 dias para risco de mercado; a indústria de fundos costuma
reportar 95% e 1 dia. **Não existe VaR "certo"** — existe VaR consistente com o parâmetro
declarado.

### O que o VaR NÃO diz

Três limitações que valem estar na ponta da língua:

1. **Não é perda máxima.** É o *piso* das perdas ruins. Nos 5% de dias em que o VaR é
   rompido, ele não diz nada sobre o tamanho do estrago — daí o Expected Shortfall.
2. **Não é subaditivo** (na forma geral). Pode acontecer $\text{VaR}(A+B) > \text{VaR}(A) +
   \text{VaR}(B)$, o que viola a intuição de que diversificar reduz risco. Por isso o VaR
   **não é uma medida coerente de risco** no sentido de Artzner et al. (1999). O ES é.
3. **É retrospectivo.** Todos os três métodos aqui estimam o futuro a partir do passado. Um
   risco que nunca se materializou na janela é invisível.

---

## 3. Os três métodos

### 3.1 VaR Empírico (simulação histórica)

$$\text{VaR}_c = -\,\text{Quantil}_{1-c}\big(\{r_{p,t}\}\big)$$

Ordena os retornos observados e lê o percentil. Nenhuma hipótese sobre a forma da
distribuição.

- **A favor:** captura cauda gorda, assimetria e qualquer formato estranho que o mercado
  realmente teve. Não erra por hipótese errada — só por amostra pobre.
- **Contra:** só enxerga o que aconteceu. Anda em **degraus**: o VaR só muda quando uma perda
  grande entra ou sai da janela, o que produz saltos artificiais na série. E todo dia da
  janela pesa igual — a crise de três anos atrás pesa o mesmo que ontem.

### 3.2 VaR Paramétrico (normal / variância-covariância)

$$\text{VaR}_c = -(\mu + z_{1-c}\,\sigma), \qquad z_{0,95} = -1{,}645,\; z_{0,99} = -2{,}326$$

Estima só dois parâmetros — média e desvio — e assume normalidade.

- **A favor:** analítico, rápido, estável, e se estende naturalmente para atribuição de risco
  por ativo via matriz de covariância.
- **Contra:** **subestima a cauda**. Retornos financeiros têm curtose em excesso — eventos de
  4 ou 5 desvios acontecem muito mais do que a normal prevê. Na B3 isso é regra, não exceção.

Um teste da aplicação mede exatamente isso: com uma $t$ de Student de 3 g.l. (mesma variância,
cauda mais pesada), o VaR empírico fica **mais de 20% acima** do paramétrico a 99,5%. Curioso:
a 95% o efeito **se inverte** — no miolo da distribuição a normal é mais conservadora. A cauda
gorda só cobra o preço quando se anda para a ponta.

### 3.3 VaR EWMA (RiskMetrics)

Mesma fórmula fechada do paramétrico, mas com variância por média móvel exponencial:

$$\sigma^2_t = \lambda\,\sigma^2_{t-1} + (1-\lambda)\,r^2_{t-1}, \qquad \lambda = 0{,}94$$

$$\text{VaR}_{c,t} = -z_{1-c}\,\sigma_t$$

O peso de um retorno de $k$ dias atrás decai como $\lambda^k$: ontem pesa 6%, um mês atrás
pesa ~1,3%, um ano atrás é praticamente zero. $\lambda = 0{,}94$ é o valor calibrado pelo
RiskMetrics (J.P. Morgan, 1996) para dados diários — a "meia-vida" é de cerca de 11 pregões.

- **A favor:** responde rápido a mudança de regime de volatilidade. Depois de um choque, o
  limite sobe em dias, não em meses.
- **Contra:** herda a normalidade do paramétrico. E como reage rápido, também **volta rápido**
  ao normal — pode relaxar o limite antes de a turbulência acabar.

Duas notas de implementação que importam:

- **Média zero.** O EWMA assume $\mu = 0$. Em horizonte de 1 dia a média é ruído perto do
  desvio ($\mu \approx 0{,}05\%$ contra $\sigma \approx 1{,}5\%$), e estimá-la adiciona mais
  erro do que informação.
- **Não tem janela.** A memória é infinita com peso decrescente. A "janela" na aplicação só
  define de onde o backtest começa a valer, para os três métodos partirem do mesmo pregão.

### 3.4 Agregação de horizonte

- **Empírico:** usa retornos acumulados de $h$ dias, em janelas sobrepostas —
  $\prod_{k=0}^{h-1}(1+r_{t-k}) - 1$. Não assume independência serial nem variância constante,
  o que é coerente com a proposta do método.
- **Paramétrico e EWMA:** escalam por $\sqrt{h}$, coerente com a hipótese i.i.d. que já
  assumem. Se houver autocorrelação nos retornos, essa regra subestima (ou superestima) o
  risco de horizonte longo.

---

## 4. Expected Shortfall (CVaR)

$$\text{ES}_c = -\,\mathbb{E}\!\left[\,r_p \mid r_p \le -\text{VaR}_c\,\right]$$

A **perda média nos dias em que o VaR foi rompido**. Responde o que o VaR ignora: *quando dá
ruim, dá quão ruim?*

O ES é sempre maior que o VaR e é **subaditivo** — diversificação nunca aumenta o ES. Por isso
Basileia III migrou de VaR 99% para ES 97,5% no capital de risco de mercado. A contrapartida:
o ES é mais difícil de fazer backtest, porque testar uma média condicional exige mais dados
que testar uma contagem de exceções.

Formas fechadas usadas aqui:

- Empírico: média aritmética dos retornos abaixo do corte.
- Normal: $\text{ES}_c = \sigma \dfrac{\phi(z_{1-c})}{1-c} - \mu$, onde $\phi$ é a densidade
  normal padrão.

---

## 5. Backtest e histórico de violações

### O que é uma violação

$$\text{violação}_t \iff r_{p,t} < -\text{VaR}_{c,t}$$

O ponto crítico é que $\text{VaR}_{c,t}$ precisa ser calculado **usando apenas informação até
$t-1$**. Se a estimativa usar o retorno do próprio dia, o modelo "prevê" o que já aconteceu e
o backtest não vale nada — é o erro de *look-ahead*. Na aplicação, o VaR do dia $t$ usa a
janela $[t - 252,\; t-1]$, e há um teste automatizado que verifica isso: alterar o último
retorno da série não pode mudar o VaR previsto para ele.

### Cobertura

Se o modelo está bem calibrado, a taxa de violações converge para $1 - c$:

$$\hat{\pi} = \frac{x}{n} \approx 1 - c$$

com $x$ violações em $n$ observações. Violar **de menos** também é problema: significa capital
regulatório parado à toa.

### Teste de Kupiec (POF — Proportion of Failures)

Testa formalmente $H_0: \pi = 1-c$ por razão de verossimilhança:

$$LR_{uc} = -2\ln\!\left[\frac{(1-p)^{n-x}\,p^{x}}{(1-\hat{\pi})^{n-x}\,\hat{\pi}^{x}}\right],
\qquad p = 1-c$$

Sob $H_0$, $LR_{uc} \sim \chi^2_1$. **p-valor abaixo de 0,05 rejeita $H_0$** — o modelo está
mal calibrado.

Duas ressalvas honestas:

1. **Poder baixo.** Com 250 observações e $c = 99\%$, o esperado são 2,5 violações; distinguir
   um modelo bom de um ruim exige anos de dados. Por isso o teste na aplicação roda sempre
   sobre o período completo, ignorando a janela dos gráficos.
2. **Ignora agrupamento.** Kupiec só conta violações, não olha *quando* elas acontecem. Dez
   violações espalhadas e dez violações em duas semanas dão o mesmo p-valor — mas a segunda
   situação é muito pior. Por isso a aplicação também reporta a **maior sequência de violações
   consecutivas**. O teste formal para isso é o de **Christoffersen** (independência +
   cobertura condicional), que não está implementado — é a extensão natural do módulo.

---

## 6. Aba VaRs — gráfico por gráfico

### 6.1 Cartões de VaR (topo)

Três números lado a lado, um por método, com ES e contagem de violações. É a leitura de
relance: **se os três estão próximos, a distribuição está se comportando como normal; se o
empírico descola para cima, há cauda gorda no período.**

### 6.2 Os VaRs no tempo

- **Eixo X:** pregões. **Eixo Y:** retorno (%), com escala compartilhada entre os três painéis.
- **Linha cinza:** retorno realizado.
- **Linha colorida:** o limite do VaR do método naquele dia.
- **Pontos brancos:** violações.

O que ler aqui é a **assinatura de cada método**:

- O **empírico** anda em degraus — cada degrau é uma perda grande entrando ou saindo da janela
  de 252 dias. Repare que o degrau de saída acontece exatamente um ano depois do evento, o que
  é um artefato do método, não informação nova do mercado.
- O **paramétrico** varia suavemente, acompanhando a média móvel do desvio.
- O **EWMA** oscila junto com a volatilidade realizada, apertando o limite dias depois de um
  choque.

Violações agrupadas em um período curto são o sinal mais preocupante: indicam que o modelo não
acompanhou uma mudança de regime.

### 6.3 Distribuição dos retornos e o corte de cada método

- **Barras:** histograma de densidade dos retornos observados na janela.
- **Linha clara:** densidade normal de mesma média e desvio — a distribuição que o paramétrico
  *supõe*.
- **Cauda pintada:** a fatia de $1-c$ que cada método considera além do VaR.
- **Linha tracejada:** o limite vigente no último pregão da janela.

É o gráfico que torna a cauda gorda visível: **compare a altura das barras nas pontas com a
linha da normal.** Se as barras nas extremidades ficam acima da curva, a normal está
subestimando a frequência dos eventos extremos — e o VaR paramétrico está otimista demais.

Duas estatísticas fecham a leitura, mostradas nos cartões:

- **Assimetria (skewness):** $\mathbb{E}[(r-\mu)^3]/\sigma^3$. Negativa significa cauda
  esquerda mais longa — quedas raras porém violentas. É o padrão de ações.
- **Curtose em excesso:** $\mathbb{E}[(r-\mu)^4]/\sigma^4 - 3$. Zero é normal. Positiva
  significa mais massa nas pontas e no centro, menos nos ombros — o retrato típico de ativo
  financeiro.

### 6.4 Violações por ano

- **Eixo Y:** taxa de violações do ano — violações ÷ observações daquele ano.
- **Linha tracejada:** a taxa esperada, $1-c$.
- **Barras cheias:** anos acima do esperado.

Está em taxa, e não em contagem, por um motivo específico: em taxa a linha do esperado é a
mesma em qualquer período, então anos com número diferente de pregões (ou janelas de tamanhos
diferentes) continuam comparáveis. Em contagem bruta, um período mais longo produziria barras
maiores sem que isso significasse pior calibragem.

A leitura é temporal: **um ano muito acima da linha normalmente coincide com um choque de
mercado** que a janela histórica ainda não tinha absorvido.

### 6.5 Aderência do modelo

A tabela do Kupiec, mais a maior sequência de violações consecutivas e os maiores excessos
(quanto o retorno passou do limite). Roda sempre sobre o histórico completo.

O **excesso** — $-(r_t + \text{VaR}_t)$ — é informação que a contagem de violações joga fora:
diz o tamanho do estouro, não só que ele houve.

### 6.6 Evolução da carteira

Valor acumulado, $V_t = V_0 \prod_{k \le t}(1 + r_{p,k})$, rebaseado ao início da janela
selecionada. Serve de contexto: casa os picos de VaR e os agrupamentos de violação com o que
estava acontecendo com o patrimônio.

---

## 7. Aba Risco e retorno

Aqui a pergunta muda. VaR responde *quanto posso perder*; esta aba responde *o risco que
corri foi pago*?

### 7.1 Taxa livre de risco — Selic

Toda medida de risco-retorno compara contra o custo de oportunidade de não correr risco
nenhum. No Brasil isso é a **Selic**, série 11 do SGS do Banco Central (taxa diária, em % ao
dia).

A conversão de taxa anual para diária é composta, não linear:

$$r_f^{dia} = (1 + r_f^{ano})^{1/252} - 1$$

A série é reindexada no calendário da bolsa com *forward fill*, porque feriado bancário e
feriado de bolsa não coincidem sempre.

### 7.2 Índice de Sharpe

$$S = \frac{\mathbb{E}[r_p - r_f]}{\sigma(r_p - r_f)} \times \sqrt{252}$$

**Retorno excedente por unidade de risco total.** Quanto prêmio a carteira entregou acima da
Selic, normalizado pela volatilidade.

Referência prática: Sharpe acima de 1 é bom, acima de 2 é raro e merece desconfiança de
sobreajuste. **Negativo significa que a carteira rendeu menos que a Selic** — no Brasil, com
juro real alto, isso é comum e não é anomalia de cálculo.

Limitações que valem citar numa banca:

- Pune volatilidade **para cima** igual à volatilidade para baixo. Um mês de +15% piora o
  Sharpe.
- Assume implicitamente que média e desvio descrevem a distribuição — o que é falso sob cauda
  gorda e assimetria.
- É sensível à frequência dos dados e ao fator de anualização.

### 7.3 Índice de Sortino

$$\text{Sortino} = \frac{\mathbb{E}[r_p - r_f]}{\sigma_{down}} \times \sqrt{252},
\qquad \sigma_{down} = \sqrt{\frac{1}{T}\sum_{t=1}^{T} \min(r_{p,t} - r_f, \; 0)^2}$$

Mesmo numerador, denominador diferente: **só o desvio das quedas**. Corrige a crítica central
ao Sharpe — investidor não tem aversão a ganhar.

Detalhe de implementação que muda o número: o denominador divide por $T$ (todas as
observações), não pelo número de dias negativos. É a definição correta, e é o que faz sentido
economicamente — uma carteira que raramente cai deve ser premiada por isso, não ter o
denominador inflado por ter poucas observações negativas.

**A distância entre Sharpe e Sortino é informação.** Sortino muito acima do Sharpe indica
assimetria positiva: a volatilidade da carteira é predominantemente para cima.

### 7.4 Sharpe e Sortino móveis

Os mesmos índices em janela móvel de 252 pregões. Um número único para cinco anos esconde
regime: **o gráfico móvel mostra quando a relação risco-retorno desandou** e se a recuperação
veio de mais retorno ou de menos volatilidade.

Os dois painéis compartilham a escala vertical de propósito — comparar os dois é o objetivo.

### 7.5 Carteira contra a Selic

Duas curvas de retorno acumulado, $\prod(1+r_t) - 1$. **A distância entre elas é o prêmio que
o risco pagou** — exatamente o numerador do Sharpe e do Sortino, em forma visual. Se a linha
tracejada da Selic está acima da carteira, todo o risco assumido foi para trás do CDI.

### 7.6 Drawdown

$$DD_t = \frac{V_t}{\max_{k \le t} V_k} - 1$$

Queda percentual em relação ao **topo anterior**. O mínimo da série é o *maximum drawdown*.

É a medida de risco que o investidor de verdade sente, porque mede a pior sequência que ele
teria atravessado — não um dia ruim isolado, mas a viagem inteira do topo ao fundo. VaR de
1,75% ao dia soa administrável; um drawdown de 57% no mesmo período conta outra história, e as
duas são verdadeiras.

Duas leituras complementares: a **profundidade** (quanto caiu) e a **duração** (quanto tempo
levou para voltar ao topo — visível na largura do vale).

---

## 8. Aba Book

- **Peso ($w_i$):** participação relativa, normalizada para somar 100%.
- **Valor nominal:** $w_i \times V_0$. É a exposição em reais de cada posição.
- **Quantidade aproximada:** valor nominal ÷ último preço, sem lote padrão nem fracionário —
  é indicativa.
- **Retorno no período:** $P_T/P_0 - 1$ do ativo isolado.

A carteira agregada quase sempre tem retorno diferente da média ponderada dos retornos
individuais do período. Isso não é erro: é o efeito do **rebalanceamento diário** — a cada dia
a carteira volta aos pesos alvo, vendendo o que subiu e comprando o que caiu.

### Por que diversificação reduz o VaR

O desvio da carteira não é a média dos desvios:

$$\sigma_p^2 = \sum_i \sum_j w_i w_j \,\sigma_i \sigma_j \,\rho_{ij}$$

Enquanto $\rho_{ij} < 1$, o desvio da carteira é **menor** que a média ponderada dos desvios
individuais. É o único almoço grátis em finanças. A contrapartida é que correlação não é
estável: em crise ela sobe em direção a 1, justamente quando a diversificação seria mais
necessária.

---

## 9. Limitações da aplicação inteira

Vale ter isso pronto, porque é o que uma banca pergunta:

1. **Risco de mercado apenas.** Nada de risco de crédito, liquidez ou operacional. A aplicação
   assume que dá para liquidar a posição ao preço de fechamento.
2. **Sem custo de transação.** O rebalanceamento diário é gratuito no modelo, o que não é
   verdade na prática — e quanto mais volátil o ativo, mais caro seria.
3. **Dependência do histórico.** Os três métodos são retrospectivos. Nenhum deles teria
   previsto março de 2020 em fevereiro de 2020.
4. **Sem análise de cenário.** Não há stress testing — a extensão natural seria aplicar
   choques hipotéticos (paralelo à curva de juros, queda de 30% no Ibovespa) além do VaR
   histórico.
5. **Distribuição estacionária implícita.** Todos assumem que a distribuição dos retornos é a
   mesma ao longo da janela. O EWMA é o único que relaxa isso parcialmente, ao ponderar o
   passado recente.
6. **yfinance é fonte não oficial.** Serve para estudo; produção exigiria dados de mercado
   auditáveis.

---

## 10. Referências

- **Jorion, P.** *Value at Risk: The New Benchmark for Managing Financial Risk*, 3ª ed.
  McGraw-Hill, 2006. A referência canônica de VaR.
- **J.P. Morgan/Reuters.** *RiskMetrics — Technical Document*, 4ª ed., 1996. Origem do EWMA
  com $\lambda = 0{,}94$.
- **Kupiec, P.** "Techniques for Verifying the Accuracy of Risk Measurement Models".
  *Journal of Derivatives*, 1995. O teste POF.
- **Christoffersen, P.** "Evaluating Interval Forecasts". *International Economic Review*,
  1998. Cobertura condicional e independência.
- **Artzner, P. et al.** "Coherent Measures of Risk". *Mathematical Finance*, 1999. Por que o
  VaR não é coerente e o ES é.
- **Sortino, F. & Price, L.** "Performance Measurement in a Downside Risk Framework".
  *Journal of Investing*, 1994.
- **BCBS.** *Minimum Capital Requirements for Market Risk*, 2019. A migração de VaR para ES.
