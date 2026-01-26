# Hebbian Mind Enterprise - Deployment Guide

## Quick Start

### 1. Install Package

```bash
pip install -e .
```

### 2. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your paths
nano .env
```

Minimum required configuration:

```bash
HEBBIAN_MIND_BASE_DIR="/opt/hebbian_mind/data"
```

### 3. Create Data Directory

```bash
mkdir -p /opt/hebbian_mind/data/disk
```

### 4. Add Node Definitions

Create `/opt/hebbian_mind/data/disk/nodes_v2.json`:

```json
{
  "nodes": [
    {
      "id": "node_001",
      "name": "Example Concept",
      "category": "general",
      "keywords": ["example", "test"],
      "prototype_phrases": ["example concept"],
      "description": "Example node",
      "weight": 1.0
    }
  ]
}
```

### 5. Test Run

```bash
python -m hebbian_mind.server
```

## MCP Integration

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%/Claude/claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "hebbian-mind": {
      "command": "python",
      "args": ["-m", "hebbian_mind.server"],
      "env": {
        "HEBBIAN_MIND_BASE_DIR": "/opt/hebbian_mind/data"
      }
    }
  }
}
```

### With RAM Disk (High Performance)

```json
{
  "mcpServers": {
    "hebbian-mind": {
      "command": "python",
      "args": ["-m", "hebbian_mind.server"],
      "env": {
        "HEBBIAN_MIND_BASE_DIR": "/opt/hebbian_mind/data",
        "HEBBIAN_MIND_RAM_DISK": "true",
        "HEBBIAN_MIND_RAM_DIR": "/dev/shm/hebbian_mind"
      }
    }
  }
}
```

## RAM Disk Setup

### Linux

```bash
# Using tmpfs (volatile - data lost on reboot)
mkdir -p /dev/shm/hebbian_mind

# Using dedicated mount (persistent across sessions)
sudo mkdir -p /mnt/ramdisk
sudo mount -t tmpfs -o size=1G tmpfs /mnt/ramdisk
mkdir -p /mnt/ramdisk/hebbian_mind
```

### macOS

```bash
# Create 1GB RAM disk
diskutil erasevolume HFS+ "RAMDisk" `hdiutil attach -nomount ram://2097152`
mkdir -p /Volumes/RAMDisk/hebbian_mind
```

### Windows

```powershell
# Using ImDisk Toolkit or similar
# Map R: drive as RAM disk, then:
mkdir R:\HEBBIAN_MIND
```

Set in configuration:

```bash
HEBBIAN_MIND_RAM_DIR="R:/HEBBIAN_MIND"
```

## Production Deployment

### SystemD Service (Linux)

Create `/etc/systemd/system/hebbian-mind.service`:

```ini
[Unit]
Description=Hebbian Mind Enterprise MCP Server
After=network.target

[Service]
Type=simple
User=hebbian
Group=hebbian
WorkingDirectory=/opt/hebbian_mind
Environment="HEBBIAN_MIND_BASE_DIR=/opt/hebbian_mind/data"
Environment="HEBBIAN_MIND_RAM_DISK=true"
Environment="HEBBIAN_MIND_RAM_DIR=/dev/shm/hebbian_mind"
ExecStartPre=/usr/bin/mkdir -p /dev/shm/hebbian_mind
ExecStart=/usr/bin/python3 -m hebbian_mind.server
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable hebbian-mind
sudo systemctl start hebbian-mind
sudo systemctl status hebbian-mind
```

### Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -e .

ENV HEBBIAN_MIND_BASE_DIR=/data

VOLUME ["/data"]

CMD ["python", "-m", "hebbian_mind.server"]
```

Build and run:

```bash
docker build -t hebbian-mind-enterprise .

docker run -d \
  --name hebbian-mind \
  -v /opt/hebbian_mind/data:/data \
  -e HEBBIAN_MIND_BASE_DIR=/data \
  hebbian-mind-enterprise
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  hebbian-mind:
    build: .
    container_name: hebbian-mind
    volumes:
      - ./data:/data
      - /dev/shm:/dev/shm:rw
    environment:
      HEBBIAN_MIND_BASE_DIR: /data
      HEBBIAN_MIND_RAM_DISK: "true"
      HEBBIAN_MIND_RAM_DIR: /dev/shm/hebbian_mind
    restart: unless-stopped
```

