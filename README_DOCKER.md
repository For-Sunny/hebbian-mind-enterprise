# Hebbian Mind Enterprise - Docker Deployment

Docker deployment guide for Hebbian Mind Enterprise neural graph memory system.

## Quick Start

### 1. Build the Image

```bash
docker-compose build
```

### 2. Start the Container

```bash
# Standard deployment (disk-based)
docker-compose up -d

# RAM disk deployment (ultra-low latency)
docker-compose --profile ramdisk up -d
```

### 3. View Logs

```bash
docker-compose logs -f hebbian-mind
```

### 4. Stop the Container

```bash
docker-compose down
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key settings:

- `HEBBIAN_MIND_RAM_DISK`: Enable RAM disk mode (true/false)
- `HEBBIAN_MIND_THRESHOLD`: Node activation threshold (0.0-1.0)
- `HEBBIAN_MIND_EDGE_FACTOR`: Hebbian edge strengthening rate
- `HEBBIAN_MIND_FAISS_ENABLED`: Enable FAISS semantic search integration
- `HEBBIAN_MIND_PRECOG_ENABLED`: Enable PRECOG concept extraction

See `.env.example` for full configuration options.

## Deployment Modes

### Standard Mode (Disk-Based)

Default configuration. Database stored on persistent volume.

```bash
docker-compose up -d
```

**Performance:**
- Node activation: ~5-10ms
- Memory save: ~10-20ms
- Suitable for: Most deployments

### RAM Disk Mode (Ultra-Low Latency)

Database mirrored to tmpfs RAM disk for sub-millisecond reads.

```bash
docker-compose --profile ramdisk up -d
```

**Performance:**
- Node activation: ~2-5ms
- Memory save: ~5-10ms
- RAM reads: <1ms

**Requirements:**
- Set `RAMDISK_SIZE` appropriately (default: 512MB)
- Ensure sufficient container memory allocation
- Data synced to disk automatically (dual-write)

## Data Persistence

### Volume Mounts

Data stored in named volume `hebbian_data`:

```yaml
volumes:
  - hebbian_data:/data/hebbian_mind
```

Default host path: `./data/hebbian_mind`

Change via environment variable:

```bash
HEBBIAN_DATA_PATH=/your/custom/path
```

### Custom Node Definitions

Mount your own `nodes_v2.json`:

```yaml
volumes:
  - ./data/nodes_v2.json:/data/hebbian_mind/nodes/nodes_v2.json:ro
```

### Backup Strategy

Backup the entire data directory:

```bash
# Backup
docker-compose exec hebbian-mind tar czf /tmp/backup.tar.gz /data/hebbian_mind
docker cp hebbian-mind:/tmp/backup.tar.gz ./hebbian-backup-$(date +%Y%m%d).tar.gz

# Restore
docker cp ./hebbian-backup-20260126.tar.gz hebbian-mind:/tmp/restore.tar.gz
docker-compose exec hebbian-mind tar xzf /tmp/restore.tar.gz -C /
```

## Integration

### MCP Client Configuration

Add to your MCP client config (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "hebbian-mind": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "hebbian-mind",
        "python",
        "-m",
        "hebbian_mind.server"
      ]
    }
  }
}
```

### FAISS Tether Integration

Enable semantic search via external FAISS server:

1. Set environment variables:
```bash
HEBBIAN_MIND_FAISS_ENABLED=true
HEBBIAN_MIND_FAISS_HOST=faiss-tether
HEBBIAN_MIND_FAISS_PORT=9998
```

2. Uncomment FAISS service in `docker-compose.yml`

3. Restart:
```bash
docker-compose down
docker-compose up -d
```

### PRECOG Concept Extraction

Enable advanced concept extraction:

1. Mount PRECOG daemon:
```yaml
volumes:
  - ./precog:/app/precog:ro
```

2. Set environment:
```bash
HEBBIAN_MIND_PRECOG_ENABLED=true
HEBBIAN_MIND_PRECOG_PATH=/app/precog
```

## Monitoring

### Health Check

Docker health check runs every 30 seconds:

```bash
docker inspect --format='{{.State.Health.Status}}' hebbian-mind
```

Status: `healthy` | `unhealthy` | `starting`

### Logs

View real-time logs:

```bash
docker-compose logs -f hebbian-mind
```

Adjust log level via environment:

```bash
HEBBIAN_MIND_LOG_LEVEL=DEBUG
```

### Statistics

Check container stats:

```bash
docker stats hebbian-mind
```

## Troubleshooting

### Container Won't Start

Check logs:
```bash
docker-compose logs hebbian-mind
```

Common issues:
- Volume permissions (ensure writable by UID 1000)
- Insufficient memory (increase Docker memory limit)
- Port conflicts (check for conflicting containers)

### Database Corruption

Restore from backup or rebuild:

```bash
docker-compose down
rm -rf ./data/hebbian_mind/disk/*.db*
docker-compose up -d
```

Database will reinitialize from `nodes_v2.json`.

### RAM Disk Issues

If RAM disk fails to mount:

1. Check `RAMDISK_SIZE` vs available memory
2. Verify tmpfs support: `docker info | grep "Supports"`
3. Fall back to standard mode

### Performance Issues

Optimize with:

1. Enable RAM disk mode
2. Increase `RAMDISK_SIZE`
3. Allocate more container memory
4. Use SSD for persistent volume

## Security

### Best Practices

1. **Run as non-root**: Container uses UID 1000 (hebbian user)
2. **Network isolation**: Use Docker networks, no exposed ports by default
3. **Volume permissions**: Restrict host volume access
4. **Secrets management**: Use Docker secrets for license keys

### Production Deployment

```bash
# Set resource limits
docker-compose up -d \
  --memory="2g" \
  --cpus="2.0"

# Enable read-only filesystem (with writable volumes)
docker run --read-only \
  -v hebbian_data:/data/hebbian_mind \
  cipscorp/hebbian-mind-enterprise
```

## Performance Benchmarks

### Standard Mode (Disk)
- Node activation: 5-10ms
- Memory save: 10-20ms
- Query by nodes: 20-50ms

### RAM Disk Mode (tmpfs)
- Node activation: 2-5ms
- Memory save: 5-10ms
- Query by nodes: 5-15ms
- RAM reads: <1ms

### With FAISS Tether
- Semantic search: 10-30ms (GPU-accelerated)
- Hybrid query: 15-40ms

## Support

- **Documentation**: https://docs.cipscorps.com/hebbian-mind
- **Email**: glass@cipscorps.io
- **License**: See LICENSE file

---

*CIPS LLC - Neural Graph Memory Systems*
