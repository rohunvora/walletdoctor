#!/bin/bash
# WalletDoctor API Deployment Script

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== WalletDoctor SSE API Deployment ===${NC}"

# Check environment
if [ "$ENV" != "production" ]; then
    echo -e "${YELLOW}Warning: ENV is not set to 'production'${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Validate required environment variables
echo -e "\n${YELLOW}Checking environment variables...${NC}"
required_vars=(
    "HELIUS_KEY"
    "SECRET_KEY"
    "REDIS_URL"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    else
        echo -e "✓ $var is set"
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo -e "${RED}Error: Missing required environment variables:${NC}"
    printf '%s\n' "${missing_vars[@]}"
    exit 1
fi

# Validate configuration
echo -e "\n${YELLOW}Validating configuration...${NC}"
python3 -c "from src.config.production import validate_config; validate_config()" || {
    echo -e "${RED}Configuration validation failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Configuration valid${NC}"

# Install/update dependencies
echo -e "\n${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt --upgrade

# Run tests
echo -e "\n${YELLOW}Running tests...${NC}"
python -m pytest tests/test_basic_imports.py -v || {
    echo -e "${RED}Basic import tests failed${NC}"
    exit 1
}

# Check API health
echo -e "\n${YELLOW}Checking API health...${NC}"
if lsof -i :5000 > /dev/null 2>&1; then
    echo -e "${YELLOW}Port 5000 is already in use${NC}"
    read -p "Stop existing service? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl stop walletdoctor || pkill -f "gunicorn.*wallet_analytics_api"
        sleep 2
    fi
fi

# Create necessary directories
echo -e "\n${YELLOW}Creating directories...${NC}"
mkdir -p logs
mkdir -p cache

# Start the service
echo -e "\n${YELLOW}Starting service...${NC}"
if [ -f /etc/systemd/system/walletdoctor.service ]; then
    sudo systemctl daemon-reload
    sudo systemctl restart walletdoctor
    sleep 3
    
    if sudo systemctl is-active --quiet walletdoctor; then
        echo -e "${GREEN}✓ Service started successfully${NC}"
    else
        echo -e "${RED}Service failed to start${NC}"
        sudo journalctl -u walletdoctor -n 50
        exit 1
    fi
else
    # Development mode - use gunicorn directly
    echo -e "${YELLOW}Starting in development mode...${NC}"
    
    # Set environment for unified module
    export STREAMING_ENABLED=true
    export IS_PRODUCTION=false
    
    gunicorn src.api.wallet_analytics_api_v3_refactored:app \
        --bind 0.0.0.0:5000 \
        --workers 2 \
        --worker-class aiohttp.GunicornWebWorker \
        --timeout 120 \
        --keepalive 5 \
        --log-level info \
        --daemon
    
    sleep 3
fi

# Verify deployment
echo -e "\n${YELLOW}Verifying deployment...${NC}"

# Check health endpoint
health_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health)
if [ "$health_response" = "200" ]; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed (HTTP $health_response)${NC}"
    exit 1
fi

# Check metrics endpoint
metrics_response=$(curl -s http://localhost:5000/metrics | head -n 5)
if [[ $metrics_response == *"walletdoctor"* ]]; then
    echo -e "${GREEN}✓ Metrics endpoint working${NC}"
else
    echo -e "${YELLOW}⚠ Metrics endpoint may not be working properly${NC}"
fi

# Run production readiness tests
echo -e "\n${YELLOW}Running production readiness tests...${NC}"
python test_production_readiness.py || {
    echo -e "${YELLOW}Some production tests failed - review output above${NC}"
}

echo -e "\n${GREEN}=== Deployment Complete ===${NC}"
echo -e "\nNext steps:"
echo -e "1. Monitor logs: ${YELLOW}journalctl -u walletdoctor -f${NC}"
echo -e "2. Check metrics: ${YELLOW}curl http://localhost:5000/metrics${NC}"
echo -e "3. Test SSE stream: ${YELLOW}curl -H 'X-API-Key: your-key' http://localhost:5000/v4/wallet/ADDRESS/stream${NC}"
echo -e "4. Configure reverse proxy (nginx/caddy)"
echo -e "5. Set up monitoring alerts" 