Run:

```bash
docker-compose up -d
docker-compose logs -f
```

## Performance Tuning

### SQLite Optimization

The system uses WAL (Write-Ahead Logging) by default. Additional tuning in `config.py`:

```python
# In _init_connections()
self.read_conn.execute("PRAGMA synchronous=NORMAL")
self.read_conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
self.read_conn.execute("PRAGMA temp_store=MEMORY")
```

### Hebbian Parameters

Tune learning rate via environment:

```bash
# Slower, more stable learning
HEBBIAN_MIND_EDGE_FACTOR="0.5"
HEBBIAN_MIND_MAX_WEIGHT="5.0"

# Faster learning
HEBBIAN_MIND_EDGE_FACTOR="2.0"
HEBBIAN_MIND_MAX_WEIGHT="20.0"
```

### Activation Threshold

```bash
# More selective (fewer activations)
HEBBIAN_MIND_THRESHOLD="0.5"

# More permissive (more activations)
HEBBIAN_MIND_THRESHOLD="0.2"
```

## Monitoring

### Health Check

```bash
# Using MCP tools
echo '{"tool": "mind_status", "arguments": {}}' | python -m hebbian_mind.server
```

### Logs

```bash
# SystemD
sudo journalctl -u hebbian-mind -f

# Docker
docker logs -f hebbian-mind

# Docker Compose
docker-compose logs -f hebbian-mind
```

### Metrics

Key metrics from `mind_status`:

- `node_count`: Total concept nodes
- `edge_count`: Total Hebbian connections
- `memory_count`: Total memories stored
- `total_activations`: Total node activation events
- `strongest_edges`: Top connected concepts
- `most_active_nodes`: Most frequently activated concepts

## Backup and Recovery

### Backup Strategy

```bash
# Stop writes (if possible)
systemctl stop hebbian-mind

# Backup disk database
tar -czf hebbian_mind_backup_$(date +%Y%m%d).tar.gz \
  /opt/hebbian_mind/data/disk/

# Restart
systemctl start hebbian-mind
```

### Hot Backup (No Downtime)

```bash
# SQLite backup command
sqlite3 /opt/hebbian_mind/data/disk/hebbian_mind.db \
  ".backup /opt/backups/hebbian_mind_$(date +%Y%m%d).db"
```

### Recovery

```bash
# Stop service
systemctl stop hebbian-mind

# Restore from backup
tar -xzf hebbian_mind_backup_YYYYMMDD.tar.gz -C /

# Or restore database only
cp /opt/backups/hebbian_mind_YYYYMMDD.db \
  /opt/hebbian_mind/data/disk/hebbian_mind.db

# Restart
systemctl start hebbian-mind
```

## Troubleshooting

### RAM Disk Not Available

Check error logs. System falls back to disk automatically.

```bash
# Verify RAM disk exists
ls -la /dev/shm/hebbian_mind

# Check write permissions
touch /dev/shm/hebbian_mind/.test && rm /dev/shm/hebbian_mind/.test
```

### Database Locked

```bash
# Check for stale connections
lsof /opt/hebbian_mind/data/disk/hebbian_mind.db

# Clean WAL files (if service stopped)
rm /opt/hebbian_mind/data/disk/hebbian_mind.db-wal
rm /opt/hebbian_mind/data/disk/hebbian_mind.db-shm
```

### Memory Growth

```bash
# Monitor process
ps aux | grep hebbian_mind

# Restart service periodically (if needed)
sudo systemctl restart hebbian-mind
```

## Security

### File Permissions

```bash
# Create dedicated user
sudo useradd -r -s /bin/false hebbian

# Set ownership
sudo chown -R hebbian:hebbian /opt/hebbian_mind

# Restrict permissions
sudo chmod 750 /opt/hebbian_mind/data
sudo chmod 640 /opt/hebbian_mind/data/disk/*.db
```

### Network Isolation

If using FAISS tether or other network features:

```bash
# Firewall rules (example)
sudo ufw allow from 127.0.0.1 to any port 9998
sudo ufw deny 9998
```

## Support

For enterprise support:

- Email: contact@cipscorps.com
- Documentation: https://docs.cipscorps.com/hebbian-mind
- Issues: Enterprise customers receive dedicated support channel
