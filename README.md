# 🤖 BlockyMarketMaker

An automated Market Maker bot for the Blocky Minecraft Economy Server.

Um bot automatizado de Market Making para o servidor de economia Blocky Minecraft.

---

<details>
<summary><strong>🇺🇸 English Documentation</strong></summary>

## 📖 Table of Contents

- [Features](#-features)
- [Requirements](#-requirements)
- [Quick Start](#-quick-start)
- [Running with Docker](#-running-with-docker)
- [Configuration Guide](#-configuration-guide)
- [Understanding the Bot](#-understanding-the-bot)
- [Monitoring](#-monitoring)
- [Troubleshooting](#-troubleshooting)

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
| **Health Endpoint** | HTTP `/health` for monitoring systems |
| **Dry Run Mode** | Test strategies without real orders |
| **Metrics & P&L** | Track your trading performance |

---

## 📋 Requirements

- Python 3.11+ (or Docker)
- Blocky API Key (get it from the Blocky panel)
- (Optional) Discord Webhook URL for alerts

---

## 🚀 Quick Start

### Option 1: Run Locally (Recommended for First Time)

```bash
# 1. Clone the repository
git clone https://github.com/zukrmn/BlockyMarketMaker.git
cd BlockyMarketMaker

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the interactive setup (creates .env file)
python setup.py

# 4. Start the bot
python bot.py
```

The setup wizard will ask for:
1. Your **Blocky API Key**
2. (Optional) **Discord Webhook URL** for alerts

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
python bot.py
```

---

## 🐳 Running with Docker

### Build the Image

```bash
docker build -f Dockerfile.prod -t blocky-market-maker:prod .
```

### Run the Container

**Important:** Create your `.env` file first (via `python setup.py` or manually).

```bash
# Run with .env mounted
docker run --rm \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -p 8080:8080 \
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
      dockerfile: Dockerfile.prod
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./.env:/app/.env:ro
      - ./config.yaml:/app/config.yaml:ro
      - ./metrics_data.json:/app/metrics_data.json
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

The bot outputs colored logs:
- 🟢 Green = INFO
- 🟡 Yellow = WARNING  
- 🔴 Red = ERROR
- 🧪 = Dry run actions

### Metrics Persistence

Metrics are saved to `metrics_data.json` every 60 seconds and on shutdown.

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| `502 Bad Gateway` | Blocky API is down. Bot will auto-retry every 5s. |
| `Circuit breaker OPEN` | Too many API errors. Will auto-recover in 30s. |
| `Insufficient funds` | Add more Iron to your wallet or reduce `target_value`. |
| `Rate limit reached` | Bot will auto-throttle. Check `rate_limit` settings. |
| No orders placed | Check `enabled_markets`/`disabled_markets` config. |

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

- [Recursos](#-recursos)
- [Requisitos](#-requisitos)
- [Início Rápido](#-início-rápido)
- [Rodando com Docker](#-rodando-com-docker)
- [Guia de Configuração](#-guia-de-configuração)
- [Entendendo o Bot](#-entendendo-o-bot)
- [Monitoramento](#-monitoramento)
- [Solução de Problemas](#-solução-de-problemas)

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
| **Endpoint de Saúde** | HTTP `/health` para sistemas de monitoramento |
| **Modo Dry Run** | Teste estratégias sem ordens reais |
| **Métricas & P&L** | Acompanhe sua performance de trading |

---

## 📋 Requisitos

- Python 3.11+ (ou Docker)
- Chave de API da Blocky (obtenha no painel da Blocky)
- (Opcional) URL do Webhook do Discord para alertas

---

## 🚀 Início Rápido

### Opção 1: Rodar Localmente (Recomendado para Primeira Vez)

```bash
# 1. Clone o repositório
git clone https://github.com/zukrmn/BlockyMarketMaker.git
cd BlockyMarketMaker

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Execute o setup interativo (cria arquivo .env)
python setup.py

# 4. Inicie o bot
python bot.py
```

O assistente de configuração vai pedir:
1. Sua **Chave de API da Blocky**
2. (Opcional) **URL do Webhook do Discord** para alertas

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
python bot.py
```

---

## 🐳 Rodando com Docker

### Construir a Imagem

```bash
docker build -f Dockerfile.prod -t blocky-market-maker:prod .
```

### Rodar o Container

**Importante:** Crie seu arquivo `.env` primeiro (via `python setup.py` ou manualmente).

```bash
# Rodar com .env montado
docker run --rm \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -p 8080:8080 \
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
      dockerfile: Dockerfile.prod
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./.env:/app/.env:ro
      - ./config.yaml:/app/config.yaml:ro
      - ./metrics_data.json:/app/metrics_data.json
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

O bot exibe logs coloridos:
- 🟢 Verde = INFO
- 🟡 Amarelo = WARNING  
- 🔴 Vermelho = ERROR
- 🧪 = Ações em dry run

### Persistência de Métricas

Métricas são salvas em `metrics_data.json` a cada 60 segundos e no shutdown.

---

## 🔧 Solução de Problemas

| Problema | Solução |
|----------|---------|
| `502 Bad Gateway` | API da Blocky está fora. Bot vai tentar novamente a cada 5s. |
| `Circuit breaker OPEN` | Muitos erros na API. Vai recuperar automaticamente em 30s. |
| `Insufficient funds` | Adicione mais Iron na carteira ou reduza `target_value`. |
| `Rate limit reached` | Bot vai auto-throttle. Verifique configurações de `rate_limit`. |
| Nenhuma ordem colocada | Verifique config `enabled_markets`/`disabled_markets`. |

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
