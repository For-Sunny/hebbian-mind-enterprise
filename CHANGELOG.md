# Changelog

All notable changes to Hebbian Mind Enterprise will be documented in this file.

## [2.3.1] - 2026-02-18

Documentation and contact information fixes applied during three-path verification.

### Fixed
- **Homeostatic scaling correction** - Post-release patch for edge weight normalization precision applied after 2.3.0 verification
- **Version strings synchronized** - `pyproject.toml`, `__init__.py`, `server.py`, and `Dockerfile` all updated to 2.3.1
- **Contact email domain** - `contact@cipscorps.com` corrected to `contact@cipscorps.io` in `pyproject.toml`, `SECURITY.md`, `DEPLOYMENT.md`, `tests/TEST_SUITE_SUMMARY.md`
- **Documentation URLs** - `docs.cipscorps.com` corrected to `docs.cipscorps.io` in `pyproject.toml`, `SECURITY.md`, `DEPLOYMENT.md`, `README_DOCKER.md`
- **Homepage URL** - `cipscorps.com` corrected to `cipscorps.io` in `pyproject.toml`
- **Repository URL** - `github.com/cipscorps/` corrected to `github.com/For-Sunny/` in `pyproject.toml`
- **CHANGELOG** - Added missing `[2.3.1]` entry (version was bumped in code without updating changelog)
- **.gitattributes** - Created with LF enforcement for all text file types

---

## [2.3.0] - 2026-02-17

### Fixed
- **CRITICAL: Edge saturation** - Harmonic formula `delta = 1/(1+w)` drove all edges to MAX_WEIGHT (10.0) after ~76 co-activations. Every edge the same weight means no edge matters. Signal differentiation destroyed.
  - Replaced with asymptotic formula: `delta = (MAX_WEIGHT - current) * LEARNING_RATE`
  - Edges approach maximum but never reach it. Weight diversity preserved.
  - LEARNING_RATE = 0.1 (closes 10% of remaining gap per co-activation)

### Added
- **Time-based edge decay** - Edges idle >1 hour lose 2% weight per homeostatic tick via `_apply_time_decay()`
  - New `last_coactivated` column on edges table (schema migration included, idempotent)
  - Backwards compatible: falls back to `last_strengthened` via COALESCE
- **Homeostatic scaling** - Per-node weight normalization via `_apply_homeostatic_scaling()`
  - Target: 50.0 total weight per node
  - Triggers every 5 co-activations
  - Prevents runaway weight accumulation on high-activity nodes
- **Transaction boundary methods** - `_begin`, `_commit`, `_rollback_transaction`
- **3 database indexes** for query performance:
  - `idx_edges_target_id` (reverse edge lookups)
  - `idx_memact_memory_id` (memory activation JOINs)
  - `idx_memact_node_id` (node activation filters)

### Changed
- `save_memory()` wrapped in single transaction: 21 separate commits reduced to 2 (1 disk + 1 RAM). ~20x faster.
- Dual-write order reversed to disk-first, RAM-second for crash safety
- Edge strengthening uses constant LEARNING_RATE (0.1) instead of dynamic harmonic factor

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
