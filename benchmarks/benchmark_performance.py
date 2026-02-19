#!/usr/bin/env python3
"""
Hebbian Mind Enterprise - Performance Benchmark Suite
=====================================================

Measures save latency, query latency, analyze latency, and database footprint.
Results are compared against README performance claims.

Usage:
    python benchmarks/benchmark_performance.py

Runs in an isolated temp directory. No production data is affected.

Copyright (c) 2026 CIPS LLC
"""

import json
import os
import platform
import re
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
import uuid


def get_system_info() -> dict:
    """Collect system information for reproducibility."""
    info = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "processor": platform.processor() or platform.machine(),
        "machine": platform.machine(),
    }
    try:
        import psutil
        info["ram_total_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        info["cpu_count"] = psutil.cpu_count(logical=True)
    except ImportError:
        info["ram_total_gb"] = "unknown (install psutil for details)"
        info["cpu_count"] = os.cpu_count()
    return info


# ---------------------------------------------------------------------------
# Standalone database setup (no module import needed)
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    keywords TEXT NOT NULL,
    prototype_phrases TEXT NOT NULL,
    description TEXT,
    weight REAL DEFAULT 1.0,
    activation_count INTEGER DEFAULT 0,
    last_activated TIMESTAMP
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    weight REAL DEFAULT 0.1,
    co_activation_count INTEGER DEFAULT 0,
    last_strengthened TIMESTAMP,
    last_coactivated REAL,
    FOREIGN KEY (source_id) REFERENCES nodes(id),
    FOREIGN KEY (target_id) REFERENCES nodes(id),
    UNIQUE(source_id, target_id)
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    source TEXT DEFAULT 'BENCHMARK',
    importance REAL DEFAULT 0.5,
    emotional_intensity REAL DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed REAL,
    effective_importance REAL,
    access_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS memory_activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL,
    node_id INTEGER NOT NULL,
    activation_score REAL NOT NULL,
    FOREIGN KEY (node_id) REFERENCES nodes(id)
);

CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_nodes_category ON nodes(category);
CREATE INDEX IF NOT EXISTS idx_edges_weight ON edges(weight);
CREATE INDEX IF NOT EXISTS idx_edges_target_id ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source);
CREATE INDEX IF NOT EXISTS idx_memact_memory_id ON memory_activations(memory_id);
CREATE INDEX IF NOT EXISTS idx_memact_node_id ON memory_activations(node_id);
CREATE INDEX IF NOT EXISTS idx_memories_effective_importance ON memories(effective_importance);
"""

# Nodes matching the enterprise content used in benchmarks
BENCHMARK_NODES = [
    {"id": "system", "name": "System", "category": "Systems & Architecture",
     "keywords": ["system"], "prototype_phrases": ["distributed system"]},
    {"id": "architecture", "name": "Architecture", "category": "Systems & Architecture",
     "keywords": ["architecture", "microservices"], "prototype_phrases": ["microservices architecture"]},
    {"id": "service", "name": "Service", "category": "Systems & Architecture",
     "keywords": ["service", "services"], "prototype_phrases": ["backend servers"]},
    {"id": "api", "name": "API", "category": "Systems & Architecture",
     "keywords": ["api"], "prototype_phrases": ["API rate limiting"]},
    {"id": "deployment", "name": "Deployment", "category": "Operations",
     "keywords": ["deployment", "deploy"], "prototype_phrases": ["independent deployment"]},
    {"id": "authentication", "name": "Authentication", "category": "Security",
     "keywords": ["authentication", "jwt"], "prototype_phrases": ["JWT authentication"]},
    {"id": "security", "name": "Security", "category": "Security",
     "keywords": ["security", "encryption", "tls"], "prototype_phrases": ["TLS encryption"]},
    {"id": "database", "name": "Database", "category": "Data & Memory",
     "keywords": ["database", "indexing"], "prototype_phrases": ["database indexing"]},
    {"id": "cache", "name": "Cache", "category": "Data & Memory",
     "keywords": ["cache", "caching", "redis"], "prototype_phrases": ["Redis caching"]},
    {"id": "performance", "name": "Performance", "category": "Quality",
     "keywords": ["performance", "latency", "load"], "prototype_phrases": ["query performance"]},
    {"id": "reliability", "name": "Reliability", "category": "Quality",
     "keywords": ["reliability", "failure"], "prototype_phrases": ["cascading failures"]},
    {"id": "monitoring", "name": "Monitoring", "category": "Operations",
     "keywords": ["monitoring", "health"], "prototype_phrases": ["health check"]},
    {"id": "pipeline", "name": "Pipeline", "category": "Operations",
     "keywords": ["pipeline", "orchestration"], "prototype_phrases": ["container orchestration"]},
    {"id": "pattern", "name": "Pattern", "category": "Logic & Reasoning",
     "keywords": ["pattern"], "prototype_phrases": ["circuit breaker pattern"]},
    {"id": "component", "name": "Component", "category": "Systems & Architecture",
     "keywords": ["component", "coupling"], "prototype_phrases": ["loose coupling"]},
    {"id": "event", "name": "Event", "category": "Systems & Architecture",
     "keywords": ["event", "event-driven"], "prototype_phrases": ["event-driven architecture"]},
    {"id": "traffic", "name": "Traffic", "category": "Operations",
     "keywords": ["traffic", "load balancer"], "prototype_phrases": ["distributes traffic"]},
    {"id": "container", "name": "Container", "category": "Operations",
     "keywords": ["container", "kubernetes", "docker"], "prototype_phrases": ["container orchestration"]},
    {"id": "data", "name": "Data", "category": "Data & Memory",
     "keywords": ["data"], "prototype_phrases": ["data in transit"]},
    {"id": "session", "name": "Session", "category": "Security",
     "keywords": ["session"], "prototype_phrases": ["session management"]},
]

LEARNING_RATE = 0.1
MAX_WEIGHT = 10.0
MIN_WEIGHT = 0.1


def create_benchmark_db(db_path: str) -> sqlite3.Connection:
    """Create a fresh database with schema and nodes."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()

    # Insert nodes
    for node in BENCHMARK_NODES:
        conn.execute(
            "INSERT OR IGNORE INTO nodes (node_id, name, category, keywords, prototype_phrases, description, weight) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (node["id"], node["name"], node["category"],
             json.dumps(node["keywords"]), json.dumps(node["prototype_phrases"]),
             "", 1.0)
        )
    conn.commit()

    # Initialize category edges
    cursor = conn.execute("SELECT id, category FROM nodes")
    nodes = cursor.fetchall()
    by_cat = {}
    for n in nodes:
        cat = n["category"]
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(n["id"])

    now = time.time()
    for cat, ids in by_cat.items():
        for i, id1 in enumerate(ids):
            for id2 in ids[i+1:]:
                s, t = min(id1, id2), max(id1, id2)
                conn.execute(
                    "INSERT OR IGNORE INTO edges (source_id, target_id, weight, co_activation_count, last_strengthened, last_coactivated) "
                    "VALUES (?, ?, 0.1, 0, ?, ?)",
                    (s, t, now, now)
                )
    conn.commit()
    return conn


