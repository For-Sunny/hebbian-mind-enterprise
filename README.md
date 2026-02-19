# Hebbian Mind Enterprise

**Memory that learns. Connections that fade.**

An MCP server that builds knowledge graphs through use. Concepts connect when they activate together. Unused connections decay. The more you use it, the smarter it gets.

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
| `HEBBIAN_MIND_MAX_WEIGHT` | `10.0` | Maximum edge weight cap |

> **Deprecated:** `HEBBIAN_MIND_EDGE_FACTOR` is no longer used. The asymptotic learning formula (LEARNING_RATE = 0.1) replaced the old harmonic strengthening factor. The env var still loads without error but has no effect on edge weights.

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

## Temporal Decay

Memories and edges both decay over time unless reinforced.

**Memory decay:** Same formula as CASCADE and PyTorch Memory. Memories lose effective importance over time. Accessed memories reset their clock. Immortal memories (importance >= 0.9) never decay.

**Edge decay:** Connections between concepts weaken if not co-activated. This is the inverse of Hebbian learning -- "neurons that stop firing together, stop wiring together." Edges decay toward a minimum weight (0.1), never to zero, preserving the structure of learned associations.

### Decay Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HEBBIAN_MIND_DECAY_ENABLED` | `true` | Enable memory decay |
| `HEBBIAN_MIND_DECAY_BASE_RATE` | `0.01` | Base exponential decay rate |
| `HEBBIAN_MIND_DECAY_THRESHOLD` | `0.1` | Memories below this are hidden |
| `HEBBIAN_MIND_DECAY_IMMORTAL_THRESHOLD` | `0.9` | Memories at or above this never decay |
| `HEBBIAN_MIND_DECAY_SWEEP_INTERVAL` | `60` | Minutes between sweep cycles |
| `HEBBIAN_MIND_EDGE_DECAY_ENABLED` | `true` | Enable edge weight decay |
| `HEBBIAN_MIND_EDGE_DECAY_RATE` | `0.005` | Edge decay rate (slower than memory decay) |
| `HEBBIAN_MIND_EDGE_DECAY_MIN_WEIGHT` | `0.1` | Minimum edge weight floor |

Decayed memories are hidden from `query_mind` by default. Pass `include_decayed: true` to retrieve them.

---

## Architecture

### Dual-Write Pattern

- **Write**: Disk first (crash-safe) -> RAM second (speed)
- **Read**: RAM (instant) with disk fallback
- **Startup**: Copies disk to RAM if RAM is empty

Disk commits before RAM updates. If the RAM write fails, the data is already on disk -- the failure gets logged but nothing is lost. This order guarantees durability. A power loss mid-write never leaves you with RAM-only data that never reached disk.

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

1. Edge created if none exists (initial weight: 0.15)
2. Existing edges strengthen via asymptotic formula:

```
delta = (MAX_WEIGHT - current_weight) * LEARNING_RATE
new_weight = current_weight + delta
```

Each co-activation closes 10% of the gap between current weight and MAX_WEIGHT (10.0). An edge at 2.0 gains 0.8. An edge at 9.0 gains 0.1. Edges approach the ceiling but never hit it -- no saturation, no runaway weights.

Combined with time-based decay (idle edges lose 2% per tick) and homeostatic scaling (total edge weight per node stays near 50.0), the graph self-regulates. Active paths strengthen. Neglected paths fade. The topology stays meaningful.

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

| Metric | Value | Notes |
|--------|-------|-------|
| Save latency | <10ms | Includes activation, Hebbian strengthening, and commit |
| Query latency | <5ms | Node lookup + JOIN + sort |
| RAM disk reads | <1ms | When `HEBBIAN_MIND_RAM_DISK=true` |
| Analyze latency | <1ms | Content analysis without save |
| Memory per node | ~1KB | SQLite row with keywords and phrases |
| Memory per edge | ~100 bytes | SQLite row with weight and timestamps |
| Startup (100 nodes) | <1 second | Schema creation + node loading + edge initialization |

### Reproducing Benchmarks

A benchmark script is included to verify these claims on your hardware:

```bash
python benchmarks/benchmark_performance.py
```

The script creates an isolated temp database, runs 200 iterations of each operation, and reports mean/median/P95/P99 latencies. Results are saved to `benchmarks/latest_results.json` with full system info for reproducibility.

**Test conditions:** Disk-only mode (no RAM disk), WAL journal mode, 20 enterprise nodes, single-threaded. RAM disk mode will produce faster read latencies.

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
- **Issues**: [GitHub Issues](https://github.com/For-Sunny/hebbian-mind-enterprise/issues)

---

## License

MIT License. See [LICENSE](./LICENSE) for terms.

---

*Memory that learns. Concepts that connect. The more you use it, the smarter it gets.*

---

**Made by [CIPS Corp](https://cipscorps.io)**

[Website](https://cipscorps.io) | [Store](https://store.cipscorps.io) | [GitHub](https://github.com/For-Sunny) | glass@cipscorps.io

Enterprise cognitive infrastructure for AI systems: [PyTorch Memory, Soul Matrix, CMM, and the full CIPS Stack](https://store.cipscorps.io).

Copyright (c) 2025-2026 C.I.P.S. LLC
