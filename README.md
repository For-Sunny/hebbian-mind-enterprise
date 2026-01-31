# Hebbian Mind Enterprise

**Memory that learns.**

An MCP server that builds knowledge graphs through use. Concepts connect when they activate together. The more you use it, the smarter it gets.

---

## What It Does

- **Associative Memory** - Save content. Query content. Related concepts surface automatically.
- **Hebbian Learning** - Edges strengthen through co-activation. No manual linking required.
- **Concept Nodes** - 100+ pre-defined enterprise concepts across Systems, Security, Data, Operations, and more.
- **MCP Native** - Works with Claude Desktop, Claude Code, any MCP-compatible client.

---

## Installation

Three paths. Pick what fits.

### Windows (Native)

```powershell
# Clone the repo
git clone https://github.com/cipscorps/hebbian-mind-enterprise.git
cd hebbian-mind-enterprise

# Install with pip
pip install -e .

# Verify
python -m hebbian_mind.server
```

The server runs on stdio. Press Ctrl+C to stop.

### Linux / macOS (Native)

```bash
# Clone the repo
git clone https://github.com/cipscorps/hebbian-mind-enterprise.git
cd hebbian-mind-enterprise

# Install with pip (use a virtual environment if you prefer)
pip install -e .

# Verify
python -m hebbian_mind.server
```

Linux gets automatic RAM disk support via `/dev/shm` when enabled.

### Docker (Teams / Enterprise)

```bash
# Clone the repo
git clone https://github.com/cipscorps/hebbian-mind-enterprise.git
cd hebbian-mind-enterprise

# Copy environment template
cp .env.example .env

# Build and start
docker-compose up -d

# View logs
docker-compose logs -f hebbian-mind
```

For RAM disk optimization:

```bash
docker-compose --profile ramdisk up -d
```

---

## Claude Desktop Integration

Add to your `claude_desktop_config.json`:

**Native Install:**

```json
{
  "mcpServers": {
    "hebbian-mind": {
      "command": "python",
      "args": ["-m", "hebbian_mind.server"]
    }
  }
}
```

**Docker Install:**

```json
{
  "mcpServers": {
    "hebbian-mind": {
      "command": "docker",
      "args": ["exec", "-i", "hebbian-mind", "python", "-m", "hebbian_mind.server"]
    }
  }
}
```

Restart Claude Desktop. The tools appear automatically.

---

## Configuration

Environment variables control behavior. Set them before running, or use `.env` with Docker.

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `HEBBIAN_MIND_BASE_DIR` | `./hebbian_mind_data` | Data storage location |
| `HEBBIAN_MIND_RAM_DISK` | `false` | Enable RAM disk for faster reads |
| `HEBBIAN_MIND_RAM_DIR` | `/dev/shm/hebbian_mind` (Linux) | RAM disk path |

### Hebbian Learning

| Variable | Default | Description |
|----------|---------|-------------|
| `HEBBIAN_MIND_THRESHOLD` | `0.3` | Activation threshold (0.0-1.0) |
| `HEBBIAN_MIND_EDGE_FACTOR` | `1.0` | Edge strengthening rate |
| `HEBBIAN_MIND_MAX_WEIGHT` | `10.0` | Maximum edge weight cap |

### Optional Integrations

| Variable | Default | Description |
|----------|---------|-------------|
| `HEBBIAN_MIND_FAISS_ENABLED` | `false` | Enable FAISS semantic search |
| `HEBBIAN_MIND_FAISS_HOST` | `localhost` | FAISS tether host |
| `HEBBIAN_MIND_FAISS_PORT` | `9998` | FAISS tether port |
| `HEBBIAN_MIND_PRECOG_ENABLED` | `false` | Enable PRECOG concept extraction |

---

## MCP Tools

Eight tools. All available through any MCP client.

### save_to_mind

Store content with automatic concept activation and edge strengthening.