def analyze_content(conn: sqlite3.Connection, content: str, threshold: float = 0.3):
    """Analyze content against nodes. Returns activations."""
    cursor = conn.execute("SELECT * FROM nodes")
    nodes = cursor.fetchall()
    content_lower = content.lower()
    activations = []

    for node in nodes:
        keywords = json.loads(node["keywords"])
        phrases = json.loads(node["prototype_phrases"])
        score = 0.0

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in content_lower:
                if re.search(r'\b' + re.escape(kw_lower) + r'\b', content_lower):
                    score += 0.25
                else:
                    score += 0.1

        for phrase in phrases:
            if phrase.lower() in content_lower:
                score += 0.35

        score = min(score, 1.0)
        if score >= threshold:
            activations.append({
                "node_id": node["id"],
                "node_name": node["node_id"],
                "name": node["name"],
                "category": node["category"],
                "score": score,
            })

    activations.sort(key=lambda x: x["score"], reverse=True)
    return activations


def save_memory(conn: sqlite3.Connection, content: str, activations: list,
                memory_id: str, importance: float = 0.5):
    """Save a memory with activations and Hebbian strengthening."""
    now = time.time()

    conn.execute(
        "INSERT INTO memories (memory_id, content, summary, source, importance, "
        "emotional_intensity, last_accessed, effective_importance, access_count) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
        (memory_id, content, f"Bench {memory_id[:8]}", "BENCHMARK",
         importance, 0.3, now, importance)
    )

    for act in activations:
        conn.execute(
            "INSERT INTO memory_activations (memory_id, node_id, activation_score) "
            "VALUES (?, ?, ?)",
            (memory_id, act["node_id"], act["score"])
        )
        conn.execute(
            "UPDATE nodes SET activation_count = activation_count + 1, "
            "last_activated = CURRENT_TIMESTAMP WHERE id = ?",
            (act["node_id"],)
        )

    # Hebbian edge strengthening
    node_ids = [a["node_id"] for a in activations]
    for i, src in enumerate(node_ids):
        for tgt in node_ids[i+1:]:
            id1, id2 = min(src, tgt), max(src, tgt)
            row = conn.execute(
                "SELECT weight FROM edges WHERE source_id = ? AND target_id = ?",
                (id1, id2)
            ).fetchone()

            if not row:
                conn.execute(
                    "INSERT INTO edges (source_id, target_id, weight, co_activation_count, "
                    "last_strengthened, last_coactivated) VALUES (?, ?, 0.15, 1, ?, ?)",
                    (id1, id2, now, now)
                )
            else:
                current = row["weight"]
                delta = (MAX_WEIGHT - current) * LEARNING_RATE
                new_weight = max(MIN_WEIGHT, min(MAX_WEIGHT, current + delta))
                conn.execute(
                    "UPDATE edges SET weight = ?, co_activation_count = co_activation_count + 1, "
                    "last_strengthened = ?, last_coactivated = ? "
                    "WHERE source_id = ? AND target_id = ?",
                    (new_weight, now, now, id1, id2)
                )

    conn.commit()


