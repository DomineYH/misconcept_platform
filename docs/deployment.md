# Production Deployment Guide

**Project**: Misconception Dialogue Simulator
**Version**: 1.0.0
**Last Updated**: 2025-11-06

## Prerequisites

### System Requirements
- **OS**: Ubuntu 20.04 LTS or newer
- **Python**: 3.11 or higher
- **RAM**: Minimum 2GB, recommended 4GB+
- **Storage**: Minimum 10GB free space
- **Network**: HTTPS certificate (Let's Encrypt recommended)

### Required Services
- **Web Server**: nginx (reverse proxy)
- **Process Manager**: systemd or supervisor
- **SSL**: certbot for Let's Encrypt certificates

## Installation Steps

### 1. Clone Repository
```bash
cd /opt
git clone https://github.com/your-org/misconcept_platform.git
cd misconcept_platform
```

### 2. Create Virtual Environment
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -e "."
```

### 3. Configure Environment Variables

Create `.env` file in project root from the canonical template:

```bash
cp .env.example .env
# `.env copy.example` is kept synchronized as a compatibility copy.

# OpenAI API Configuration (Responses API only)
OPENAI_API_KEY=sk-your-openai-api-key-here
CHAT_MODEL=gpt-5-mini
ANALYSIS_MODEL=gpt-5.2
DIALOGUE_ANALYSIS_MODEL=gpt-5.2

# Reasoning controls
ANALYSIS_REASONING=high
ANALYSIS_MISCONCEPTION_REASONING=low
ANALYSIS_CLASSIFICATION_REASONING=low
ANALYSIS_GREETING_REASONING=low
ANALYSIS_SYNTHESIS_REASONING=high
STUDENT_REASONING=medium
TUTOR_REASONING=low

# Token budgets
STUDENT_MAX_TOKENS=1500
TUTOR_MAX_TOKENS=1500
ANALYSIS_MISCONCEPTION_MAX_TOKENS=500
ANALYSIS_CLASSIFICATION_MAX_TOKENS=2500
ANALYSIS_CLASSIFICATION_RETRY_MAX_TOKENS=4000
ANALYSIS_GREETING_MAX_TOKENS=1000
ANALYSIS_GREETING_RETRY_MAX_TOKENS=1500
ANALYSIS_SYNTHESIS_MAX_TOKENS=8000
ANALYSIS_SYNTHESIS_RETRY_MAX_TOKENS=12000
DIALOGUE_ANALYSIS_MAX_TOKENS=200
TUTOR_INTERVENTION_THRESHOLD=3
CONTEXT_WINDOW_TURNS=20

# Session Security (CHANGE THIS!)
SESSION_SECRET=your-secure-random-secret-key-here

# Database
DATABASE_URL=sqlite+aiosqlite:///./dialogue_sim.db

# Server
HOST=0.0.0.0
PORT=8000

# Production Settings
TESTING=false
```

**Security Notes**:
- Generate `SESSION_SECRET` with:
  `python -c "import secrets; print(secrets.token_hex(32))"`
- Never commit `.env` to version control
- Restrict file permissions: `chmod 600 .env`

### 4. Initialize Database
```bash
python -m src.db.seed
```

This will:
- Create database schema
- Insert default analysis framework
- Create admin user (student_uid: `admin_001`, nickname: `관리자`)

### 5. Verify Installation
```bash
# Run development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Test health endpoint
curl http://localhost:8000/health
```

## Production Configuration

### 1. Systemd Service

Create `/etc/systemd/system/misconcept.service`:

```ini
[Unit]
Description=Misconception Dialogue Simulator
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/misconcept_platform
Environment="PATH=/opt/misconcept_platform/.venv/bin"
ExecStart=/opt/misconcept_platform/.venv/bin/uvicorn \
    src.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level info \
    --no-access-log \
    --proxy-headers

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Worker Configuration**:
- Calculate workers: `(2 x CPU cores) + 1`
- For 2-core server: `--workers 4`
- For 4-core server: `--workers 8`

Enable and start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable misconcept
sudo systemctl start misconcept
sudo systemctl status misconcept
```

### 2. Nginx Reverse Proxy

Create `/etc/nginx/sites-available/misconcept`:

```nginx
upstream misconcept_backend {
    server 127.0.0.1:8000 fail_timeout=0;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Max upload size
    client_max_body_size 10M;

    # Proxy settings
    location / {
        proxy_pass http://misconcept_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files (if needed)
    location /static {
        alias /opt/misconcept_platform/static;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint (no auth required)
    location /health {
        proxy_pass http://misconcept_backend;
        access_log off;
    }
}
```

Enable site and restart nginx:
```bash
sudo ln -s /etc/nginx/sites-available/misconcept \
    /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 3. SSL Certificate (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
sudo systemctl reload nginx
```

Auto-renewal test:
```bash
sudo certbot renew --dry-run
```

## Database Management

### Backup Strategy

Create backup script `/opt/misconcept_platform/scripts/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/misconcept_platform/backups"
DB_FILE="/opt/misconcept_platform/dialogue_sim.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# SQLite backup with .backup command
sqlite3 $DB_FILE ".backup '$BACKUP_DIR/dialogue_sim_$TIMESTAMP.db'"

# Compress backup
gzip $BACKUP_DIR/dialogue_sim_$TIMESTAMP.db

# Keep only last 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

echo "Backup completed: dialogue_sim_$TIMESTAMP.db.gz"
```

Schedule daily backups with cron:
```bash
sudo chmod +x /opt/misconcept_platform/scripts/backup.sh
sudo crontab -e

# Add this line (daily at 2 AM)
0 2 * * * /opt/misconcept_platform/scripts/backup.sh
```

### Database Restoration
```bash
# Stop application
sudo systemctl stop misconcept

# Restore from backup
gunzip -c backups/dialogue_sim_20250106_020000.db.gz > dialogue_sim.db

# Start application
sudo systemctl start misconcept
```

## Monitoring

### Application Logs

View logs:
```bash
# Systemd logs
sudo journalctl -u misconcept -f

# Last 100 lines
sudo journalctl -u misconcept -n 100

# Filter by error level
sudo journalctl -u misconcept -p err
```

### Health Checks

Set up monitoring service (e.g., UptimeRobot, Pingdom):
- **Endpoint**: `https://your-domain.com/health`
- **Interval**: Every 5 minutes
- **Expected Response**: HTTP 200 + `{"status": "healthy"}`

### Metrics Collection

Access metrics:
```bash
curl https://your-domain.com/metrics
```

Returns:
```json
{
  "total_users": 150,
  "total_sessions": 450,
  "total_messages": 12500,
  "uptime_seconds": 86400,
  "database_size_mb": 12.5
}
```

### Log Rotation

Configure logrotate `/etc/logrotate.d/misconcept`:

```
/var/log/misconcept/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload misconcept > /dev/null 2>&1 || true
    endscript
}
```

## Security Hardening

### 1. Firewall Configuration
```bash
# Allow SSH, HTTP, HTTPS only
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2. Rate Limiting (Application Level)

Already configured in `src/main.py`:
- Login: 5 requests/minute
- Messages: 30 requests/minute
- End session: 10 requests/minute

### 3. Nginx Rate Limiting (Additional Layer)

Add to nginx config:
```nginx
# Define rate limit zone
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# Apply to location
location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    proxy_pass http://misconcept_backend;
}
```

### 4. Database Permissions
```bash
sudo chown www-data:www-data dialogue_sim.db
sudo chmod 640 dialogue_sim.db
```

### 5. Regular Updates
```bash
# System packages
sudo apt update && sudo apt upgrade -y

# Python dependencies
cd /opt/misconcept_platform
source .venv/bin/activate
uv pip install --upgrade -e "."

# Restart service
sudo systemctl restart misconcept
```

## Performance Optimization

### 1. SQLite WAL Mode

Already enabled in `src/db/connection.py`. Verify:
```bash
sqlite3 dialogue_sim.db "PRAGMA journal_mode;"
# Should return: wal
```

### 2. Worker Tuning

Monitor and adjust workers:
```bash
# Check CPU usage
top

# Adjust workers in systemd service
sudo systemctl edit misconcept
```

### 3. Nginx Caching

Add caching for static assets (already in config above).

## Troubleshooting

### Service Won't Start
```bash
# Check logs
sudo journalctl -u misconcept -n 50

# Common issues:
# 1. Port 8000 already in use
sudo lsof -i :8000

# 2. Permission issues
ls -la /opt/misconcept_platform

# 3. Database locked
rm dialogue_sim.db-shm dialogue_sim.db-wal
```

### High Memory Usage
```bash
# Check memory
free -h

# Reduce workers in systemd service
# From --workers 8 to --workers 4
```

### Database Growing Too Large
```bash
# Vacuum database
sqlite3 dialogue_sim.db "VACUUM;"

# Check size
du -h dialogue_sim.db
```

## Deployment Checklist

- [ ] Clone repository to `/opt`
- [ ] Install dependencies with uv
- [ ] Create and configure `.env` file
- [ ] Generate secure `SESSION_SECRET`
- [ ] Initialize database with seed data
- [ ] Create systemd service file
- [ ] Configure nginx reverse proxy
- [ ] Set up SSL with Let's Encrypt
- [ ] Configure firewall rules
- [ ] Set up daily database backups
- [ ] Configure log rotation
- [ ] Set up uptime monitoring
- [ ] Test health and metrics endpoints
- [ ] Create admin user credentials
- [ ] Document admin access instructions
- [ ] Schedule regular update maintenance

## Support

For issues or questions:
- **GitHub Issues**: https://github.com/your-org/misconcept_platform/issues
- **Documentation**: See `docs/` directory
- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics`
