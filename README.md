# 🤖 BlockyMarketMaker

An automated Market Maker bot for the Blocky Minecraft Economy Server.

Um bot automatizado de Market Making para o servidor de economia Blocky Minecraft.

---

<details>
<summary><strong>🇺🇸 English Documentation</strong></summary>

## 📖 Table of Contents

- [What is Market Making?](#-what-is-market-making)
- [Features](#-features)
- [Requirements](#-requirements)
- [Quick Start](#-quick-start)
- [Running with Docker](#-running-with-docker)
- [Configuration Guide](#-configuration-guide)
- [Understanding the Bot](#-understanding-the-bot)
- [Dashboard](#-dashboard)
- [Monitoring](#-monitoring)
- [Project Structure](#-project-structure)
- [Understanding Log Messages](#-understanding-log-messages)
- [Troubleshooting](#-troubleshooting)

---

## 💡 What is Market Making?

**Market Making** is a trading strategy where you provide liquidity to a market by placing **buy** and **sell** orders simultaneously.

### Simple Example:
Imagine you want to trade diamonds:
- You place a **BUY order** at 49 Iron (you're willing to buy diamonds for 49)
- You place a **SELL order** at 51 Iron (you're willing to sell diamonds for 51)

When someone sells you a diamond for 49 and later someone buys it for 51, you profit 2 Iron!

**The "spread"** (51 - 49 = 2 Iron, or ~4%) is your profit margin.

### Why use a bot?
- Markets move 24/7 - you can't watch them constantly
- The bot adjusts prices automatically based on supply/demand
- It handles dozens of markets simultaneously
- It responds to market changes in milliseconds

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Dynamic Spread** | Automatically adjusts spreads based on volatility and inventory |
| **Smart Order Diffing** | Only updates orders when necessary (reduces API spam) |
| **Pennying Strategy** | Automatically beats competitors by 0.01 while maintaining profit margins |
| **Scarcity-Based Pricing** | Prices items based on remaining world supply |
| **Circuit Breaker** | Protects against API failures with automatic recovery |
| **Rate Limiting** | Respects API limits (30 req/sec) |
| **Discord/Slack Alerts** | Get notified about errors and important events |
| **Web Dashboard** | Real-time trading dashboard with charts |
| **Health Endpoint** | HTTP `/health` for monitoring systems |
| **Dry Run Mode** | Test strategies without real orders |
| **Metrics & P&L** | Track your trading performance |

---

## 📋 Requirements

### Minimum Requirements
- **Python 3.11+** (or Docker)
- **Blocky API Key** (see below how to get it)
- **Internet connection** (stable, for WebSocket)
- **~100MB RAM** (the bot is lightweight)

### How to Get Your Blocky API Key

1. Go to the Blocky web panel: `https://craft.blocky.com.br`
2. Log in with your Minecraft account
3. Navigate to **Settings** or **API**
4. Generate a new API key
5. Copy and save it securely (you'll need it during setup)

> ⚠️ **Important:** Never share your API key with anyone!

### Optional
- Discord Webhook URL (for alerts)
- Docker (for containerized deployment)

---

## 🚀 Quick Start

### Option 1: Run Locally (Recommended for Beginners)

#### Step 1: Install Python

**Windows:**
1. Download Python 3.11+ from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. ✅ **Check "Add Python to PATH"** during installation
4. Open Command Prompt and verify: `python --version`

**macOS:**
```bash
brew install python@3.11
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.11 python3-pip python3-venv
```

#### Step 2: Clone and Setup

```bash
# 1. Clone the repository
git clone https://github.com/zukrmn/BlockyMarketMaker.git
cd BlockyMarketMaker

# 2. Create a virtual environment (recommended)
python -m venv venv

# 3. Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the interactive setup (creates .env file)
python scripts/setup.py

# 6. Start the bot
python run.py
```

The setup wizard will ask for:
1. Your **Blocky API Key**
2. (Optional) **Discord Webhook URL** for alerts

#### Step 3: Stopping the Bot

Press `Ctrl+C` in the terminal to stop the bot gracefully. It will:
- Cancel all open orders
- Save metrics to disk
- Close connections properly

### Option 2: Manual Configuration

Create a `.env` file manually:

```bash
# .env
BLOCKY_API_KEY=your-api-key-here
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
ALERT_WEBHOOK_TYPE=discord
```

Then run:

```bash
pip install -r requirements.txt
python run.py
```

---

## 🐳 Running with Docker

### Build the Image

```bash
docker build -f docker/Dockerfile -t blocky-market-maker:prod .
```

### Run the Container

**Important:** Create your `.env` file first (via `python scripts/setup.py` or manually).

```bash
# Run with .env mounted
docker run --rm \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -p 8080:8080 \
  -p 8081:8081 \
  blocky-market-maker:prod
```

### Docker Compose (Recommended)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  market-maker:
    build:
      context: .
      dockerfile: docker/Dockerfile
    restart: unless-stopped
    ports:
      - "8080:8080"   # Health endpoint
      - "8081:8081"   # Dashboard
    volumes:
      - ./.env:/app/.env:ro
      - ./config.yaml:/app/config.yaml:ro
      - ./src/metrics_data.json:/app/src/metrics_data.json
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Then run:

```bash
docker-compose up -d
```

---

## ⚙️ Configuration Guide

All settings are in `config.yaml`. Environment variables override YAML values.

### Trading Parameters

```yaml
trading:
  dry_run: false           # true = simulate only, no real orders
  enabled_markets: []      # Whitelist: empty = all markets
  disabled_markets: []     # Blacklist: never trade these
  spread: 0.05             # 5% fixed spread (used if dynamic_spread disabled)
  min_spread_ticks: 0.01   # Minimum price difference between buy/sell
  target_value: 10.0       # Target order value in Iron
  max_quantity: 6400       # Maximum order quantity
  refresh_interval: 60     # Seconds between integrity checks
```

#### Examples

**Trade only specific markets:**
```yaml
trading:
  enabled_markets: [diam_iron, gold_iron, lapi_iron]
```

**Exclude problematic markets:**
```yaml
trading:
  disabled_markets: [sand_iron, dirt_iron]
```

**Test without real orders:**
```yaml
trading:
  dry_run: true
```

### Dynamic Spread

```yaml
dynamic_spread:
  enabled: true            # false = use fixed spread from trading.spread
  base_spread: 0.03        # 3% base spread
  volatility_multiplier: 2.0  # Higher = more sensitive to volatility
  inventory_impact: 0.02   # Max adjustment from inventory imbalance
  min_spread: 0.01         # 1% minimum (floor)
  max_spread: 0.15         # 15% maximum (ceiling)
  volatility_window: 24    # Hours of OHLCV data to analyze
```

**How it works:**
- `spread = base_spread + volatility_adj + inventory_adj`
- High volatility → wider spreads (protection)
- Overstocked → wider buy spread, tighter sell spread (rebalancing)

### Price Model

```yaml
price_model:
  cache_ttl: 60            # Seconds to cache supply metrics
  
  base_prices:             # Base prices when 0% of item is acquired
    diam_iron: 50.0
    gold_iron: 5.0
    lapi_iron: 2.0
    coal_iron: 0.5
    ston_iron: 0.1
    cobl_iron: 0.05
    dirt_iron: 0.01
    sand_iron: 0.05
    olog_iron: 0.45
    obsn_iron: 2.5
    slme_iron: 5.0
```

The bot calculates prices based on **scarcity**:
- `fair_price = base_price × (total_supply / remaining_supply)`
- As items are collected, prices increase

### Rate Limiting & Circuit Breaker

```yaml
rate_limit:
  max_requests: 30         # Requests per window
  window_seconds: 1.0      # Window duration

circuit_breaker:
  failure_threshold: 5     # Failures before blocking requests
  recovery_timeout: 30.0   # Seconds before trying again
```

### Alerts

```yaml
alerts:
  enabled: true
  webhook_type: "discord"  # discord, slack, telegram, custom
  min_level: "warning"     # info, warning, error, critical
  rate_limit_seconds: 60   # Prevent spam
```

Set webhook URL via environment variable:
```bash
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### Health Endpoint

```yaml
health:
  enabled: true
  port: 8080
```

Access at `http://localhost:8080/health`

---

## 🧠 Understanding the Bot

### Trading Strategy

1. **Price Calculation**: Uses scarcity model + market data
2. **Spread Calculation**: Dynamic based on volatility + inventory
3. **Pennying**: If competitor has better price, beat them by 0.01 (within profit margin)
4. **Order Diffing**: Only cancel/create orders when prices change significantly
5. **Inventory Management**: Adjusts quotes based on current holdings

### Order Flow

```
Every 60 seconds:
├── Update wallet balances
├── Fetch market tickers (batch)
├── For each market:
│   ├── Calculate fair price (scarcity model)
│   ├── Calculate dynamic spread
│   ├── Apply pennying strategy
│   ├── Check inventory/capital
│   ├── Diff with existing orders
│   ├── Cancel stale orders (if needed)
│   └── Place new orders (if needed)
└── Poll recent trades for P&L

WebSocket events (real-time):
├── Trade on market → immediate requote
└── Orderbook change → immediate requote
```

---

## 📊 Dashboard

The bot includes a **real-time web dashboard** for monitoring your trading activity.

### Accessing the Dashboard

Once the bot is running, open your browser and go to:
```
http://localhost:8081/dashboard
```

### Dashboard Features

- **📈 Live Price Charts**: Candlestick charts with real-time data
- **📖 Order Book**: See current bids and asks
- **💰 P&L Tracking**: Monitor your realized profits
- **🎯 Strategy Cards**: View active pricing strategies
- **📋 Market List**: Quick navigation between all markets
- **🎨 Drawing Tools**: Add trendlines and annotations to charts

### Dashboard Ports

| Port | Service |
|------|---------|
| 8080 | Health endpoint (`/health`) |
| 8081 | Web Dashboard (`/dashboard`) |

---

## 📊 Monitoring

### Health Check

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "status": "healthy",
  "markets_count": 11,
  "circuit_breaker": "CLOSED",
  "websocket_connected": true,
  "realized_pnl": 12.54,
  "orders_placed": 156,
  "total_trades": 23
}
```

### Logs

The bot outputs colored logs to console and saves them to `logs/bot.log`:
- 🟢 Green = INFO
- 🟡 Yellow = WARNING  
- 🔴 Red = ERROR
- 🧪 = Dry run actions

### Metrics Persistence

Metrics are saved to `src/metrics_data.json` every 60 seconds and on shutdown.

---

## 📁 Project Structure

```
BlockyMarketMaker/
├── run.py                 # Entry point - run this to start the bot
├── config.yaml            # Main configuration file
├── requirements.txt       # Python dependencies
├── .env                   # Your API keys (create this)
│
├── src/                   # Source code
│   ├── main.py            # Bot main logic
│   ├── blocky/            # Blocky API client
│   ├── dashboard/         # Web dashboard
│   ├── price_model.py     # Scarcity-based pricing
│   ├── spread_calculator.py
│   ├── trading_helpers.py
│   └── ...
│
├── scripts/               # Utility scripts
│   ├── setup.py           # Interactive setup wizard
│   └── ...
│
├── docker/                # Docker configuration
│   └── Dockerfile
│
├── logs/                  # Log files (auto-created)
│   └── bot.log
│
├── data/                  # Market data for analysis (auto-created)
│
└── tests/                 # Unit tests
```

---

## 📝 Understanding Log Messages

Here's what common log messages mean:

| Message | Meaning |
|---------|---------|
| `Placed buy order` | Successfully placed a buy order |
| `Placed sell order` | Successfully placed a sell order |
| `Cancelling order (Diff Mismatch)` | Price changed, old order being replaced |
| `Insufficient funds` | Not enough Iron to place order |
| `Circuit breaker OPEN` | Too many API errors, pausing requests |
| `WS Event: Trade on X` | Someone traded on market X |
| `Integrity Check` | Periodic check of all orders |
| `🧪 [DRY-RUN]` | Simulated action (no real order) |

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| `BLOCKY_API_KEY not set` | Run `python scripts/setup.py` or create `.env` file |
| `502 Bad Gateway` | Blocky API is down. Bot will auto-retry every 5s. |
| `Circuit breaker OPEN` | Too many API errors. Will auto-recover in 30s. |
| `Insufficient funds` | Add more Iron to your wallet or reduce `target_value`. |
| `Rate limit reached` | Bot will auto-throttle. Check `rate_limit` settings. |
| No orders placed | Check `enabled_markets`/`disabled_markets` config. |
| Dashboard not loading | Make sure port 8081 is free. Check `http://localhost:8081/dashboard` |
| `ModuleNotFoundError` | Activate virtual environment: `source venv/bin/activate` |

### Before Your First Run

1. ✅ Make sure you have **Iron in your Blocky wallet**
2. ✅ Start with `dry_run: true` to test without real money
3. ✅ Use a **single market** first: `enabled_markets: [diam_iron]`
4. ✅ Check the dashboard to see what the bot is doing

### Dry Run Testing

Test your configuration without real orders:

```yaml
trading:
  dry_run: true
```

Logs will show `🧪 [DRY-RUN]` prefix for simulated actions.

---

</details>

---

<details open>
<summary><strong>🇧🇷 Documentação em Português</strong></summary>

## 📖 Índice

- [O que é Market Making?](#-o-que-é-market-making)
- [Recursos](#-recursos)
- [Requisitos](#-requisitos)
- [Início Rápido](#-início-rápido)
- [Rodando com Docker](#-rodando-com-docker)
- [Guia de Configuração](#-guia-de-configuração)
- [Entendendo o Bot](#-entendendo-o-bot)
- [Dashboard](#-dashboard-1)
- [Monitoramento](#-monitoramento)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Entendendo as Mensagens de Log](#-entendendo-as-mensagens-de-log)
- [Solução de Problemas](#-solução-de-problemas)

---

## 💡 O que é Market Making?

**Market Making** é uma estratégia de trading onde você fornece liquidez ao mercado colocando ordens de **compra** e **venda** simultaneamente.

### Exemplo Simples:
Imagine que você quer negociar diamantes:
- Você coloca uma **ordem de COMPRA** a 49 Iron (você está disposto a comprar diamantes por 49)
- Você coloca uma **ordem de VENDA** a 51 Iron (você está disposto a vender diamantes por 51)

Quando alguém te vende um diamante por 49 e depois alguém compra por 51, você lucra 2 Iron!

**O "spread"** (51 - 49 = 2 Iron, ou ~4%) é sua margem de lucro.

### Por que usar um bot?
- Mercados funcionam 24/7 - você não pode ficar assistindo o tempo todo
- O bot ajusta preços automaticamente baseado em oferta/demanda
- Ele gerencia dezenas de mercados simultaneamente
- Responde a mudanças de mercado em milissegundos

---

## ✨ Recursos

| Recurso | Descrição |
|---------|-----------|
| **Spread Dinâmico** | Ajusta spreads automaticamente baseado em volatilidade e inventário |
| **Smart Order Diffing** | Só atualiza ordens quando necessário (reduz spam na API) |
| **Estratégia de Pennying** | Supera concorrentes por 0.01 mantendo margem de lucro |
| **Precificação por Escassez** | Precifica itens baseado na oferta restante no mundo |
| **Circuit Breaker** | Protege contra falhas na API com recuperação automática |
| **Rate Limiting** | Respeita limites da API (30 req/seg) |
| **Alertas Discord/Slack** | Notificações sobre erros e eventos importantes |
| **Dashboard Web** | Dashboard de trading em tempo real com gráficos |
| **Endpoint de Saúde** | HTTP `/health` para sistemas de monitoramento |
| **Modo Dry Run** | Teste estratégias sem ordens reais |
| **Métricas & P&L** | Acompanhe sua performance de trading |

---

## 📋 Requisitos

### Requisitos Mínimos
- **Python 3.11+** (ou Docker)
- **Chave de API da Blocky** (veja abaixo como obter)
- **Conexão com internet** (estável, para WebSocket)
- **~100MB RAM** (o bot é leve)

### Como Obter Sua Chave de API da Blocky

1. Acesse o painel web da Blocky: `https://craft.blocky.com.br`
2. Faça login com sua conta Minecraft
3. Navegue até **Configurações** ou **API**
4. Gere uma nova chave de API
5. Copie e guarde em segurança (você vai precisar durante o setup)

> ⚠️ **Importante:** Nunca compartilhe sua chave de API com ninguém!

### Opcional
- URL de Webhook do Discord (para alertas)
- Docker (para deploy containerizado)

---

## 🚀 Início Rápido

### Opção 1: Rodar Localmente (Recomendado para Iniciantes)

#### Passo 1: Instalar Python

**Windows:**
1. Baixe Python 3.11+ em [python.org](https://www.python.org/downloads/)
2. Execute o instalador
3. ✅ **Marque "Add Python to PATH"** durante a instalação
4. Abra o Prompt de Comando e verifique: `python --version`

**macOS:**
```bash
brew install python@3.11
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.11 python3-pip python3-venv
```

#### Passo 2: Clonar e Configurar

```bash
# 1. Clone o repositório
git clone https://github.com/zukrmn/BlockyMarketMaker.git
cd BlockyMarketMaker

# 2. Crie um ambiente virtual (recomendado)
python -m venv venv

# 3. Ative o ambiente virtual
# No Windows:
venv\Scripts\activate
# No macOS/Linux:
source venv/bin/activate

# 4. Instale as dependências
pip install -r requirements.txt

# 5. Execute o setup interativo (cria arquivo .env)
python scripts/setup.py

# 6. Inicie o bot
python run.py
```

O assistente de configuração vai pedir:
1. Sua **Chave de API da Blocky**
2. (Opcional) **URL do Webhook do Discord** para alertas

#### Passo 3: Parando o Bot

Pressione `Ctrl+C` no terminal para parar o bot graciosamente. Ele vai:
- Cancelar todas as ordens abertas
- Salvar métricas em disco
- Fechar conexões corretamente

### Opção 2: Configuração Manual

Crie um arquivo `.env` manualmente:

```bash
# .env
BLOCKY_API_KEY=sua-api-key-aqui
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
ALERT_WEBHOOK_TYPE=discord
```

Depois execute:

```bash
pip install -r requirements.txt
python run.py
```

---

## 🐳 Rodando com Docker

### Construir a Imagem

```bash
docker build -f docker/Dockerfile -t blocky-market-maker:prod .
```

### Rodar o Container

**Importante:** Crie seu arquivo `.env` primeiro (via `python scripts/setup.py` ou manualmente).

```bash
# Rodar com .env montado
docker run --rm \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -p 8080:8080 \
  -p 8081:8081 \
  blocky-market-maker:prod
```

### Docker Compose (Recomendado)

Crie `docker-compose.yml`:

```yaml
version: '3.8'

services:
  market-maker:
    build:
      context: .
      dockerfile: docker/Dockerfile
    restart: unless-stopped
    ports:
      - "8080:8080"   # Endpoint de saúde
      - "8081:8081"   # Dashboard
    volumes:
      - ./.env:/app/.env:ro
      - ./config.yaml:/app/config.yaml:ro
      - ./src/metrics_data.json:/app/src/metrics_data.json
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Depois execute:

```bash
docker-compose up -d
```

---

## ⚙️ Guia de Configuração

Todas as configurações estão em `config.yaml`. Variáveis de ambiente sobrescrevem valores do YAML.

### Parâmetros de Trading

```yaml
trading:
  dry_run: false           # true = apenas simula, sem ordens reais
  enabled_markets: []      # Whitelist: vazio = todos os mercados
  disabled_markets: []     # Blacklist: nunca opera nesses
  spread: 0.05             # 5% spread fixo (usado se dynamic_spread desabilitado)
  min_spread_ticks: 0.01   # Diferença mínima de preço entre compra/venda
  target_value: 10.0       # Valor alvo da ordem em Iron
  max_quantity: 6400       # Quantidade máxima por ordem
  refresh_interval: 60     # Segundos entre verificações de integridade
```

#### Exemplos

**Operar apenas mercados específicos:**
```yaml
trading:
  enabled_markets: [diam_iron, gold_iron, lapi_iron]
```

**Excluir mercados problemáticos:**
```yaml
trading:
  disabled_markets: [sand_iron, dirt_iron]
```

**Testar sem ordens reais:**
```yaml
trading:
  dry_run: true
```

### Spread Dinâmico

```yaml
dynamic_spread:
  enabled: true            # false = usa spread fixo de trading.spread
  base_spread: 0.03        # 3% spread base
  volatility_multiplier: 2.0  # Maior = mais sensível à volatilidade
  inventory_impact: 0.02   # Ajuste máximo por desbalanceamento de inventário
  min_spread: 0.01         # 1% mínimo (piso)
  max_spread: 0.15         # 15% máximo (teto)
  volatility_window: 24    # Horas de dados OHLCV para analisar
```

**Como funciona:**
- `spread = spread_base + ajuste_volatilidade + ajuste_inventário`
- Alta volatilidade → spreads maiores (proteção)
- Excesso de estoque → spread de compra maior, spread de venda menor (rebalanceamento)

### Modelo de Preço

```yaml
price_model:
  cache_ttl: 60            # Segundos para cachear métricas de supply
  
  base_prices:             # Preços base quando 0% do item foi coletado
    diam_iron: 50.0
    gold_iron: 5.0
    lapi_iron: 2.0
    coal_iron: 0.5
    ston_iron: 0.1
    cobl_iron: 0.05
    dirt_iron: 0.01
    sand_iron: 0.05
    olog_iron: 0.45
    obsn_iron: 2.5
    slme_iron: 5.0
```

O bot calcula preços baseado em **escassez**:
- `preço_justo = preço_base × (supply_total / supply_restante)`
- Conforme itens são coletados, preços aumentam

### Rate Limiting & Circuit Breaker

```yaml
rate_limit:
  max_requests: 30         # Requisições por janela
  window_seconds: 1.0      # Duração da janela

circuit_breaker:
  failure_threshold: 5     # Falhas antes de bloquear requisições
  recovery_timeout: 30.0   # Segundos antes de tentar novamente
```

### Alertas

```yaml
alerts:
  enabled: true
  webhook_type: "discord"  # discord, slack, telegram, custom
  min_level: "warning"     # info, warning, error, critical
  rate_limit_seconds: 60   # Previne spam
```

Configure a URL do webhook via variável de ambiente:
```bash
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### Endpoint de Saúde

```yaml
health:
  enabled: true
  port: 8080
```

Acesse em `http://localhost:8080/health`

---

## 🧠 Entendendo o Bot

### Estratégia de Trading

1. **Cálculo de Preço**: Usa modelo de escassez + dados de mercado
2. **Cálculo de Spread**: Dinâmico baseado em volatilidade + inventário
3. **Pennying**: Se concorrente tem preço melhor, supera por 0.01 (dentro da margem de lucro)
4. **Order Diffing**: Só cancela/cria ordens quando preços mudam significativamente
5. **Gestão de Inventário**: Ajusta quotes baseado em holdings atuais

### Fluxo de Ordens

```
A cada 60 segundos:
├── Atualiza saldos das carteiras
├── Busca tickers de mercado (em lote)
├── Para cada mercado:
│   ├── Calcula preço justo (modelo de escassez)
│   ├── Calcula spread dinâmico
│   ├── Aplica estratégia de pennying
│   ├── Verifica inventário/capital
│   ├── Compara com ordens existentes (diff)
│   ├── Cancela ordens obsoletas (se necessário)
│   └── Coloca novas ordens (se necessário)
└── Consulta trades recentes para P&L

Eventos WebSocket (tempo real):
├── Trade no mercado → recotação imediata
└── Mudança no orderbook → recotação imediata
```

---

## 📊 Dashboard

O bot inclui um **dashboard web em tempo real** para monitorar sua atividade de trading.

### Acessando o Dashboard

Com o bot rodando, abra seu navegador e acesse:
```
http://localhost:8081/dashboard
```

### Recursos do Dashboard

- **📈 Gráficos de Preço em Tempo Real**: Candlesticks com dados ao vivo
- **📖 Order Book**: Veja compras e vendas atuais
- **💰 Acompanhamento de P&L**: Monitore seus lucros realizados
- **🎯 Cards de Estratégia**: Visualize estratégias de precificação ativas
- **📋 Lista de Mercados**: Navegação rápida entre todos os mercados
- **🎨 Ferramentas de Desenho**: Adicione linhas de tendência e anotações

### Portas do Dashboard

| Porta | Serviço |
|-------|---------|
| 8080 | Endpoint de saúde (`/health`) |
| 8081 | Dashboard Web (`/dashboard`) |

---

## 📊 Monitoramento

### Health Check

```bash
curl http://localhost:8080/health
```

Resposta:
```json
{
  "status": "healthy",
  "markets_count": 11,
  "circuit_breaker": "CLOSED",
  "websocket_connected": true,
  "realized_pnl": 12.54,
  "orders_placed": 156,
  "total_trades": 23
}
```

### Logs

O bot exibe logs coloridos no console e salva em `logs/bot.log`:
- 🟢 Verde = INFO
- 🟡 Amarelo = WARNING  
- 🔴 Vermelho = ERROR
- 🧪 = Ações em dry run

### Persistência de Métricas

Métricas são salvas em `src/metrics_data.json` a cada 60 segundos e no shutdown.

---

## 📁 Estrutura do Projeto

```
BlockyMarketMaker/
├── run.py                 # Ponto de entrada - execute isso para iniciar
├── config.yaml            # Arquivo principal de configuração
├── requirements.txt       # Dependências Python
├── .env                   # Suas chaves de API (crie este arquivo)
│
├── src/                   # Código fonte
│   ├── main.py            # Lógica principal do bot
│   ├── blocky/            # Cliente da API Blocky
│   ├── dashboard/         # Dashboard web
│   ├── price_model.py     # Precificação por escassez
│   ├── spread_calculator.py
│   ├── trading_helpers.py
│   └── ...
│
├── scripts/               # Scripts utilitários
│   ├── setup.py           # Assistente de configuração
│   └── ...
│
├── docker/                # Configuração Docker
│   └── Dockerfile
│
├── logs/                  # Arquivos de log (criado automaticamente)
│   └── bot.log
│
├── data/                  # Dados de mercado para análise (criado automaticamente)
│
└── tests/                 # Testes unitários
```

---

## 📝 Entendendo as Mensagens de Log

Aqui está o significado das mensagens de log mais comuns:

| Mensagem | Significado |
|----------|-------------|
| `Placed buy order` | Ordem de compra colocada com sucesso |
| `Placed sell order` | Ordem de venda colocada com sucesso |
| `Cancelling order (Diff Mismatch)` | Preço mudou, ordem antiga sendo substituída |
| `Insufficient funds` | Iron insuficiente para colocar ordem |
| `Circuit breaker OPEN` | Muitos erros na API, pausando requisições |
| `WS Event: Trade on X` | Alguém negociou no mercado X |
| `Integrity Check` | Verificação periódica de todas as ordens |
| `🧪 [DRY-RUN]` | Ação simulada (sem ordem real) |

---

## 🔧 Solução de Problemas

| Problema | Solução |
|----------|---------|
| `BLOCKY_API_KEY not set` | Execute `python scripts/setup.py` ou crie o arquivo `.env` |
| `502 Bad Gateway` | API da Blocky está fora. Bot vai tentar novamente a cada 5s. |
| `Circuit breaker OPEN` | Muitos erros na API. Vai recuperar automaticamente em 30s. |
| `Insufficient funds` | Adicione mais Iron na carteira ou reduza `target_value`. |
| `Rate limit reached` | Bot vai auto-throttle. Verifique configurações de `rate_limit`. |
| Nenhuma ordem colocada | Verifique config `enabled_markets`/`disabled_markets`. |
| Dashboard não carrega | Certifique-se que a porta 8081 está livre. Acesse `http://localhost:8081/dashboard` |
| `ModuleNotFoundError` | Ative o ambiente virtual: `source venv/bin/activate` |

### Antes da Sua Primeira Execução

1. ✅ Certifique-se de ter **Iron na sua carteira Blocky**
2. ✅ Comece com `dry_run: true` para testar sem dinheiro real
3. ✅ Use **um único mercado** primeiro: `enabled_markets: [diam_iron]`
4. ✅ Confira o dashboard para ver o que o bot está fazendo

### Testando em Dry Run

Teste sua configuração sem ordens reais:

```yaml
trading:
  dry_run: true
```

Logs vão mostrar prefixo `🧪 [DRY-RUN]` para ações simuladas.

---

</details>

---

## 📄 License

MIT License - Feel free to use and modify!

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first.

---

**Made with ❤️ for the Blocky community**
