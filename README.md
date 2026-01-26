# Hebbian Mind Enterprise

**"Neurons that fire together, wire together"**

Enterprise-grade Hebbian learning neural graph memory system for AI applications. Built on proven neuroscience principles, Hebbian Mind Enterprise provides self-organizing associative memory that strengthens through use, enabling AI systems to develop natural concept relationships and semantic understanding.

---

## Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Quick Start](#quick-start)
6. [Configuration](#configuration)
7. [API Reference](#api-reference)
8. [Performance Characteristics](#performance-characteristics)
9. [Integration Patterns](#integration-patterns)
10. [Deployment](#deployment)
11. [Support](#support)
12. [License](#license)

---

## Overview

Hebbian Mind Enterprise implements biological Hebbian learning principles in a high-performance neural graph database. Unlike traditional static knowledge graphs or vector databases, Hebbian Mind learns and adapts through use - edges between concepts strengthen when activated together, creating organic semantic networks that mirror natural cognitive patterns.

### What It Does

- **Associative Memory**: Stores content with automatic concept node activation
- **Hebbian Learning**: Edge weights strengthen through co-activation (Donald Hebb's principle)
- **Semantic Relationships**: Discovers and reinforces conceptual connections organically
- **Sub-millisecond Inference**: High-performance graph traversal with RAM disk optimization
- **MCP Integration**: Native Model Context Protocol server for AI agent systems

### Use Cases

- AI agent memory systems with natural concept drift
- Semantic knowledge graphs that learn from usage patterns
- Associative recall systems for language models
- Concept relationship discovery in large corpora
- Real-time cognitive architectures for autonomous systems

---

## Key Features

### Hebbian Learning

```
When concept A and concept B activate together repeatedly,
the edge between them strengthens automatically.

Activation count: 1  → Edge weight: 1.0
Activation count: 5  → Edge weight: 3.2
Activation count: 10 → Edge weight: 5.8
```

- **Automatic edge strengthening** through co-activation
- **Configurable learning rates** and maximum weights
- **Temporal decay** options for time-sensitive applications
- **Bidirectional reinforcement** for symmetric relationships

### Dual-Write Architecture

High-performance RAM disk layer with persistent disk backup:

```
WRITE PATH:
  Content → RAM Disk (instant write) → Disk Storage (persistence)

READ PATH:
  RAM Disk (sub-ms lookup) → Disk Fallback (if RAM unavailable)
```

- **RAM disk**: R:\ or configurable path for instant access
- **Disk storage**: Source of truth, automatic sync
- **Automatic failover**: Seamless degradation to disk-only mode
- **Startup sync**: Disk-to-RAM copy on initialization

### MCP Server Interface

Native Model Context Protocol implementation:

- **8 MCP tools** for graph operations
- **Standard MCP transport** (stdio/HTTP)
- **Tool discovery** via MCP protocol
- **Type-safe parameters** with JSON Schema validation

### Concept Node System

118+ pre-configured concept nodes across categories:

- **Identity**: Self, consciousness, purpose
- **Technical**: Code, systems, architecture
- **Temporal**: Time, history, evolution
- **Relational**: Partnership, collaboration, trust
- **Cognitive**: Learning, understanding, reasoning
- **Operational**: Action, execution, results

Each node includes:
- Multiple prototype phrases for pattern matching
- Category classification
- Activation history tracking
- Edge relationship metadata

### Performance Optimizations

- **Sub-millisecond RAM disk access** (<1ms typical)
- **Efficient graph traversal** via SQLite with indexes
- **Batch operations** for bulk imports
- **Connection pooling** for concurrent access
- **Lazy loading** of node relationships

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    AI AGENT / LLM                        │
│                                                          │
│  "Save this memory about the project discussion"        │
└────────────────────┬─────────────────────────────────────┘
                     │
                     │ MCP Protocol (stdio/HTTP)
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              HEBBIAN MIND MCP SERVER                     │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  Concept Extraction Layer                      │    │
│  │  - Pattern matching against 118+ nodes         │    │
│  │  - Multi-phrase recognition                    │    │
│  │  - Confidence scoring                          │    │
│  └────────────────────────────────────────────────┘    │
│                     │                                    │
│                     ▼                                    │
│  ┌────────────────────────────────────────────────┐    │
│  │  Hebbian Learning Engine                       │    │
│  │  - Edge detection (co-activated nodes)         │    │
│  │  - Weight strengthening: w = w + factor        │    │
│  │  - Bidirectional updates                       │    │
│  └────────────────────────────────────────────────┘    │
│                     │                                    │
│                     ▼                                    │
│  ┌──────────────────────────────────────────────────┐  │
│  │        Dual-Write Persistence Layer              │  │
│  │                                                  │  │
│  │   RAM DISK (R:\)        DISK STORAGE             │  │
│  │   ┌─────────────┐       ┌──────────────┐        │  │
│  │   │hebbian_mind │◄─────►│hebbian_mind  │        │  │
│  │   │    .db      │       │    .db       │        │  │
│  │   │ <1ms read   │       │(source truth)│        │  │
│  │   └─────────────┘       └──────────────┘        │  │
│  │                                                  │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

**Save Operation:**

1. Agent sends content via `save_to_mind` tool
2. Concept extraction layer analyzes content
3. Matching nodes activate (threshold-based)
4. Hebbian engine detects co-activations
5. Edge weights update: `new_weight = min(old_weight + factor, max_weight)`
6. Content written to RAM disk SQLite
7. Synchronous write to disk storage
8. Return activated nodes and strengthened edges

**Query Operation:**

1. Agent requests memories by concept via `query_mind` tool
2. Node lookup in RAM disk graph
3. Edge traversal following weighted connections
4. Related content retrieval via SQLite JOIN
5. Results ranked by edge weight and relevance
6. Return memories with relationship metadata

### Database Schema

**Nodes Table:**
```sql
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    prototype_phrases TEXT,  -- JSON array
    activation_count INTEGER DEFAULT 0,
    last_activated TIMESTAMP
);
```

**Edges Table:**
```sql
CREATE TABLE edges (
    id INTEGER PRIMARY KEY,
    source_node_id INTEGER NOT NULL,
    target_node_id INTEGER NOT NULL,
    weight REAL DEFAULT 1.0,
    activation_count INTEGER DEFAULT 0,
    last_activated TIMESTAMP,
    FOREIGN KEY (source_node_id) REFERENCES nodes(id),
    FOREIGN KEY (target_node_id) REFERENCES nodes(id),
    UNIQUE(source_node_id, target_node_id)
);
```

**Memories Table:**
```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,  -- JSON
    activated_nodes TEXT  -- JSON array of node IDs
);
```

**Memory-Node Junction:**
```sql
CREATE TABLE memory_nodes (
    memory_id INTEGER NOT NULL,
    node_id INTEGER NOT NULL,
    activation_strength REAL DEFAULT 1.0,
    FOREIGN KEY (memory_id) REFERENCES memories(id),
    FOREIGN KEY (node_id) REFERENCES nodes(id),
    PRIMARY KEY (memory_id, node_id)
);
```

---

## Installation

### Requirements

- Python 3.10 or higher
- MCP SDK 1.0.0+
- Operating System: Windows, Linux, or macOS
- Optional: RAM disk software (ImDisk, imdisk-toolkit, etc.)

### Install from PyPI

```bash
pip install hebbian-mind-enterprise
```

### Install from Source

```bash
git clone https://github.com/cipscorps/hebbian-mind-enterprise.git
cd hebbian-mind-enterprise
pip install -e .
```

### Development Installation

```bash
pip install -e ".[dev]"
```

This includes pytest, black, and ruff for development.

---

## Quick Start

### 1. Basic MCP Server Setup

Create a configuration file `hebbian_mind_config.json`:

```json
{
  "mcpServers": {
    "hebbian-mind": {
      "command": "python",
      "args": ["-m", "hebbian_mind"],
      "env": {
        "HEBBIAN_MIND_BASE_DIR": "./data/hebbian_mind",
        "HEBBIAN_MIND_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### 2. Start the Server

**Via MCP client (Claude Desktop, etc.):**

Add the above config to your MCP settings file.

**Via command line:**

```bash
python -m hebbian_mind
```

### 3. Use via MCP Protocol

**Save a memory:**

```json
{
  "tool": "save_to_mind",
  "arguments": {
    "content": "Discussed system architecture with the team. Focus on scalability and performance.",
    "source": "meeting_notes",
    "metadata": {
      "date": "2026-01-26",
      "participants": ["team_lead", "architect", "engineer"]
    }
  }
}
```

**Response:**

```json
{
  "memory_id": 42,
  "activated_nodes": [
    {"name": "architecture", "category": "technical", "strength": 0.85},
    {"name": "performance", "category": "technical", "strength": 0.72},
    {"name": "collaboration", "category": "relational", "strength": 0.65}
  ],
  "strengthened_edges": [
    {"from": "architecture", "to": "performance", "new_weight": 3.2, "activations": 5},
    {"from": "architecture", "to": "collaboration", "new_weight": 2.1, "activations": 3}
  ],
  "timestamp": "2026-01-26T10:30:45Z"
}
```

**Query memories:**

```json
{
  "tool": "query_mind",
  "arguments": {
    "concept": "architecture",
    "limit": 10,
    "min_edge_weight": 2.0
  }
}
```

**Response:**

```json
{
  "memories": [
    {
      "id": 42,
      "content": "Discussed system architecture with the team...",
      "timestamp": "2026-01-26T10:30:45Z",
      "activated_nodes": ["architecture", "performance", "collaboration"],
      "relevance_score": 0.92
    }
  ],
  "related_concepts": [
    {"name": "performance", "edge_weight": 3.2},
    {"name": "scalability", "edge_weight": 2.8},
    {"name": "design", "edge_weight": 2.5}
  ]
}
```

### 4. Python SDK Usage

```python
from hebbian_mind import HebbianMindClient

# Initialize client
client = HebbianMindClient(
    base_dir="./data/hebbian_mind",
    ram_disk_enabled=True,
    ram_disk_path="R:/HEBBIAN_MIND"
)

# Save a memory
result = client.save(
    content="Implemented new caching layer for API endpoints",
    source="development_log",
    metadata={"project": "api_v2", "sprint": 5}
)

print(f"Saved memory {result['memory_id']}")
print(f"Activated nodes: {[n['name'] for n in result['activated_nodes']]}")

# Query by concept
memories = client.query(
    concept="performance",
    limit=5,
    min_edge_weight=2.0
)

for memory in memories:
    print(f"[{memory['timestamp']}] {memory['content']}")
    print(f"  Related: {memory['related_concepts']}")

# Get concept relationships
related = client.get_related_nodes("architecture", min_weight=2.0)
print(f"Concepts related to 'architecture': {related}")

# System status
status = client.get_status()
print(f"Total memories: {status['memory_count']}")
print(f"Active edges: {status['edge_count']}")
print(f"RAM disk: {'ACTIVE' if status['ram_available'] else 'DISK ONLY'}")
```

---

## Configuration

All configuration is managed via environment variables for containerized deployments and cloud environments.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HEBBIAN_MIND_BASE_DIR` | `./hebbian_mind_data` | Base directory for data storage |
| `HEBBIAN_MIND_RAM_DISK` | `false` | Enable RAM disk layer (`true`/`false`) |
| `HEBBIAN_MIND_RAM_DIR` | `R:/HEBBIAN_MIND` | RAM disk mount point |
| `HEBBIAN_MIND_THRESHOLD` | `0.3` | Concept activation threshold (0.0-1.0) |
| `HEBBIAN_MIND_EDGE_FACTOR` | `1.0` | Edge strengthening increment |
| `HEBBIAN_MIND_MAX_WEIGHT` | `10.0` | Maximum edge weight cap |
| `HEBBIAN_MIND_LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `HEBBIAN_MIND_FAISS_ENABLED` | `false` | Enable FAISS vector search integration |
| `HEBBIAN_MIND_FAISS_HOST` | `localhost` | FAISS server hostname |
| `HEBBIAN_MIND_FAISS_PORT` | `9998` | FAISS server port |
| `HEBBIAN_MIND_PRECOG_ENABLED` | `false` | Enable PRECOG concept extraction |
| `HEBBIAN_MIND_PRECOG_PATH` | (none) | Path to PRECOG daemon |

### Example Configurations

**Development (Disk-only):**

```bash
export HEBBIAN_MIND_BASE_DIR="./dev_data"
export HEBBIAN_MIND_LOG_LEVEL="DEBUG"
python -m hebbian_mind
```

**Production (RAM Disk Enabled):**

```bash
export HEBBIAN_MIND_BASE_DIR="/var/lib/hebbian_mind"
export HEBBIAN_MIND_RAM_DISK="true"
export HEBBIAN_MIND_RAM_DIR="/mnt/ramdisk/hebbian"
export HEBBIAN_MIND_LOG_LEVEL="WARNING"
python -m hebbian_mind
```

**With FAISS Integration:**

```bash
export HEBBIAN_MIND_FAISS_ENABLED="true"
export HEBBIAN_MIND_FAISS_HOST="faiss-server.internal"
export HEBBIAN_MIND_FAISS_PORT="9999"
python -m hebbian_mind
```

### Docker Deployment

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install Hebbian Mind
RUN pip install hebbian-mind-enterprise

# Create data directories
RUN mkdir -p /data/hebbian_mind /ramdisk

# Mount RAM disk (requires --privileged or specific mount capabilities)
VOLUME ["/data/hebbian_mind"]

# Environment configuration
ENV HEBBIAN_MIND_BASE_DIR=/data/hebbian_mind
ENV HEBBIAN_MIND_RAM_DISK=true
ENV HEBBIAN_MIND_RAM_DIR=/ramdisk
ENV HEBBIAN_MIND_LOG_LEVEL=INFO

# Run MCP server
CMD ["python", "-m", "hebbian_mind"]
```

**Run container:**

```bash
docker build -t hebbian-mind-enterprise .

docker run -d \
  --name hebbian-mind \
  -v /var/lib/hebbian_data:/data/hebbian_mind \
  --tmpfs /ramdisk:rw,size=512m \
  -e HEBBIAN_MIND_THRESHOLD=0.35 \
  hebbian-mind-enterprise
```

---

## API Reference

### MCP Tools

#### `save_to_mind`

Save content with automatic Hebbian learning.

**Parameters:**

```typescript
{
  content: string;           // Content to save
  source?: string;           // Source identifier (e.g., "user_input", "agent_log")
  metadata?: object;         // Arbitrary JSON metadata
  importance?: number;       // Importance score (0.0-1.0)
}
```

**Returns:**

```typescript
{
  memory_id: number;
  activated_nodes: Array<{
    name: string;
    category: string;
    strength: number;
  }>;
  strengthened_edges: Array<{
    from: string;
    to: string;
    new_weight: number;
    activation_count: number;
  }>;
  timestamp: string;
}
```

---

#### `query_mind`

Query memories by concept node.

**Parameters:**

```typescript
{
  concept: string;           // Node name to query
  limit?: number;            // Max results (default: 10)
  min_edge_weight?: number;  // Minimum edge weight filter (default: 1.0)
  include_related?: boolean; // Include related concepts (default: true)
}
```

**Returns:**

```typescript
{
  memories: Array<{
    id: number;
    content: string;
    timestamp: string;
    activated_nodes: string[];
    relevance_score: number;
    metadata?: object;
  }>;
  related_concepts: Array<{
    name: string;
    edge_weight: number;
    category: string;
  }>;
}
```

---

#### `analyze_content`

Analyze content without saving (preview mode).

**Parameters:**

```typescript
{
  content: string;           // Content to analyze
  threshold?: number;        // Activation threshold override (0.0-1.0)
}
```

**Returns:**

```typescript
{
  activated_nodes: Array<{
    name: string;
    category: string;
    strength: number;
    matched_phrases: string[];
  }>;
  potential_edges: Array<{
    from: string;
    to: string;
    current_weight: number;
  }>;
}
```

---

#### `get_related_nodes`

Get nodes connected by Hebbian edges.

**Parameters:**

```typescript
{
  concept: string;           // Source node name
  min_weight?: number;       // Minimum edge weight (default: 1.0)
  max_depth?: number;        // Graph traversal depth (default: 1)
  limit?: number;            // Max results (default: 20)
}
```

**Returns:**

```typescript
{
  source_node: string;
  related_nodes: Array<{
    name: string;
    category: string;
    edge_weight: number;
    activation_count: number;
    path_length: number;      // Hops from source
  }>;
}
```

---

#### `list_nodes`

List all concept nodes.

**Parameters:**

```typescript
{
  category?: string;         // Filter by category (optional)
  min_activations?: number;  // Minimum activation count (optional)
  sort_by?: "name" | "activations" | "category";  // Sort order
}
```

**Returns:**

```typescript
{
  nodes: Array<{
    id: number;
    name: string;
    category: string;
    prototype_phrases: string[];
    activation_count: number;
    last_activated: string | null;
  }>;
  categories: string[];      // Available categories
}
```

---

#### `get_status`

Get system health and statistics.

**Parameters:** None

**Returns:**

```typescript
{
  status: "healthy" | "degraded" | "error";
  memory_count: number;
  node_count: number;
  edge_count: number;
  avg_edge_weight: number;
  ram_available: boolean;
  ram_path: string | null;
  disk_path: string;
  database_size_mb: number;
  uptime_seconds: number;
  faiss_enabled: boolean;
  faiss_connected: boolean | null;
}
```

---

#### `faiss_search` (Optional)

Semantic vector search via FAISS integration.

**Requires:** `HEBBIAN_MIND_FAISS_ENABLED=true`

**Parameters:**

```typescript
{
  query: string;             // Search query text
  limit?: number;            // Max results (default: 10)
  threshold?: number;        // Similarity threshold (default: 0.7)
}
```

**Returns:**

```typescript
{
  results: Array<{
    memory_id: number;
    content: string;
    similarity: number;
    activated_nodes: string[];
  }>;
  faiss_latency_ms: number;
}
```

---

#### `bulk_import`

Import multiple memories in batch.

**Parameters:**

```typescript
{
  memories: Array<{
    content: string;
    source?: string;
    metadata?: object;
    timestamp?: string;       // ISO 8601 format (optional)
  }>;
  learn_edges?: boolean;     // Apply Hebbian learning (default: true)
}
```

**Returns:**

```typescript
{
  imported_count: number;
  failed_count: number;
  new_edges: number;
  total_edge_updates: number;
  errors: Array<{
    index: number;
    error: string;
  }>;
}
```

---

## Performance Characteristics

### Benchmarks

Tested on commodity hardware (Intel i7-9700K, 32GB RAM, NVMe SSD):

| Operation | RAM Disk | Disk Only | Notes |
|-----------|----------|-----------|-------|
| Save memory | 0.8ms | 12ms | Includes concept extraction + Hebbian update |
| Query by concept | 0.5ms | 8ms | Single-depth traversal, 10 results |
| Get related nodes | 0.3ms | 5ms | Direct edge lookup |
| Analyze content | 0.2ms | 0.2ms | No I/O, pattern matching only |
| List all nodes | 0.4ms | 6ms | 118 nodes |
| Bulk import (100) | 85ms | 1200ms | Batch transaction |

### Scaling Characteristics

| Scale | Memory Count | Edge Count | RAM Usage | Disk Size | Query Time (p95) |
|-------|--------------|------------|-----------|-----------|------------------|
| Small | 1K | 500 | 50MB | 15MB | <1ms |
| Medium | 100K | 50K | 500MB | 150MB | <5ms |
| Large | 1M | 500K | 2GB | 1.5GB | <20ms |
| Enterprise | 10M | 5M | 8GB | 15GB | <50ms |

**Recommendations:**

- **RAM Disk**: Strongly recommended for >10K memories
- **Indexing**: Automatic on `edges(source_node_id, target_node_id)` and `memory_nodes(node_id)`
- **Connection Pooling**: Use single server instance per deployment unit
- **Batch Operations**: Use `bulk_import` for >100 memories at once

### Resource Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 2GB
- Disk: 100MB + 1KB per memory (approx)

**Recommended Production:**
- CPU: 4+ cores
- RAM: 8GB (includes 2GB RAM disk allocation)
- Disk: 10GB SSD
- Network: Low latency to FAISS server if enabled

---

## Integration Patterns

### Pattern 1: AI Agent Memory

```python
class CognitiveAgent:
    def __init__(self):
        self.memory = HebbianMindClient(ram_disk_enabled=True)

    async def process_interaction(self, user_input: str, context: dict):
        # Retrieve relevant memories
        relevant = self.memory.query(
            concept="conversation",
            limit=5,
            min_edge_weight=2.0
        )

        # Generate response using context + memory
        response = await self.llm.generate(
            prompt=user_input,
            context=relevant
        )

        # Save interaction with learned associations
        self.memory.save(
            content=f"User: {user_input}\nAgent: {response}",
            source="interaction",
            metadata={
                "user_id": context["user_id"],
                "session_id": context["session_id"]
            }
        )

        return response
```

### Pattern 2: Concept Discovery Pipeline

```python
class ConceptLearningPipeline:
    def __init__(self):
        self.memory = HebbianMindClient()

    def ingest_corpus(self, documents: List[str]):
        """Ingest documents and discover concept relationships"""

        results = self.memory.bulk_import(
            memories=[
                {"content": doc, "source": "corpus"}
                for doc in documents
            ],
            learn_edges=True
        )

        print(f"Ingested {results['imported_count']} documents")
        print(f"Discovered {results['new_edges']} new concept relationships")

    def get_concept_clusters(self, min_weight: float = 3.0):
        """Extract strong concept clusters"""

        all_nodes = self.memory.list_nodes()

        clusters = []
        for node in all_nodes['nodes']:
            related = self.memory.get_related_nodes(
                concept=node['name'],
                min_weight=min_weight,
                max_depth=2
            )

            if len(related['related_nodes']) >= 3:
                clusters.append({
                    'core_concept': node['name'],
                    'cluster': related['related_nodes']
                })

        return clusters
```

### Pattern 3: Multi-Tenant Deployment

```python
class TenantMemoryManager:
    def __init__(self):
        self.tenants = {}

    def get_tenant_memory(self, tenant_id: str) -> HebbianMindClient:
        if tenant_id not in self.tenants:
            self.tenants[tenant_id] = HebbianMindClient(
                base_dir=f"./data/tenants/{tenant_id}",
                ram_disk_enabled=True,
                ram_disk_path=f"R:/HEBBIAN_{tenant_id}"
            )
        return self.tenants[tenant_id]

    async def save_tenant_memory(self, tenant_id: str, content: str):
        memory = self.get_tenant_memory(tenant_id)
        return memory.save(content, source=f"tenant_{tenant_id}")
```

---

## Deployment

### Standalone Server

```bash
# Install
pip install hebbian-mind-enterprise

# Configure
export HEBBIAN_MIND_BASE_DIR="/var/lib/hebbian_mind"
export HEBBIAN_MIND_RAM_DISK="true"
export HEBBIAN_MIND_RAM_DIR="/mnt/ramdisk"

# Run as systemd service
cat > /etc/systemd/system/hebbian-mind.service <<EOF
[Unit]
Description=Hebbian Mind Enterprise MCP Server
After=network.target

[Service]
Type=simple
User=hebbian
WorkingDirectory=/opt/hebbian-mind
Environment="HEBBIAN_MIND_BASE_DIR=/var/lib/hebbian_mind"
Environment="HEBBIAN_MIND_RAM_DISK=true"
Environment="HEBBIAN_MIND_RAM_DIR=/mnt/ramdisk"
ExecStart=/usr/bin/python3 -m hebbian_mind
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl enable hebbian-mind
systemctl start hebbian-mind
```

### Docker Compose

```yaml
version: '3.8'

services:
  hebbian-mind:
    image: cipscorps/hebbian-mind-enterprise:latest
    container_name: hebbian-mind
    environment:
      - HEBBIAN_MIND_BASE_DIR=/data
      - HEBBIAN_MIND_RAM_DISK=true
      - HEBBIAN_MIND_RAM_DIR=/ramdisk
      - HEBBIAN_MIND_LOG_LEVEL=INFO
    volumes:
      - hebbian_data:/data
    tmpfs:
      - /ramdisk:rw,size=1g
    restart: unless-stopped
    networks:
      - ai_backend

  # Optional: FAISS vector server
  faiss-server:
    image: cipscorps/faiss-server:latest
    container_name: faiss-server
    environment:
      - FAISS_PORT=9998
    volumes:
      - faiss_data:/data
    restart: unless-stopped
    networks:
      - ai_backend

volumes:
  hebbian_data:
  faiss_data:

networks:
  ai_backend:
    driver: bridge
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hebbian-mind
spec:
  replicas: 3
  selector:
    matchLabels:
      app: hebbian-mind
  template:
    metadata:
      labels:
        app: hebbian-mind
    spec:
      containers:
      - name: hebbian-mind
        image: cipscorps/hebbian-mind-enterprise:latest
        env:
        - name: HEBBIAN_MIND_BASE_DIR
          value: "/data"
        - name: HEBBIAN_MIND_RAM_DISK
          value: "true"
        - name: HEBBIAN_MIND_RAM_DIR
          value: "/ramdisk"
        volumeMounts:
        - name: data
          mountPath: /data
        - name: ramdisk
          mountPath: /ramdisk
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: hebbian-mind-pvc
      - name: ramdisk
        emptyDir:
          medium: Memory
          sizeLimit: 1Gi
```

---

## Support

### Enterprise Support

CIPS LLC provides enterprise support packages for Hebbian Mind Enterprise:

- **24/7 Support**: Critical issue response within 1 hour
- **Architecture Review**: System design consultation
- **Custom Integration**: Tailored deployment for your infrastructure
- **Performance Tuning**: Optimization for your workload
- **Training**: Team onboarding and best practices

Contact: enterprise@cipscorps.com

### Documentation

- **Full Documentation**: https://docs.cipscorps.com/hebbian-mind
- **API Reference**: https://docs.cipscorps.com/hebbian-mind/api
- **Examples**: https://github.com/cipscorps/hebbian-mind-examples

### Community

- **GitHub Issues**: https://github.com/cipscorps/hebbian-mind-enterprise/issues
- **Discussions**: https://github.com/cipscorps/hebbian-mind-enterprise/discussions

---

## License

**Proprietary License - CIPS LLC**

Copyright (c) 2026 CIPS LLC. All rights reserved.

This software is licensed for enterprise use. See LICENSE file for terms.

For licensing inquiries: licensing@cipscorps.com

---

## About CIPS LLC

CIPS LLC develops enterprise AI infrastructure with a focus on cognitive architectures, memory systems, and agent orchestration. Our products are deployed in production environments serving millions of AI interactions daily.

**Product Line:**
- Hebbian Mind Enterprise (Neural Graph Memory)
- CASCADE Memory (Multi-Layer Memory Architecture)
- FAISS Enterprise (GPU-Accelerated Vector Search)
- Galaxy Brain (Sequential Thinking + Doing)
- Capability Graph (Living Skill Memory)

**Website**: https://cipscorps.com

**Contact**: contact@cipscorps.com

---

**Built on the principle: "Neurons that fire together, wire together"**

*Hebbian Mind Enterprise - Where AI learns like minds do.*