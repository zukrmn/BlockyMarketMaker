# BlockyMarketMaker

An automated Market Maker bot for the Blocky Minecraft Economy Server.

Um bot automatizado de Market Making para o servidor de economia Blocky Minecraft.

---

<details>
<summary><strong>English Documentation</strong></summary>

## Table of Contents

- [What is Market Making?](#what-is-market-making)
- [Features](#features)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Running with Docker](#running-with-docker)
- [Configuration Guide](#configuration-guide)
- [Understanding the Bot](#understanding-the-bot)
- [Dashboard](#dashboard)
- [Monitoring](#monitoring)
- [Project Structure](#project-structure)
- [Understanding Log Messages](#understanding-log-messages)
- [Troubleshooting](#troubleshooting)

---

## What is Market Making?

**Market Making** is a trading strategy where you provide liquidity to a market by placing **buy** and **sell** orders simultaneously.

### Simple Example

Imagine you want to trade diamonds:
- You place a **BUY order** at 49 Iron (you're willing to buy diamonds for 49)
- You place a **SELL order** at 51 Iron (you're willing to sell diamonds for 51)

When someone sells you a diamond for 49 and later someone buys it for 51, you profit 2 Iron.

**The "spread"** (51 - 49 = 2 Iron, or ~4%) is your profit margin.

### Why use a bot?

- Markets operate 24/7 - manual monitoring is impractical
- Automatic price adjustments based on supply/demand
- Simultaneous management of dozens of markets
- Millisecond response to market changes

---

## Features

| Feature | Description |
|---------|-------------|
| Dynamic Spread | Automatically adjusts spreads based on volatility and inventory |
| Dynamic Capital Allocation | Automatically calculates order sizes based on your Iron inventory |
| Smart Order Diffing | Only updates orders when necessary (reduces API calls) |
| Pennying Strategy | Automatically beats competitors by 0.01 while maintaining margins |
| Scarcity-Based Pricing | Prices items based on remaining world supply |
| Circuit Breaker | Protects against API failures with automatic recovery |
| Rate Limiting | Respects API limits (30 req/sec) |
| Discord/Slack Alerts | Notifications for errors and important events |
| Web Dashboard | Real-time trading dashboard with charts |
| Health Endpoint | HTTP `/health` for monitoring systems |
| Dry Run Mode | Test strategies without real orders |
| Metrics & P&L | Track trading performance |


---

## Requirements

### Minimum Requirements

- **Python 3.11+** (or Docker)
- **Blocky API Key** (see below)
- **Stable internet connection** (for WebSocket)
- **~100MB RAM**

### Obtaining Your Blocky API Key

1. Access the Blocky web panel: `https://craft.blocky.com.br`
2. Log in with your Minecraft account
3. Navigate to **Settings** or **API**
4. Generate a new API key
5. Copy and store securely

> **Important:** Never share your API key.

### Optional

- Discord Webhook URL (for alerts)
- Docker (for containerized deployment)

---

## Quick Start

### Option 1: Windows Executable (Easiest)

For Windows users who prefer not to install Python:

1. Download `BlockyMarketMaker.exe` from the [Releases](https://github.com/zukrmn/BlockyMarketMaker/releases) page
2. Double-click to run
3. Complete the setup wizard:
   - Enter your Blocky API key
   - Configure trading settings
   - Select markets
4. The bot will start automatically

The setup wizard explains each setting and helps you configure unique values to avoid conflicts with other users.

---

### Option 2: Run Locally with Python

#### Step 1: Install Python

**Windows:**
1. Download Python 3.11+ from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. Check **"Add Python to PATH"** during installation
4. Verify installation: `python --version`

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
# Clone the repository
git clone https://github.com/zukrmn/BlockyMarketMaker.git
cd BlockyMarketMaker

# Create a virtual environment (recommended)
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the interactive setup (creates .env file)
python scripts/setup.py

# Start the bot
python run.py
```

The setup wizard will prompt for:
1. Your **Blocky API Key**
2. (Optional) **Discord Webhook URL** for alerts

#### Step 3: Stopping the Bot

Press `Ctrl+C` to stop the bot. It will:
- Cancel all open orders
- Save metrics to disk
- Close connections properly

### Option 3: Manual Configuration

Create a `.env` file:

```bash
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

## Running with Docker

### Build the Image

```bash
docker build -f docker/Dockerfile -t blocky-market-maker:prod .
```

### Run the Container

Create your `.env` file first via `python scripts/setup.py` or manually.

```bash
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
      - "8080:8080"
      - "8081:8081"
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

Run:

```bash
docker-compose up -d
```

---

## Configuration Guide

All settings are in `config.yaml`. Environment variables override YAML values.

### Trading Parameters

```yaml
trading:
  dry_run: false           # true = simulate only, no real orders
  enabled_markets: []      # Whitelist: empty = all markets
  disabled_markets: []     # Blacklist: never trade these
  spread: 0.05             # 5% fixed spread (if dynamic_spread disabled)
  min_spread_ticks: 0.01   # Minimum price difference between buy/sell
  target_value: 10.0       # Target order value in Iron
  max_quantity: 6400       # Maximum order quantity
  refresh_interval: 60     # Seconds between integrity checks
```

#### Examples

**Trade specific markets only:**
```yaml
trading:
  enabled_markets: [diam_iron, gold_iron, lapi_iron]
```

**Exclude markets:**
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
  enabled: true
  base_spread: 0.03        # 3% base spread
  volatility_multiplier: 2.0
  inventory_impact: 0.02
  min_spread: 0.01         # 1% minimum
  max_spread: 0.15         # 15% maximum
  volatility_window: 24    # Hours of OHLCV data
```

**Calculation:**
- `spread = base_spread + volatility_adj + inventory_adj`
- High volatility → wider spreads
- Overstocked → wider buy spread, tighter sell spread

### Dynamic Capital Allocation

Automatically calculates order sizes based on your Iron inventory:

```yaml
capital_allocation:
  enabled: true                   # Enable dynamic allocation
  base_reserve_ratio: 0.10        # Minimum 10% reserve
  max_reserve_ratio: 0.30         # Maximum 30% reserve
  min_order_value: 0.10           # Minimum order value
  priority_markets: [diam_iron, gold_iron, slme_iron]  # Higher allocation
  priority_boost: 1.5             # 50% more for priority markets
```

**Formula:**
```
Reserve Ratio = 10% + (number_of_markets / 100)
Reserve = Total Iron × Reserve Ratio
Per Market = (Total Iron - Reserve) / number_of_markets
```

**Example with 500 Iron and 37 markets:**
- Reserve Ratio: 10% + 37% = 30% (capped)
- Reserve: 150 Iron (kept safe)
- Deployable: 350 Iron
- Per Market: ~9.5 Iron

### Price Model

```yaml
price_model:
  cache_ttl: 60
  
  base_prices:
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

Pricing formula:
- `fair_price = base_price × (total_supply / remaining_supply)`

### Rate Limiting & Circuit Breaker

```yaml
rate_limit:
  max_requests: 30
  window_seconds: 1.0

circuit_breaker:
  failure_threshold: 5
  recovery_timeout: 30.0
```

### Alerts

```yaml
alerts:
  enabled: true
  webhook_type: "discord"
  min_level: "warning"
  rate_limit_seconds: 60
```

Set webhook URL via environment:
```bash
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### Health Endpoint

```yaml
health:
  enabled: true
  port: 8080
```

Access: `http://localhost:8080/health`

---

## Understanding the Bot

### Trading Strategy

1. **Price Calculation**: Scarcity model + market data
2. **Spread Calculation**: Dynamic based on volatility + inventory
3. **Pennying**: Beat competitors by 0.01 within profit margin
4. **Order Diffing**: Only update orders when prices change significantly
5. **Inventory Management**: Adjust quotes based on holdings

### Order Flow

```
Every 60 seconds:
├── Update wallet balances
├── Fetch market tickers (batch)
├── For each market:
│   ├── Calculate fair price
│   ├── Calculate dynamic spread
│   ├── Apply pennying strategy
│   ├── Check inventory/capital
│   ├── Diff with existing orders
│   ├── Cancel stale orders
│   └── Place new orders
└── Poll trades for P&L

WebSocket events (real-time):
├── Trade → immediate requote
└── Orderbook change → immediate requote
```

---

## Dashboard

The bot includes a real-time web dashboard.

### Access

With the bot running:
```
http://localhost:8081/dashboard
```

### Features

- Live candlestick charts
- Order book display
- P&L tracking
- Strategy visualization
- Market navigation
- Drawing tools for chart analysis

### Ports

| Port | Service |
|------|---------|
| 8080 | Health endpoint |
| 8081 | Web Dashboard |

---

## Monitoring

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

Logs are output to console and saved to `logs/bot.log`:
- Green = INFO
- Yellow = WARNING  
- Red = ERROR
- `[DRY-RUN]` = Simulated actions

### Metrics Persistence

Metrics saved to `src/metrics_data.json` every 60 seconds and on shutdown.

---

## Project Structure

```
BlockyMarketMaker/
├── run.py                 # Entry point
├── config.yaml            # Configuration
├── requirements.txt       # Dependencies
├── .env                   # API keys (create this)
│
├── src/                   # Source code
│   ├── main.py            # Bot logic
│   ├── blocky/            # API client
│   ├── dashboard/         # Web dashboard
│   ├── price_model.py     # Pricing
│   ├── spread_calculator.py
│   ├── trading_helpers.py
│   └── ...
│
├── scripts/               # Utilities
│   └── setup.py           # Setup wizard
│
├── docker/                # Docker config
│   └── Dockerfile
│
├── logs/                  # Log files
├── data/                  # Market data
└── tests/                 # Unit tests
```

---

## Understanding Log Messages

| Message | Meaning |
|---------|---------|
| `Placed buy order` | Buy order placed successfully |
| `Placed sell order` | Sell order placed successfully |
| `Cancelling order (Diff Mismatch)` | Price changed, replacing order |
| `Insufficient funds` | Not enough Iron for order |
| `Circuit breaker OPEN` | API errors, pausing requests |
| `WS Event: Trade on X` | Trade occurred on market X |
| `Integrity Check` | Periodic order verification |
| `[DRY-RUN]` | Simulated action |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `BLOCKY_API_KEY not set` | Run `python scripts/setup.py` or create `.env` |
| `502 Bad Gateway` | API down, auto-retry in 5s |
| `Circuit breaker OPEN` | Too many errors, auto-recovery in 30s |
| `Insufficient funds` | Add Iron or reduce `target_value` |
| `Rate limit reached` | Auto-throttle active |
| No orders placed | Check `enabled_markets`/`disabled_markets` |
| Dashboard not loading | Verify port 8081 is available |
| `ModuleNotFoundError` | Activate venv: `source venv/bin/activate` |

### Before First Run

1. Ensure you have **Iron in your Blocky wallet**
2. Start with `dry_run: true` to test
3. Use single market first: `enabled_markets: [diam_iron]`
4. Monitor via dashboard

### Dry Run Testing

```yaml
trading:
  dry_run: true
```

Logs show `[DRY-RUN]` prefix for simulated actions.

---

## Building the Windows Executable

For developers who want to build the `.exe` themselves.

### Prerequisites

1. **Python 3.11+** installed
   - Download from [python.org](https://www.python.org/downloads/)
   - During installation, check **"Add Python to PATH"**
   - Verify: `python --version`

2. **Git** installed
   - Download from [git-scm.com](https://git-scm.com/downloads)

### Build Steps

```bash
# 1. Clone the repository
git clone https://github.com/zukrmn/BlockyMarketMaker.git
cd BlockyMarketMaker

# 2. Install project dependencies
pip install -r requirements.txt

# 3. Install PyInstaller
pip install pyinstaller

# 4. Build the executable
build_exe.bat
```

Or build manually:
```bash
pyinstaller blocky.spec --clean
```

### Build Output

- **Executable**: `dist/BlockyMarketMaker.exe`
- **Expected size**: ~50-80MB
- **Build time**: 1-3 minutes

### Testing the Build

1. Create a new empty folder (e.g., `C:\BlockyTest\`)
2. Copy `dist/BlockyMarketMaker.exe` to this folder
3. Copy `config.yaml` to the same folder (as template)
4. Double-click `BlockyMarketMaker.exe`
5. The setup wizard should open

### Distributing

To share with other users, they only need:
- `BlockyMarketMaker.exe`
- `config.yaml` (optional, will use defaults if missing)

Users do NOT need Python installed.

### Troubleshooting Build Issues

| Problem | Solution |
|---------|----------|
| `python not found` | Reinstall Python with "Add to PATH" checked |
| `pip not found` | Run `python -m pip install --upgrade pip` |
| `ModuleNotFoundError` during build | Run `pip install <module_name>` and rebuild |
| Build succeeds but exe crashes | Check for missing hidden imports in `blocky.spec` |
| Antivirus blocks/deletes exe | Add exception for `dist/` folder (false positive) |
| Windows SmartScreen warning | Click "More info" → "Run anyway" |
| Exe size is 200MB+ | Something wrong with spec, rebuild with `--clean` |

### Adding an Icon (Optional)

1. Create or download a `.ico` file
2. Save as `img/icon.ico`
3. Uncomment the icon line in `blocky.spec`:
   ```python
   icon='img/icon.ico',
   ```
4. Rebuild

---

</details>

---

<details open>
<summary><strong>Documentação em Português</strong></summary>

## Índice

- [O que é Market Making?](#o-que-é-market-making)
- [Recursos](#recursos)
- [Requisitos](#requisitos)
- [Início Rápido](#início-rápido)
- [Rodando com Docker](#rodando-com-docker)
- [Guia de Configuração](#guia-de-configuração)
- [Entendendo o Bot](#entendendo-o-bot)
- [Dashboard](#dashboard-1)
- [Monitoramento](#monitoramento)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Entendendo as Mensagens de Log](#entendendo-as-mensagens-de-log)
- [Solução de Problemas](#solução-de-problemas)

---

## O que é Market Making?

**Market Making** é uma estratégia de trading onde você fornece liquidez ao mercado colocando ordens de **compra** e **venda** simultaneamente.

### Exemplo Simples

Imagine que você quer negociar diamantes:
- Você coloca uma **ordem de COMPRA** a 49 Iron
- Você coloca uma **ordem de VENDA** a 51 Iron

Quando alguém te vende um diamante por 49 e depois alguém compra por 51, você lucra 2 Iron.

**O "spread"** (51 - 49 = 2 Iron, ou ~4%) é sua margem de lucro.

### Por que usar um bot?

- Mercados funcionam 24/7 - monitoramento manual é impraticável
- Ajuste automático de preços baseado em oferta/demanda
- Gerenciamento simultâneo de dezenas de mercados
- Resposta em milissegundos a mudanças de mercado

---

## Recursos

| Recurso | Descrição |
|---------|-----------|
| Spread Dinâmico | Ajusta spreads baseado em volatilidade e inventário |
| Alocação Dinâmica de Capital | Calcula tamanho das ordens baseado no seu inventário de Iron |
| Smart Order Diffing | Atualiza ordens apenas quando necessário |
| Estratégia de Pennying | Supera concorrentes por 0.01 mantendo margem |
| Precificação por Escassez | Preços baseados na oferta restante |
| Circuit Breaker | Proteção contra falhas com recuperação automática |
| Rate Limiting | Respeita limites da API (30 req/seg) |
| Alertas Discord/Slack | Notificações de erros e eventos |
| Dashboard Web | Dashboard em tempo real com gráficos |
| Endpoint de Saúde | HTTP `/health` para monitoramento |
| Modo Dry Run | Teste sem ordens reais |
| Métricas & P&L | Acompanhamento de performance |

---

## Requisitos

### Requisitos Mínimos

- **Python 3.11+** (ou Docker)
- **Chave de API da Blocky** (veja abaixo)
- **Conexão estável com internet** (para WebSocket)
- **~100MB RAM**

### Obtendo a Chave de API

1. Acesse o painel: `https://craft.blocky.com.br`
2. Faça login com sua conta Minecraft
3. Navegue até **Configurações** ou **API**
4. Gere uma nova chave
5. Copie e guarde com segurança

> **Importante:** Nunca compartilhe sua chave de API.

### Opcional

- URL de Webhook do Discord (para alertas)
- Docker (para deploy containerizado)

---

## Início Rápido

### Opção 1: Executável Windows (Mais Fácil)

Para usuários Windows que preferem não instalar Python:

1. Baixe `BlockyMarketMaker.exe` da página de [Releases](https://github.com/zukrmn/BlockyMarketMaker/releases)
2. Dê duplo clique para executar
3. Complete o assistente de configuração:
   - Digite sua chave API da Blocky
   - Configure parâmetros de trading
   - Selecione mercados
4. O bot iniciará automaticamente

O assistente explica cada configuração e ajuda a definir valores únicos para evitar conflitos com outros usuários.

---

### Opção 2: Rodar Localmente com Python

#### Passo 1: Instalar Python

**Windows:**
1. Baixe Python 3.11+ em [python.org](https://www.python.org/downloads/)
2. Execute o instalador
3. Marque **"Add Python to PATH"**
4. Verifique: `python --version`

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
# Clone o repositório
git clone https://github.com/zukrmn/BlockyMarketMaker.git
cd BlockyMarketMaker

# Crie ambiente virtual (recomendado)
python -m venv venv

# Ative o ambiente virtual
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Instale dependências
pip install -r requirements.txt

# Execute o setup interativo
python scripts/setup.py

# Inicie o bot
python run.py
```

O assistente pedirá:
1. Sua **Chave de API da Blocky**
2. (Opcional) **URL do Webhook do Discord**

#### Passo 3: Parando o Bot

Pressione `Ctrl+C` para parar. O bot irá:
- Cancelar ordens abertas
- Salvar métricas
- Fechar conexões

### Opção 3: Configuração Manual

Crie um arquivo `.env`:

```bash
BLOCKY_API_KEY=sua-api-key-aqui
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
ALERT_WEBHOOK_TYPE=discord
```

Execute:

```bash
pip install -r requirements.txt
python run.py
```

---

## Rodando com Docker

### Construir a Imagem

```bash
docker build -f docker/Dockerfile -t blocky-market-maker:prod .
```

### Rodar o Container

Crie o arquivo `.env` primeiro.

```bash
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
      - "8080:8080"
      - "8081:8081"
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

Execute:

```bash
docker-compose up -d
```

---

## Guia de Configuração

Configurações em `config.yaml`. Variáveis de ambiente sobrescrevem o YAML.

### Parâmetros de Trading

```yaml
trading:
  dry_run: false           # true = apenas simula
  enabled_markets: []      # Whitelist: vazio = todos
  disabled_markets: []     # Blacklist
  spread: 0.05             # 5% spread fixo
  min_spread_ticks: 0.01
  target_value: 10.0       # Valor em Iron
  max_quantity: 6400
  refresh_interval: 60
```

#### Exemplos

**Mercados específicos:**
```yaml
trading:
  enabled_markets: [diam_iron, gold_iron, lapi_iron]
```

**Excluir mercados:**
```yaml
trading:
  disabled_markets: [sand_iron, dirt_iron]
```

**Testar sem ordens:**
```yaml
trading:
  dry_run: true
```

### Spread Dinâmico

```yaml
dynamic_spread:
  enabled: true
  base_spread: 0.03
  volatility_multiplier: 2.0
  inventory_impact: 0.02
  min_spread: 0.01
  max_spread: 0.15
  volatility_window: 24
```

**Cálculo:**
- `spread = base + volatilidade + inventário`
- Alta volatilidade → spreads maiores
- Excesso de estoque → spread de compra maior

### Alocação Dinâmica de Capital

Calcula automaticamente o tamanho das ordens baseado no seu Iron:

```yaml
capital_allocation:
  enabled: true                   # Habilitar alocação dinâmica
  base_reserve_ratio: 0.10        # Mínimo 10% de reserva
  max_reserve_ratio: 0.30         # Máximo 30% de reserva
  min_order_value: 0.10           # Valor mínimo de ordem
  priority_markets: [diam_iron, gold_iron, slme_iron]  # Maior alocação
  priority_boost: 1.5             # 50% a mais para mercados prioritários
```

**Fórmula:**
```
Reserva = 10% + (número_de_mercados / 100)
Reserva em Iron = Total × Reserva
Por Mercado = (Total - Reserva) / número_de_mercados
```

**Exemplo com 500 Iron e 37 mercados:**
- Reserva: 30% (cap) = 150 Iron guardados
- Disponível: 350 Iron
- Por Mercado: ~9.5 Iron

### Modelo de Preço

```yaml
price_model:
  cache_ttl: 60
  
  base_prices:
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

Fórmula:
- `preço_justo = preço_base × (supply_total / supply_restante)`

### Rate Limiting & Circuit Breaker

```yaml
rate_limit:
  max_requests: 30
  window_seconds: 1.0

circuit_breaker:
  failure_threshold: 5
  recovery_timeout: 30.0
```

### Alertas

```yaml
alerts:
  enabled: true
  webhook_type: "discord"
  min_level: "warning"
  rate_limit_seconds: 60
```

Webhook via ambiente:
```bash
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### Endpoint de Saúde

```yaml
health:
  enabled: true
  port: 8080
```

Acesse: `http://localhost:8080/health`

---

## Entendendo o Bot

### Estratégia de Trading

1. **Cálculo de Preço**: Modelo de escassez + dados de mercado
2. **Cálculo de Spread**: Dinâmico (volatilidade + inventário)
3. **Pennying**: Superar concorrentes por 0.01
4. **Order Diffing**: Atualizar apenas quando necessário
5. **Gestão de Inventário**: Ajustar quotes por holdings

### Fluxo de Ordens

```
A cada 60 segundos:
├── Atualiza saldos
├── Busca tickers (lote)
├── Para cada mercado:
│   ├── Calcula preço justo
│   ├── Calcula spread
│   ├── Aplica pennying
│   ├── Verifica capital
│   ├── Compara ordens
│   ├── Cancela obsoletas
│   └── Coloca novas
└── Consulta trades para P&L

WebSocket (tempo real):
├── Trade → recotação imediata
└── Mudança orderbook → recotação
```

---

## Dashboard

Dashboard web em tempo real incluído.

### Acesso

Com o bot rodando:
```
http://localhost:8081/dashboard
```

### Recursos

- Gráficos candlestick ao vivo
- Exibição do order book
- Acompanhamento P&L
- Visualização de estratégias
- Navegação entre mercados
- Ferramentas de desenho

### Portas

| Porta | Serviço |
|-------|---------|
| 8080 | Endpoint de saúde |
| 8081 | Dashboard Web |

---

## Monitoramento

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

Logs no console e em `logs/bot.log`:
- Verde = INFO
- Amarelo = WARNING  
- Vermelho = ERROR
- `[DRY-RUN]` = Ações simuladas

### Persistência

Métricas salvas em `src/metrics_data.json` a cada 60s e no shutdown.

---

## Estrutura do Projeto

```
BlockyMarketMaker/
├── run.py                 # Ponto de entrada
├── config.yaml            # Configuração
├── requirements.txt       # Dependências
├── .env                   # Chaves (criar)
│
├── src/                   # Código fonte
│   ├── main.py            # Lógica do bot
│   ├── blocky/            # Cliente API
│   ├── dashboard/         # Dashboard web
│   ├── price_model.py     # Precificação
│   ├── spread_calculator.py
│   ├── trading_helpers.py
│   └── ...
│
├── scripts/               # Utilitários
│   └── setup.py           # Assistente
│
├── docker/                # Config Docker
│   └── Dockerfile
│
├── logs/                  # Logs
├── data/                  # Dados de mercado
└── tests/                 # Testes
```

---

## Entendendo as Mensagens de Log

| Mensagem | Significado |
|----------|-------------|
| `Placed buy order` | Compra colocada com sucesso |
| `Placed sell order` | Venda colocada com sucesso |
| `Cancelling order (Diff Mismatch)` | Preço mudou, substituindo |
| `Insufficient funds` | Iron insuficiente |
| `Circuit breaker OPEN` | Erros na API, pausando |
| `WS Event: Trade on X` | Trade no mercado X |
| `Integrity Check` | Verificação periódica |
| `[DRY-RUN]` | Ação simulada |

---

## Solução de Problemas

| Problema | Solução |
|----------|---------|
| `BLOCKY_API_KEY not set` | Execute `python scripts/setup.py` ou crie `.env` |
| `502 Bad Gateway` | API fora, retry em 5s |
| `Circuit breaker OPEN` | Muitos erros, recovery em 30s |
| `Insufficient funds` | Adicione Iron ou reduza `target_value` |
| `Rate limit reached` | Auto-throttle ativo |
| Sem ordens | Verifique `enabled_markets`/`disabled_markets` |
| Dashboard não carrega | Verifique porta 8081 |
| `ModuleNotFoundError` | Ative venv: `source venv/bin/activate` |

### Antes da Primeira Execução

1. Tenha **Iron na carteira Blocky**
2. Comece com `dry_run: true`
3. Use um mercado: `enabled_markets: [diam_iron]`
4. Monitore via dashboard

### Teste Dry Run

```yaml
trading:
  dry_run: true
```

Logs mostram `[DRY-RUN]` para ações simuladas.

---

## Compilando o Executável Windows

Para desenvolvedores que desejam compilar o `.exe`.

### Pré-requisitos

1. **Python 3.11+** instalado
   - Baixe em [python.org](https://www.python.org/downloads/)
   - Durante a instalação, marque **"Add Python to PATH"**
   - Verifique: `python --version`

2. **Git** instalado
   - Baixe em [git-scm.com](https://git-scm.com/downloads)

### Passos para Compilar

```bash
# 1. Clone o repositório
git clone https://github.com/zukrmn/BlockyMarketMaker.git
cd BlockyMarketMaker

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Instale o PyInstaller
pip install pyinstaller

# 4. Compile o executável
build_exe.bat
```

Ou compile manualmente:
```bash
pyinstaller blocky.spec --clean
```

### Resultado da Compilação

- **Executável**: `dist/BlockyMarketMaker.exe`
- **Tamanho esperado**: ~50-80MB
- **Tempo de build**: 1-3 minutos

### Testando o Build

1. Crie uma pasta vazia (ex: `C:\BlockyTest\`)
2. Copie `dist/BlockyMarketMaker.exe` para esta pasta
3. Copie `config.yaml` para a mesma pasta (como template)
4. Dê duplo clique em `BlockyMarketMaker.exe`
5. O assistente de configuração deve abrir

### Distribuindo

Para compartilhar com outros usuários, eles precisam apenas de:
- `BlockyMarketMaker.exe`
- `config.yaml` (opcional, usa padrões se ausente)

Usuários NÃO precisam ter Python instalado.

### Solução de Problemas de Build

| Problema | Solução |
|----------|---------|
| `python not found` | Reinstale Python marcando "Add to PATH" |
| `pip not found` | Execute `python -m pip install --upgrade pip` |
| `ModuleNotFoundError` durante build | Execute `pip install <modulo>` e recompile |
| Build funciona mas exe trava | Verifique hidden imports em `blocky.spec` |
| Antivírus bloqueia/deleta exe | Adicione exceção para pasta `dist/` (falso positivo) |
| Aviso do Windows SmartScreen | Clique "Mais informações" → "Executar assim mesmo" |
| Exe com 200MB+ | Algo errado no spec, recompile com `--clean` |

### Adicionando um Ícone (Opcional)

1. Crie ou baixe um arquivo `.ico`
2. Salve como `img/icon.ico`
3. Descomente a linha do ícone em `blocky.spec`:
   ```python
   icon='img/icon.ico',
   ```
4. Recompile

---

</details>

---

## License

MIT License - Feel free to use and modify.

## Contributing

Pull requests welcome. For major changes, open an issue first.

---

**Made for the Blocky community**
