# Production Deployment Guide

## Overview

This guide covers deploying the WalletDoctor SSE Streaming API to production with proper security, monitoring, and performance optimization.

## Prerequisites

- Python 3.9+
- Redis instance (for rate limiting)
- TLS certificate (HTTPS required)
- Monitoring infrastructure (Prometheus/Grafana recommended)
- Log aggregation system (ELK stack or similar)

## Environment Setup

### 1. Create Production Environment File

```bash
# .env.production
ENV=production
SECRET_KEY=<generate-secure-32-char-key>

# API Configuration
API_KEY_REQUIRED=true
ALLOWED_ORIGINS=https://app.walletdoctor.com,https://www.walletdoctor.com

# Blockchain APIs
HELIUS_KEY=<your-helius-api-key>
BIRDEYE_API_KEY=<your-birdeye-api-key>

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_STREAMING_CONNECTIONS=10
REDIS_URL=redis://:<password>@redis.example.com:6379/0

# SSE Configuration
SSE_KEEPALIVE_INTERVAL=30
SSE_MAX_STREAM_DURATION=600
SSE_BATCH_SIZE=100

# Monitoring
MONITORING_ENABLED=true
PROMETHEUS_ENABLED=true
LOG_LEVEL=INFO
SENTRY_DSN=https://<key>@sentry.io/<project>

# Performance
PARALLEL_PAGES=40
MAX_WALLET_SIZE=20000
```

### 2. Generate Secure Keys

```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# Generate API keys for clients
python -c "from src.lib.sse_auth import generate_api_key; print(generate_api_key())"
```

## Deployment Steps

### 1. Application Setup

```bash
# Clone repository
git clone https://github.com/walletdoctor/api.git
cd api

# Install dependencies
pip install -r requirements.txt

# Validate configuration
python -c "from src.config.production import validate_config; validate_config()"
```

### 2. Gunicorn Configuration

Create `gunicorn.conf.py`:

```python
import multiprocessing
import os

# Server socket
bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '5000')}"
backlog = 2048

# Worker processes
workers = int(os.getenv('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'aiohttp.GunicornWebWorker'
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 5

# Logging
accesslog = '-'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
errorlog = '-'
loglevel = 'info'

# Process naming
proc_name = 'walletdoctor-api'

# Server mechanics
daemon = False
pidfile = '/var/run/walletdoctor.pid'
user = 'walletdoctor'
group = 'walletdoctor'
tmp_upload_dir = None

# SSL (if not using reverse proxy)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'
```

### 3. Systemd Service

Create `/etc/systemd/system/walletdoctor.service`:

```ini
[Unit]
Description=WalletDoctor SSE Streaming API
After=network.target redis.service

[Service]
Type=notify
User=walletdoctor
Group=walletdoctor
WorkingDirectory=/opt/walletdoctor
Environment="PATH=/opt/walletdoctor/venv/bin"
EnvironmentFile=/opt/walletdoctor/.env.production
ExecStart=/opt/walletdoctor/venv/bin/gunicorn \
    --config /opt/walletdoctor/gunicorn.conf.py \
    src.api.wallet_analytics_api_v3:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/walletdoctor/logs

[Install]
WantedBy=multi-user.target
```

### 4. Nginx Configuration

```nginx
upstream walletdoctor {
    server 127.0.0.1:5000 fail_timeout=0;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name api.walletdoctor.com;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/api.walletdoctor.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.walletdoctor.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # SSE specific settings
    location ~ ^/v4/wallet/.*/stream$ {
        proxy_pass http://walletdoctor;
        proxy_http_version 1.1;
        
        # SSE requirements
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
        
        # Timeouts for long-lived connections
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        
        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Regular API endpoints
    location / {
        proxy_pass http://walletdoctor;
        proxy_http_version 1.1;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }

    # Monitoring endpoints (restricted)
    location /metrics {
        proxy_pass http://walletdoctor;
        allow 10.0.0.0/8;  # Internal network only
        deny all;
    }
}
```

## Monitoring Setup

### 1. Prometheus Configuration

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'walletdoctor'
    static_configs:
      - targets: ['api.walletdoctor.com:443']
    scheme: https
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### 2. Grafana Dashboard

Import the dashboard from `monitoring/grafana-dashboard.json` or create with:

- Active SSE streams gauge
- Streams per minute rate
- Error rate percentage
- P95 stream duration
- Trades yielded per minute
- API response times

### 3. Alerting Rules

```yaml
groups:
  - name: walletdoctor
    rules:
      - alert: HighErrorRate
        expr: walletdoctor_error_rate > 5
        for: 5m
        annotations:
          summary: "High error rate detected"
          
      - alert: TooManyActiveStreams
        expr: walletdoctor_active_streams > 1000
        for: 2m
        annotations:
          summary: "Too many active SSE connections"
          
      - alert: APIDown
        expr: up{job="walletdoctor"} == 0
        for: 1m
        annotations:
          summary: "WalletDoctor API is down"
```

## Performance Tuning

### 1. Linux Kernel Parameters

Add to `/etc/sysctl.conf`:

```bash
# Increase max connections
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535

# TCP optimization for SSE
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 6

# Buffer sizes
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728

# File descriptors
fs.file-max = 2097152
```

### 2. Service Limits

Add to systemd service:

```ini
[Service]
LimitNOFILE=65535
LimitNPROC=65535
```

## Security Checklist

- [ ] API keys required for all endpoints
- [ ] HTTPS/TLS configured and forced
- [ ] CORS origins restricted (no wildcards)
- [ ] Security headers configured
- [ ] Rate limiting enabled
- [ ] Redis password protected
- [ ] Monitoring endpoints IP restricted
- [ ] Error messages don't leak internals
- [ ] Logs don't contain sensitive data
- [ ] Regular security updates scheduled

## Deployment Commands

```bash
# Deploy application
sudo systemctl daemon-reload
sudo systemctl enable walletdoctor
sudo systemctl start walletdoctor

# Check status
sudo systemctl status walletdoctor
sudo journalctl -u walletdoctor -f

# Reload after config changes
sudo systemctl reload walletdoctor

# Nginx
sudo nginx -t
sudo systemctl reload nginx
```

## Rollback Plan

1. Keep previous version tagged
2. Database migrations reversible
3. Feature flags for new features
4. Blue-green deployment ready
5. Monitoring alerts configured

## Post-Deployment

1. Verify all endpoints responding
2. Check SSE streams working
3. Monitor error rates
4. Verify rate limiting active
5. Test API key authentication
6. Check monitoring data flowing
7. Perform load test
8. Update documentation

## Support

- Logs: `/var/log/walletdoctor/`
- Metrics: `https://api.walletdoctor.com/metrics`
- Health: `https://api.walletdoctor.com/health`
- Monitoring: Grafana dashboard
- Alerts: PagerDuty/Slack integration 