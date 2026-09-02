# CloudStack Template Automation - Production Deployment Guide

This guide provides end-to-end instructions for deploying the CloudStack Template Automation Engine in production environments.

---

## 1. System Requirements & Architecture

- **Host Operating System**: Rocky Linux 8/9, AlmaLinux 8/9, Ubuntu 22.04/24.04 LTS, Debian 12, or RHEL 8/9
- **Python**: 3.9 or higher
- **Database**: PostgreSQL 13+ (or SQLite for single-node development)
- **Network Access**: Outbound SSH (port 22) from the automation engine host to all target CloudStack VMs
- **Optional**: OpenAI API Key / Anthropic API Key for AI error diagnostics

---

## 2. Option A: Bare Metal / Linux VM Deployment (Systemd + PostgreSQL)

### Step 1: Install System Dependencies
```bash
# On RHEL / Rocky / AlmaLinux:
sudo dnf install -y python3 python3-pip python3-devel postgresql-server postgresql-contrib git

# On Ubuntu / Debian:
sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv python3-dev postgresql libpq-dev git
```

### Step 2: Configure PostgreSQL Database
```bash
sudo -u postgres psql -c "CREATE USER cloudstack WITH PASSWORD 'SecureDbPassword123!';"
sudo -u postgres psql -c "CREATE DATABASE cloudstack_automation OWNER cloudstack;"
```

### Step 3: Deploy Application Code
```bash
sudo mkdir -p /opt/cloudstack-automation
sudo useradd -r -s /bin/false cloudstack
sudo chown cloudstack:cloudstack /opt/cloudstack-automation

cd /opt/cloudstack-automation
sudo -u cloudstack git clone https://github.com/your-org/cloudstack-automation.git .
sudo -u cloudstack python3 -m venv venv
sudo -u cloudstack /opt/cloudstack-automation/venv/bin/pip install --upgrade pip
sudo -u cloudstack /opt/cloudstack-automation/venv/bin/pip install -r requirements.txt
```

### Step 4: Configure Production Environment (`.env`)
```bash
sudo cp .env.example .env
sudo nano .env
```
Set the following production values:
```ini
API_HOST=0.0.0.0
API_PORT=8000
API_LOG_LEVEL=INFO
DATABASE_URL=postgresql://cloudstack:SecureDbPassword123!@localhost:5432/cloudstack_automation
SECRET_KEY=ChangeThisToAStrongRandomSecretKey
ALLOWED_ORIGINS=https://templates.yourdomain.com
OPENAI_API_KEY=sk-...
```

### Step 5: Initialize Database Schema
```bash
sudo -u cloudstack /opt/cloudstack-automation/venv/bin/python init_db.py
```

### Step 6: Configure Systemd Service
```bash
sudo cp cloudstack-automation.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cloudstack-automation
sudo systemctl status cloudstack-automation
```

---

## 3. Option B: Docker Compose Multi-Container Deployment

```bash
# 1. Clone repository
git clone https://github.com/your-org/cloudstack-automation.git
cd cloudstack-automation

# 2. Configure .env
cp .env.example .env

# 3. Launch stack
docker-compose up -d --build

# 4. Check container health
docker-compose ps
```

---

## 4. Option C: Kubernetes Manifests

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cloudstack-automation
  namespace: cloudstack
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cloudstack-automation
  template:
    metadata:
      labels:
        app: cloudstack-automation
    spec:
      containers:
      - name: backend
        image: your-registry/cloudstack-automation-backend:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: cloudstack-automation-secrets
        resources:
          requests:
            cpu: 250m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 15
---
apiVersion: v1
kind: Service
metadata:
  name: cloudstack-automation-svc
  namespace: cloudstack
spec:
  type: ClusterIP
  selector:
    app: cloudstack-automation
  ports:
  - port: 8000
    targetPort: 8000
```

---

## 5. Security & Hardening Best Practices

1. **Credential Hygiene**: Target VM SSH credentials are processed only in-memory and discarded upon execution completion.
2. **Network Isolation**: Restrict backend inbound ports (8000) using firewall rules or reverse proxy authentication (Cloudflare / Nginx / Traefik).
3. **Database SSL**: Ensure SSL connection encryption (`sslmode=require`) when connecting to managed PostgreSQL instances.
4. **Rate Limiting**: Implement rate limiting on `/api/template/create` to prevent denial-of-service or connection flooding.
