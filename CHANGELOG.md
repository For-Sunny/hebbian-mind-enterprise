# Changelog

All notable changes to Hebbian Mind Enterprise will be documented in this file.

## [2.2.0] - 2026-02-09

### Added
- **Temporal Memory Decay** - Memories now decay over time using exponential formula:
  `effective_importance = importance * e^(-decay_rate * days_since_access)`
  - Memories with importance >= 0.9 are immortal (never decay)
  - Higher importance = slower decay rate
  - Decayed memories hidden by default in `query_mind`, visible with `include_decayed: true`
  - Touch-on-access: queried memories refresh their `last_accessed` timestamp
  - Periodic sweep recalculates `effective_importance` for all memories

- **Hebbian Edge Decay** - Edge weights weaken when not reinforced:
  - Edges decay toward minimum weight (0.1), never to zero
  - Separate decay rate from memory decay (default 0.005 vs 0.01)
  - Co-activation resets decay clock (existing `_strengthen_edge` updates `last_strengthened`)
  - Periodic sweep applies decay to all edges above minimum weight

- **Decay Engine** (`HebbianDecayEngine` class):
  - Configurable sweep interval (default: 60 minutes)
  - Daemon thread timer (non-blocking)
  - Full status and statistics reporting
  - Dual-write compliant (RAM + Disk)

- **New database columns**: `last_accessed`, `effective_importance`, `access_count` on memories table
- **Schema migration**: Automatic with duplicate-column-safe pattern
- **Backfill**: Existing memories get `last_accessed = created_at`, `effective_importance = importance`
- **New index**: `idx_memories_effective_importance` for decay-filtered queries

### Configuration (Environment Variables)
| Variable | Default | Description |
|----------|---------|-------------|
| `HEBBIAN_MIND_DECAY_ENABLED` | `true` | Enable memory decay |
| `HEBBIAN_MIND_DECAY_BASE_RATE` | `0.01` | Base exponential decay rate |
| `HEBBIAN_MIND_DECAY_THRESHOLD` | `0.1` | Below this = decayed |
| `HEBBIAN_MIND_DECAY_IMMORTAL_THRESHOLD` | `0.9` | Above this = immortal |
| `HEBBIAN_MIND_DECAY_SWEEP_INTERVAL` | `60` | Minutes between sweeps |
| `HEBBIAN_MIND_EDGE_DECAY_ENABLED` | `true` | Enable edge decay |
| `HEBBIAN_MIND_EDGE_DECAY_RATE` | `0.005` | Edge weight decay rate |
| `HEBBIAN_MIND_EDGE_DECAY_MIN_WEIGHT` | `0.1` | Minimum edge weight floor |

### Changed
- `query_mind` tool now accepts `include_decayed` parameter
- `mind_status` tool now reports decay engine status and memory/edge statistics
- `save_to_mind` sets decay fields (`last_accessed`, `effective_importance`, `access_count`) on save

## [2.1.0] - 2026-01-15

### Added
- Initial enterprise release
- Hebbian learning with dual-write architecture (RAM + Disk)
- PRECOG concept extractor integration
- FAISS tether bridge for semantic search
- Error message sanitization (no internal path leakage)
- Docker support with standalone mode