```json
{
  "content": "Microservices architecture enables independent deployment",
  "summary": "Optional summary",
  "source": "ARCHITECTURE_DOCS",
  "importance": 0.8
}
```

Activates matching concept nodes. Strengthens edges between co-activated concepts.

### query_mind

Query memories by concept nodes.

```json
{
  "nodes": ["architecture", "deployment"],
  "limit": 20
}
```

Returns memories that activated those concepts.

### analyze_content

Preview which concepts would activate without saving.

```json
{
  "content": "API authentication using JWT tokens",
  "threshold": 0.3
}
```

### get_related_nodes

Get concepts connected via Hebbian edges.

```json
{
  "node": "security",
  "min_weight": 0.1
}
```

Returns the neighborhood graph - concepts that have fired together with "security".

### list_nodes

List all concept nodes, optionally filtered.

```json
{
  "category": "Security"
}
```

### mind_status

Server health and statistics.

```json
{}
```

Returns node count, edge count, memory count, strongest connections, dual-write status.

### faiss_search

Semantic search via external FAISS tether (if enabled).

```json
{
  "query": "authentication patterns",
  "top_k": 10
}
```

### faiss_status

Check FAISS tether connection status.

---

## Architecture

### Dual-Write Pattern

- **Write**: RAM first (speed) -> Disk second (persistence)
- **Read**: RAM (instant) with disk fallback
- **Startup**: Copies disk to RAM if RAM is empty

RAM disk is optional. Without it, reads and writes go directly to SQLite on disk.

### Concept Nodes

100+ pre-defined nodes across categories:

- **Systems & Architecture** - service, api, component, integration
- **Security** - authentication, authorization, encryption, access
- **Data & Memory** - database, cache, persistence, schema
- **Logic & Reasoning** - pattern, rule, validation, analysis
- **Operations** - workflow, pipeline, monitoring, health
- **Quality** - performance, reliability, scalability, test

Nodes have keywords and prototype phrases. Content activates nodes when keywords match.

### Hebbian Learning

When concepts co-activate (appear in the same saved content):

1. Edge created if none exists (weight: 0.15)
2. Edge strengthened if exists: `weight += factor / (1 + current_weight)`
3. Weight capped at `MAX_EDGE_WEIGHT`

"Neurons that fire together, wire together."

---

## Troubleshooting

### Server won't start

Check Python version (requires 3.10+):

```bash
python --version
```

Verify MCP SDK installed:

```bash
pip install mcp
```

### No activations on save

Content must match node keywords above threshold. Lower the threshold:

```bash
export HEBBIAN_MIND_THRESHOLD=0.2
```

Or check what would activate:

```json
{"tool": "analyze_content", "content": "your text here"}
```

### Docker container won't connect

Ensure container is running:

```bash
docker ps | grep hebbian-mind
```

Check logs:

```bash
docker-compose logs hebbian-mind
```

### High memory with RAM disk

Check node/edge counts via `mind_status`. Consider increasing `HEBBIAN_MIND_THRESHOLD` to activate fewer nodes, or lower `HEBBIAN_MIND_MAX_WEIGHT` to limit edge growth.

---

## Performance

| Metric | Value |
|--------|-------|
| Save latency | <10ms |
| Query latency | <5ms |
| RAM disk reads | <1ms |
| Memory per node | ~1KB |
| Memory per edge | ~100 bytes |
| Startup (100 nodes) | <1 second |

---

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=hebbian_mind
```

---

## Support

- **Documentation**: [cipscorps.io/docs/hebbian-mind](https://cipscorps.io/docs/hebbian-mind)
- **Email**: support@cipscorps.io
- **Issues**: Private repo issue tracker

Enterprise support plans available.

---

## License

Proprietary software. See [LICENSE](./LICENSE) for terms.

- **Individual**: Single developer, unlimited projects
- **Team**: Up to 10 developers, single organization
- **Enterprise**: Unlimited developers, single organization

Redistribution prohibited.

---

*Memory that learns. Concepts that connect. The more you use it, the smarter it gets.*
