#!/bin/bash
# Entrypoint script for Blocky Market Maker Bot
# Runs setup if .env doesn't exist, then starts the bot

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🎮 Blocky Market Maker Bot${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Arquivo .env não encontrado. Iniciando configuração...${NC}"
    echo ""
    python setup.py
    
    # Check if setup was successful
    if [ ! -f .env ]; then
        echo -e "${YELLOW}Setup cancelado ou falhou. Saindo.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}🚀 Iniciando bot...${NC}"
echo ""

# Run the bot
exec python bot.py