def query_by_nodes(conn: sqlite3.Connection, node_names: list, limit: int = 20):
    """Query memories by node names."""
    node_ids = []
    for name in node_names:
        row = conn.execute(
            "SELECT id FROM nodes WHERE node_id = ? OR name = ? OR LOWER(name) = LOWER(?)",
            (name, name, name)
        ).fetchone()
        if row:
            node_ids.append(row["id"])

    if not node_ids:
        return []

    placeholders = ",".join("?" * len(node_ids))
    cursor = conn.execute(
        f"SELECT DISTINCT m.* FROM memories m "
        f"JOIN memory_activations ma ON m.memory_id = ma.memory_id "
        f"WHERE ma.node_id IN ({placeholders}) "
        f"ORDER BY m.created_at DESC LIMIT ?",
        (*node_ids, limit)
    )
    return [dict(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Benchmark functions
# ---------------------------------------------------------------------------

BENCHMARK_CONTENTS = [
    "Microservices architecture enables independent deployment of services",
    "JWT authentication tokens provide stateless session management",
    "Database indexing improves query performance significantly",
    "Load balancer distributes traffic across multiple backend servers",
    "Container orchestration with Kubernetes manages service lifecycle",
    "API rate limiting prevents abuse and ensures fair resource usage",
    "Event-driven architecture enables loose coupling between components",
    "Redis caching reduces database load for frequently accessed data",
    "TLS encryption secures data in transit between client and server",
    "Circuit breaker pattern prevents cascading failures in distributed systems",
]


def percentile(data, p):
    """Calculate the p-th percentile of a sorted list."""
    idx = int(len(data) * p / 100)
    idx = min(idx, len(data) - 1)
    return sorted(data)[idx]


def run_save_benchmark(conn, iterations=200) -> dict:
    """Benchmark save_memory latency."""
    latencies = []
    skipped = 0

    for i in range(iterations):
        content = BENCHMARK_CONTENTS[i % len(BENCHMARK_CONTENTS)]
        activations = analyze_content(conn, content)

        if not activations:
            skipped += 1
            continue

        memory_id = f"bench_{uuid.uuid4().hex[:16]}"

        start = time.perf_counter()
        save_memory(conn, content, activations, memory_id)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

    if not latencies:
        return {"error": "No activations matched", "skipped": skipped}

    return {
        "operation": "save_memory",
        "iterations": len(latencies),
        "skipped": skipped,
        "mean_ms": round(statistics.mean(latencies), 3),
        "median_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(percentile(latencies, 95), 3),
        "p99_ms": round(percentile(latencies, 99), 3),
        "min_ms": round(min(latencies), 3),
        "max_ms": round(max(latencies), 3),
    }


def run_query_benchmark(conn, iterations=200) -> dict:
    """Benchmark query_by_nodes latency."""
    node_queries = [
        ["architecture"],
        ["security", "authentication"],
        ["database", "performance"],
        ["deployment"],
        ["api", "service"],
    ]

    latencies = []
    for i in range(iterations):
        nodes = node_queries[i % len(node_queries)]

        start = time.perf_counter()
        query_by_nodes(conn, nodes, limit=20)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

    return {
        "operation": "query_by_nodes",
        "iterations": len(latencies),
        "mean_ms": round(statistics.mean(latencies), 3),
        "median_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(percentile(latencies, 95), 3),
        "p99_ms": round(percentile(latencies, 99), 3),
        "min_ms": round(min(latencies), 3),
        "max_ms": round(max(latencies), 3),
    }


def run_analyze_benchmark(conn, iterations=200) -> dict:
    """Benchmark analyze_content latency."""
    latencies = []
    for i in range(iterations):
        content = BENCHMARK_CONTENTS[i % len(BENCHMARK_CONTENTS)]

        start = time.perf_counter()
        analyze_content(conn, content)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

    return {
        "operation": "analyze_content",
        "iterations": len(latencies),
        "mean_ms": round(statistics.mean(latencies), 3),
        "median_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(percentile(latencies, 95), 3),
        "p99_ms": round(percentile(latencies, 99), 3),
        "min_ms": round(min(latencies), 3),
        "max_ms": round(max(latencies), 3),
    }


def measure_db_size(db_path: str) -> dict:
    """Measure database file size."""
    conn = sqlite3.connect(db_path)
    node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    memory_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    conn.close()

    file_size = os.path.getsize(db_path)
    return {
        "file_size_bytes": file_size,
        "file_size_kb": round(file_size / 1024, 1),
        "node_count": node_count,
        "edge_count": edge_count,
        "memory_count": memory_count,
        "bytes_per_node": round(file_size / max(node_count, 1)),
        "bytes_per_edge": round(file_size / max(edge_count, 1)) if edge_count else 0,
    }


def main():
    print("=" * 64)
    print("  Hebbian Mind Enterprise - Performance Benchmark")
    print("=" * 64)
    print()

    system_info = get_system_info()
    print("System:")
    for key, value in system_info.items():
        print(f"  {key}: {value}")
    print()

    # Create temp directory
    tmp_dir = tempfile.mkdtemp(prefix="hebbian_bench_")
    db_path = os.path.join(tmp_dir, "hebbian_mind.db")

    try:
        print(f"Database: {db_path}")
        print()

        # Setup
        print("Initializing database with 20 enterprise nodes...")
        conn = create_benchmark_db(db_path)
        node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        print(f"  Nodes: {node_count}, Initial edges: {edge_count}")

        # Verify activations work
        test_acts = analyze_content(conn, BENCHMARK_CONTENTS[0])
        print(f"  Test activation: {len(test_acts)} nodes matched")
        if not test_acts:
            print("  ERROR: No activations. Cannot benchmark save. Exiting.")
            return
        print()

        iterations = 200

        # Save benchmark
        print(f"Save benchmark ({iterations} iterations)...")
        save_results = run_save_benchmark(conn, iterations)
        if "error" in save_results:
            print(f"  FAILED: {save_results['error']}")
        else:
            print(f"  Mean: {save_results['mean_ms']:.2f}ms  "
                  f"Median: {save_results['median_ms']:.2f}ms  "
                  f"P95: {save_results['p95_ms']:.2f}ms  "
                  f"P99: {save_results['p99_ms']:.2f}ms")
        print()

        # Query benchmark
        print(f"Query benchmark ({iterations} iterations)...")
        query_results = run_query_benchmark(conn, iterations)
        print(f"  Mean: {query_results['mean_ms']:.2f}ms  "
              f"Median: {query_results['median_ms']:.2f}ms  "
              f"P95: {query_results['p95_ms']:.2f}ms  "
              f"P99: {query_results['p99_ms']:.2f}ms")
        print()

        # Analyze benchmark
        print(f"Analyze benchmark ({iterations} iterations)...")
        analyze_results = run_analyze_benchmark(conn, iterations)
        print(f"  Mean: {analyze_results['mean_ms']:.2f}ms  "
              f"Median: {analyze_results['median_ms']:.2f}ms  "
              f"P95: {analyze_results['p95_ms']:.2f}ms  "
              f"P99: {analyze_results['p99_ms']:.2f}ms")
        print()

        # DB size
        conn.close()
        size_results = measure_db_size(db_path)
        print(f"Database size: {size_results['file_size_kb']} KB")
        print(f"  Nodes: {size_results['node_count']}  "
              f"Edges: {size_results['edge_count']}  "
              f"Memories: {size_results['memory_count']}")
        print()

        # Summary vs claims
        print("=" * 64)
        print("  RESULTS vs README CLAIMS")
        print("=" * 64)

        if "error" not in save_results:
            save_pass = save_results["median_ms"] < 10.0
            print(f"  Save latency:  claim <10ms  |  measured {save_results['median_ms']:.2f}ms  "
                  f"[{'PASS' if save_pass else 'FAIL'}]")

        query_pass = query_results["median_ms"] < 5.0
        print(f"  Query latency: claim <5ms   |  measured {query_results['median_ms']:.2f}ms  "
              f"[{'PASS' if query_pass else 'FAIL'}]")
        print()

        # Save full results as JSON
        full_results = {
            "system": system_info,
            "config": {
                "nodes": len(BENCHMARK_NODES),
                "iterations": iterations,
                "learning_rate": LEARNING_RATE,
                "max_weight": MAX_WEIGHT,
                "ram_disk": False,
                "notes": "Disk-only mode (no RAM disk). WAL journal mode.",
            },
            "benchmarks": {
                "save": save_results if "error" not in save_results else {"error": save_results["error"]},
                "query": query_results,
                "analyze": analyze_results,
                "db_size": size_results,
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        results_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "latest_results.json"
        )
        with open(results_path, "w") as f:
            json.dump(full_results, f, indent=2)
        print(f"Full results: {results_path}")

    finally:
        # Cleanup temp directory (Windows-safe: close conn before delete)
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
