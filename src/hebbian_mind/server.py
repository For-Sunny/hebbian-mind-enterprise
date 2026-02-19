#!/usr/bin/env python3
"""
Hebbian Mind Enterprise - Neural Graph Memory System
====================================================

MCP server implementing Hebbian learning for associative memory.
"Neurons that fire together, wire together"

DUAL-WRITE ARCHITECTURE
- RAM disk for instant reads (optional)
- Disk storage for permanent truth
- WRITE: Disk first (crash-safe) -> RAM second (speed)
- READ: RAM (instant) with disk fallback
- Copy disk to RAM on startup if RAM empty

Copyright (c) 2026 CIPS LLC
All rights reserved.
"""

import asyncio
import json
import re
import sqlite3
import socket
import sys
import time
import logging
import shutil
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
from importlib import resources

from .config import Config, sanitize_error_message
from .decay import HebbianDecayEngine

# Initialize configuration
Config.ensure_directories()

# Initialize logger
logger = logging.getLogger("hebbian-mind")

# PRECOG Integration (optional concept extraction)
PRECOG_AVAILABLE = False
if Config.PRECOG_ENABLED and Config.PRECOG_PATH:
    if str(Config.PRECOG_PATH) not in sys.path:
        sys.path.insert(0, str(Config.PRECOG_PATH))

    try:
        from concept_extractor import extract_concepts

        PRECOG_AVAILABLE = True
        print("[HEBBIAN-MIND] PRECOG ConceptExtractor loaded successfully", file=sys.stderr)
    except ImportError as e:
        print(f"[HEBBIAN-MIND] PRECOG ConceptExtractor not available: {e}", file=sys.stderr)

# Anti-saturation parameters (Feb 16, 2026)
LEARNING_RATE = 0.1  # Asymptotic approach rate
MAX_WEIGHT = 10.0  # Maximum edge weight (unchanged)
MIN_WEIGHT = 0.1  # Minimum edge weight
TARGET_TOTAL_WEIGHT = 50.0  # Target sum of edge weights per node
SCALING_RATE = 0.3  # Homeostatic scaling factor (27% correction per tick)
DECAY_IDLE_THRESHOLD = 3600  # 1 hour in seconds - edges idle longer than this decay
DECAY_IDLE_RATE = 0.02  # 2% weight loss per homeostatic tick for idle edges
HOMEOSTATIC_INTERVAL = 5  # Apply homeostatic scaling every N co-activations

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types
except ImportError:
    print("MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)


def check_ram_available() -> bool:
    """Check if RAM disk is available and writable."""
    return Config.check_ram_available()


USE_RAM = check_ram_available()


class HebbianMindDatabase:
    """SQLite database for Hebbian neural graph with DUAL-WRITE support."""

    def __init__(self):
        self.disk_path = Config.DISK_DB_PATH
        self.ram_path = Config.RAM_DB_PATH if USE_RAM else None
        self.using_ram = False
        self.read_conn = None  # Primary read connection (RAM if available)
        self.disk_conn = None  # Secondary write connection (disk - truth)
        self._in_transaction = False
        self._coactivation_count = 0
        self._lock = threading.RLock()  # Serialize all DB access across threads
        self._decay_engine: Optional[HebbianDecayEngine] = None

        self._init_connections()
        self._init_schema()
        self._ensure_last_coactivated_column()
        self._init_nodes_if_empty()

    def _init_connections(self):
        """Initialize read and write connections with dual-write pattern."""

        if USE_RAM and self.ram_path:
            # Check if RAM DB exists
            if self.ram_path.exists():
                # RAM DB exists - use it for reads
                print(f"[HEBBIAN-MIND] Using RAM disk for reads: {self.ram_path}", file=sys.stderr)
                self.using_ram = True
            elif self.disk_path.exists():
                # RAM available but empty - copy from disk first
                try:
                    shutil.copy2(self.disk_path, self.ram_path)
                    # Copy WAL and SHM if they exist
                    for ext in ["-wal", "-shm"]:
                        disk_extra = Path(str(self.disk_path) + ext)
                        ram_extra = Path(str(self.ram_path) + ext)
                        if disk_extra.exists():
                            shutil.copy2(disk_extra, ram_extra)
                    print(f"[HEBBIAN-MIND] Copied disk DB to RAM: {self.ram_path}", file=sys.stderr)
                    self.using_ram = True
                except Exception as e:
                    print(f"[HEBBIAN-MIND] Failed to copy to RAM, using disk: {e}", file=sys.stderr)
                    self.using_ram = False
            else:
                # No disk DB yet - will create on RAM, then sync to disk
                print(f"[HEBBIAN-MIND] Creating new DB on RAM: {self.ram_path}", file=sys.stderr)
                self.using_ram = True

        # Primary connection - for reads (RAM if available, else disk)
        read_path = self.ram_path if self.using_ram else self.disk_path
        self.read_conn = sqlite3.connect(str(read_path), check_same_thread=False)
        self.read_conn.row_factory = sqlite3.Row
        self.read_conn.execute("PRAGMA journal_mode=WAL")

        # Secondary connection for dual-write (disk) - only if reading from RAM
        if self.using_ram:
            self.disk_conn = sqlite3.connect(str(self.disk_path), check_same_thread=False)
            self.disk_conn.row_factory = sqlite3.Row
            self.disk_conn.execute("PRAGMA journal_mode=WAL")
            print("[HEBBIAN-MIND] Dual-write enabled: RAM + Disk", file=sys.stderr)
        else:
            self.disk_conn = None
            print("[HEBBIAN-MIND] Single-write mode: Disk only", file=sys.stderr)

    def _init_schema(self):
        """Initialize database schema on both connections."""
        schema = """
            -- Nodes table: the concept nodes
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

            -- Edges table: Hebbian connections between nodes
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                weight REAL DEFAULT 0.1,
                co_activation_count INTEGER DEFAULT 0,
                last_strengthened TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES nodes(id),
                FOREIGN KEY (target_id) REFERENCES nodes(id),
                UNIQUE(source_id, target_id)
            );

            -- Memories table
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                source TEXT DEFAULT 'HEBBIAN_MIND',
                importance REAL DEFAULT 0.5,
                emotional_intensity REAL DEFAULT 0.5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Memory-to-node activation mapping
            CREATE TABLE IF NOT EXISTS memory_activations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                node_id INTEGER NOT NULL,
                activation_score REAL NOT NULL,
                FOREIGN KEY (node_id) REFERENCES nodes(id)
            );

            -- Indexes
            CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
            CREATE INDEX IF NOT EXISTS idx_nodes_category ON nodes(category);
            CREATE INDEX IF NOT EXISTS idx_edges_weight ON edges(weight);
            CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source);

            -- Performance indexes (Feb 16, 2026)
            CREATE INDEX IF NOT EXISTS idx_edges_target_id ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_memact_memory_id ON memory_activations(memory_id);
            CREATE INDEX IF NOT EXISTS idx_memact_node_id ON memory_activations(node_id);
        """

        # Apply schema to read connection (RAM or disk)
        self.read_conn.executescript(schema)
        self.read_conn.commit()

        # Apply schema to disk connection if dual-write
        if self.disk_conn:
            self.disk_conn.executescript(schema)
            self.disk_conn.commit()

        # === Decay column migrations ===
        decay_migrations = [
            "ALTER TABLE memories ADD COLUMN last_accessed REAL",
            "ALTER TABLE memories ADD COLUMN effective_importance REAL",
            "ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0",
        ]
        for conn in [self.read_conn] + ([self.disk_conn] if self.disk_conn else []):
            for migration in decay_migrations:
                try:
                    conn.execute(migration)
                except sqlite3.OperationalError as e:
                    if "duplicate column" not in str(e).lower():
                        raise

            # Backfill: set last_accessed from created_at, effective_importance from importance
            conn.execute("""
                UPDATE memories SET
                    last_accessed = CAST(strftime('%s', created_at) AS REAL),
                    effective_importance = importance,
                    access_count = 0
                WHERE last_accessed IS NULL
            """)
            conn.commit()

        # Index for decay queries
        self.read_conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_effective_importance "
            "ON memories(effective_importance)"
        )
        self.read_conn.commit()
        if self.disk_conn:
            self.disk_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_effective_importance "
                "ON memories(effective_importance)"
            )
            self.disk_conn.commit()

    def _ensure_last_coactivated_column(self):
        """Add last_coactivated column to edges table if missing (schema migration)."""
        connections = [self.read_conn]
        if self.disk_conn and self.disk_conn != self.read_conn:
            connections.append(self.disk_conn)
        for conn in connections:
            cursor = conn.execute("PRAGMA table_info(edges)")
            columns = [
                row[1] if isinstance(row, tuple) else row["name"] for row in cursor.fetchall()
            ]
            if "last_coactivated" not in columns:
                conn.execute("ALTER TABLE edges ADD COLUMN last_coactivated REAL")
                conn.commit()

    def _init_nodes_if_empty(self):
        """Load nodes from nodes_v2.json if table is empty.

        Search order:
        1. User's data directory: nodes_v2.json
        2. User's data directory: nodes.json
        3. Package bundled data: nodes_v2.json
        4. Package bundled data: nodes.json
        """
        cursor = self.read_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM nodes")
        if cursor.fetchone()[0] > 0:
            return  # Already has nodes

        nodes_data = None
        source_name = None

        # Try user's data directory first (allows customization)
        user_paths = [Config.DISK_NODES_PATH, Config.DISK_DATA_DIR / "nodes.json"]  # nodes_v2.json

        for user_path in user_paths:
            if user_path.exists():
                try:
                    with open(user_path, "r", encoding="utf-8") as f:
                        nodes_data = json.load(f)
                    source_name = str(user_path)
                    break
                except Exception as e:
                    logger.warning(f"Failed to load {user_path}: {e}")

        # Fall back to package bundled data if no user file found
        if nodes_data is None:
            bundled_files = ["nodes_v2.json", "nodes.json"]
            for bundled_file in bundled_files:
                try:
                    # Python 3.9+ compatible resource loading
                    if hasattr(resources, "files"):
                        # Python 3.9+
                        data_files = resources.files("hebbian_mind").joinpath("data")
                        nodes_file = data_files.joinpath(bundled_file)
                        if nodes_file.is_file():
                            nodes_data = json.loads(nodes_file.read_text(encoding="utf-8"))
                            source_name = f"bundled:{bundled_file}"
                            break
                    else:
                        # Python 3.8 fallback
                        with resources.open_text("hebbian_mind.data", bundled_file) as f:
                            nodes_data = json.load(f)
                        source_name = f"bundled:{bundled_file}"
                        break
                except Exception:
                    continue

        if nodes_data is None:
            logger.warning("No nodes file found. Starting with empty graph.")
            return

        nodes = nodes_data.get("nodes", nodes_data)

        if len(nodes) == 0:
            logger.warning("No nodes loaded. Graph will be empty until nodes are added.")
            return

        # Insert nodes to both connections
        for node in nodes:
            self._insert_node(node)

        # Initialize edges between same-category nodes
        self._init_category_edges()

        logger.info(f"Loaded {len(nodes)} nodes from {source_name}")

    def _insert_node(self, node: Dict):
        """Insert a node to both RAM and disk."""
        sql = """
            INSERT OR IGNORE INTO nodes (node_id, name, category, keywords, prototype_phrases, description, weight)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            node.get("id", node.get("node_id")),
            node.get("name", ""),
            node.get("category", ""),
            json.dumps(node.get("keywords", [])),
            json.dumps(node.get("prototype_phrases", [])),
            node.get("description", ""),
            node.get("weight", 1.0),
        )

        self.read_conn.execute(sql, params)
        self.read_conn.commit()

        if self.disk_conn:
            self.disk_conn.execute(sql, params)
            self.disk_conn.commit()

    def _init_category_edges(self):
        """Initialize weak edges between nodes in same category."""
        cursor = self.read_conn.cursor()
        cursor.execute("SELECT id, category FROM nodes")
        nodes = cursor.fetchall()

        # Group by category
        by_category = {}
        for node in nodes:
            cat = node["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(node["id"])

        # Create edges within categories
        for cat, node_ids in by_category.items():
            for i, id1 in enumerate(node_ids):
                for id2 in node_ids[i + 1 :]:
                    self._create_edge(id1, id2, 0.1)

    def _create_edge(self, source_id: int, target_id: int, weight: float = 0.1):
        """Create edge between nodes with initial weight.

        Only used during initialization for category edges.
        Uses dual-write and time.time() for consistency with the rest of the codebase.
        """
        # Ensure consistent ordering
        id1, id2 = min(source_id, target_id), max(source_id, target_id)
        now = time.time()

        # Check if edge exists
        cursor = self.read_conn.execute(
            "SELECT id FROM edges WHERE source_id = ? AND target_id = ?", (id1, id2)
        )
        existing = cursor.fetchone()
        if existing:
            return existing[0]

        # Create new edge using dual-write pattern
        self._dual_write(
            """INSERT INTO edges
               (source_id, target_id, weight, co_activation_count, last_strengthened, last_coactivated)
               VALUES (?, ?, ?, 0, ?, ?)""",
            (id1, id2, weight, now, now),
        )

        # Get the created edge ID
        cursor = self.read_conn.execute(
            "SELECT id FROM edges WHERE source_id = ? AND target_id = ?", (id1, id2)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def _dual_write(self, sql: str, params: tuple = ()):
        """Execute SQL on both disk and RAM, skip commits if in transaction.

        Thread-safe: acquires _lock if not already held (RLock is reentrant).
        """
        with self._lock:
            if self.disk_conn:
                # Write to disk first (crash-safe)
                self.disk_conn.execute(sql, params)
                if not self._in_transaction:
                    self.disk_conn.commit()

                # Write to RAM second (failure is non-fatal)
                try:
                    self.read_conn.execute(sql, params)
                    if not self._in_transaction:
                        self.read_conn.commit()
                except Exception as e:
                    logger.warning(f"RAM write failed: {e}")
            else:
                # Single-write mode (disk only, no separate disk_conn)
                self.read_conn.execute(sql, params)
                if not self._in_transaction:
                    self.read_conn.commit()

    def _begin_transaction(self):
        """Begin transaction on both disk and RAM connections."""
        if self.disk_conn:
            self.disk_conn.execute("BEGIN")
        self.read_conn.execute("BEGIN")
        self._in_transaction = True

    def _commit_transaction(self):
        """Commit transaction on both connections."""
        try:
            if self.disk_conn:
                self.disk_conn.commit()
            self.read_conn.commit()
        finally:
            self._in_transaction = False

    def _rollback_transaction(self):
        """Rollback transaction on both connections."""
        try:
            if self.disk_conn:
                try:
                    self.disk_conn.rollback()
                except Exception as e:
                    logger.warning(f"Disk rollback failed: {e}")

            try:
                self.read_conn.rollback()
            except Exception as e:
                logger.warning(f"RAM rollback failed: {e}")
        finally:
            self._in_transaction = False

    # ============ NODE OPERATIONS ============

    def get_all_nodes(self, limit: int = 10000) -> List[Dict]:
        """Get all concept nodes with safety limit.

        Args:
            limit: Maximum number of nodes to return (default 10000).
                   Prevents unbounded memory consumption on large graphs.
        """
        cursor = self.read_conn.cursor()
        cursor.execute("SELECT * FROM nodes ORDER BY category, name LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_node_by_name(self, name: str) -> Optional[Dict]:
        """Get a node by name or node_id."""
        cursor = self.read_conn.cursor()
        cursor.execute(
            """
            SELECT * FROM nodes
            WHERE node_id = ? OR name = ? OR LOWER(name) = LOWER(?)
        """,
            (name, name, name),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def analyze_content(self, content: str, threshold: Optional[float] = None) -> List[Dict]:
        """Analyze content and return activated nodes.

        Enhanced with PRECOG ConceptExtractor (optional):
        - Extracts concepts using PRECOG's vocabulary-aware extraction
        - Boosts node scores when PRECOG concepts match node keywords
        - Adds 'precog_concepts' field to activation results
        """
        if threshold is None:
            threshold = Config.ACTIVATION_THRESHOLD

        nodes = self.get_all_nodes()
        activations = []
        content_lower = content.lower()

        # PRECOG Integration: Extract concepts for boosting
        precog_concepts = []
        precog_concepts_lower = set()
        if PRECOG_AVAILABLE:
            try:
                precog_concepts = extract_concepts(content, max_concepts=15)
                precog_concepts_lower = {c.lower().replace("_", " ") for c in precog_concepts}
                precog_concepts_lower.update({c.lower().replace("_", "") for c in precog_concepts})
            except Exception as e:
                print(f"[HEBBIAN-MIND] PRECOG extraction error: {e}", file=sys.stderr)

        for node in nodes:
            raw_keywords = node.get("keywords", [])
            keywords = json.loads(raw_keywords) if isinstance(raw_keywords, str) else raw_keywords
            raw_phrases = node.get("prototype_phrases", [])
            prototype_phrases = (
                json.loads(raw_phrases) if isinstance(raw_phrases, str) else raw_phrases
            )

            score = 0.0
            matched_keywords = []
            precog_boosted = False

            # Check keywords
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in content_lower:
                    if re.search(r"\b" + re.escape(keyword_lower) + r"\b", content_lower):
                        score += 0.25
                        matched_keywords.append(keyword)
                    else:
                        score += 0.1

                # PRECOG boost: If PRECOG extracted this concept, boost the score
                if precog_concepts_lower and keyword_lower in precog_concepts_lower:
                    score += 0.15  # PRECOG concept match bonus
                    precog_boosted = True
                    if f"[precog]{keyword}" not in matched_keywords:
                        matched_keywords.append(f"[precog]{keyword}")

            # Check prototype phrases (higher weight)
            for phrase in prototype_phrases:
                if phrase.lower() in content_lower:
                    score += 0.35
                    matched_keywords.append(f"[phrase]{phrase}")

            # Additional PRECOG boost: Check if node name matches PRECOG concepts
            node_name_lower = node["name"].lower().replace(" ", "_")
            node_name_nospace = node_name_lower.replace("_", "")
            if precog_concepts_lower:
                if (
                    node_name_lower in precog_concepts_lower
                    or node_name_nospace in precog_concepts_lower
                ):
                    if not precog_boosted:
                        score += 0.2  # Node name matched PRECOG concept
                        matched_keywords.append(f"[precog-node]{node['name']}")
                        precog_boosted = True

            score = min(score, 1.0)

            if score >= threshold:
                activations.append(
                    {
                        "node_id": node["id"],
                        "node_name": node["node_id"],
                        "name": node["name"],
                        "category": node["category"],
                        "score": score,
                        "matched_keywords": matched_keywords,
                        "precog_boosted": precog_boosted,
                    }
                )

        activations.sort(key=lambda x: x["score"], reverse=True)

        # Attach PRECOG concepts to result metadata (available via first activation or separately)
        if activations and precog_concepts:
            # Store precog_concepts in a way that can be retrieved
            activations[0]["precog_concepts"] = precog_concepts

        return activations

    # ============ MEMORY OPERATIONS ============

    def save_memory(
        self,
        memory_id: str,
        content: str,
        summary: str,
        source: str,
        activations: List[Dict],
        importance: float = 0.5,
        emotional_intensity: float = 0.5,
    ) -> bool:
        """Save a memory with all activations and edges in single transaction.

        Thread-safe: entire operation runs under _lock.

        Raises:
            RuntimeError: On failure, with details about what went wrong.
        """
        with self._lock:
            try:
                self._begin_transaction()

                now = time.time()
                # Insert memory (no OR REPLACE -- UUID prevents collisions,
                # and we must never silently overwrite existing memories)
                self._dual_write(
                    """
                    INSERT INTO memories
                    (memory_id, content, summary, source, importance, emotional_intensity,
                     last_accessed, effective_importance, access_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                    (
                        memory_id,
                        content,
                        summary,
                        source,
                        importance,
                        emotional_intensity,
                        now,
                        importance,
                    ),
                )

                # Record activations and update node counts
                for activation in activations:
                    self._dual_write(
                        """
                        INSERT INTO memory_activations (memory_id, node_id, activation_score)
                        VALUES (?, ?, ?)
                    """,
                        (memory_id, activation["node_id"], activation["score"]),
                    )

                    self._dual_write(
                        """
                        UPDATE nodes SET
                            activation_count = activation_count + 1,
                            last_activated = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """,
                        (activation["node_id"],),
                    )

                # Hebbian learning: strengthen edges between co-activated nodes
                node_ids = [a["node_id"] for a in activations]
                for i, source_id in enumerate(node_ids):
                    for target_id in node_ids[i + 1 :]:
                        self._strengthen_edge(source_id, target_id)

                # Homeostatic maintenance every N co-activations
                self._coactivation_count += 1
                if self._coactivation_count % HOMEOSTATIC_INTERVAL == 0:
                    self._apply_time_decay()
                    self._apply_homeostatic_scaling()

                self._commit_transaction()
                return True

            except Exception as e:
                logger.error(f"save_memory failed: {e}")
                self._rollback_transaction()
                raise RuntimeError(f"save_memory failed for memory_id={memory_id}: {e}") from e

    def _strengthen_edge(self, source_id: int, target_id: int):
        """Strengthen edge using asymptotic formula (anti-saturation)."""
        id1, id2 = min(source_id, target_id), max(source_id, target_id)

        cursor = self.read_conn.cursor()
        cursor.execute("SELECT weight FROM edges WHERE source_id = ? AND target_id = ?", (id1, id2))
        row = cursor.fetchone()

        now = time.time()

        if not row:
            self._dual_write(
                """
                INSERT INTO edges (source_id, target_id, weight, co_activation_count, last_strengthened, last_coactivated)
                VALUES (?, ?, 0.15, 1, ?, ?)
            """,
                (id1, id2, now, now),
            )
        else:
            current = row["weight"]

            # Asymptotic formula: delta approaches 0 as weight approaches MAX
            delta = (MAX_WEIGHT - current) * LEARNING_RATE

            # Clamp to [MIN_WEIGHT, MAX_WEIGHT]
            new_weight = max(MIN_WEIGHT, min(MAX_WEIGHT, current + delta))

            self._dual_write(
                """
                UPDATE edges SET
                    weight = ?,
                    co_activation_count = co_activation_count + 1,
                    last_strengthened = ?,
                    last_coactivated = ?
                WHERE source_id = ? AND target_id = ?
            """,
                (new_weight, now, now, id1, id2),
            )

    def _apply_time_decay(self):
        """Apply time-based decay to idle edges."""
        now = time.time()
        threshold_time = now - DECAY_IDLE_THRESHOLD

        # Find edges idle longer than threshold
        query = """
            SELECT id, weight, last_coactivated, last_strengthened
            FROM edges
            WHERE COALESCE(last_coactivated, last_strengthened, 0) < ?
              AND weight > ?
        """
        cursor = self.read_conn.execute(query, (threshold_time, MIN_WEIGHT))
        idle_edges = cursor.fetchall()

        for row in idle_edges:
            edge_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
            weight = row["weight"] if isinstance(row, sqlite3.Row) else row[1]

            # Decay by DECAY_IDLE_RATE (2% per tick)
            new_weight = max(MIN_WEIGHT, weight * (1.0 - DECAY_IDLE_RATE))

            self._dual_write("UPDATE edges SET weight = ? WHERE id = ?", (new_weight, edge_id))

    def _apply_homeostatic_scaling(self):
        """Apply homeostatic scaling to prevent saturation.

        Computes total edge weight per node bidirectionally (as both source and target),
        since all edges are stored with source_id = min(a,b), target_id = max(a,b).
        Scales all edges connected to over-target nodes in both directions.
        """
        query = """
            SELECT node_id, SUM(weight) as total_weight
            FROM (
                SELECT source_id AS node_id, weight FROM edges
                UNION ALL
                SELECT target_id AS node_id, weight FROM edges
            )
            GROUP BY node_id
            HAVING total_weight > ?
        """
        cursor = self.read_conn.execute(query, (TARGET_TOTAL_WEIGHT,))
        over_target_nodes = cursor.fetchall()

        for row in over_target_nodes:
            node_id = row["node_id"] if isinstance(row, sqlite3.Row) else row[0]
            total_weight = row["total_weight"] if isinstance(row, sqlite3.Row) else row[1]

            # Calculate scaling factor
            scale = 1.0 - SCALING_RATE * (total_weight - TARGET_TOTAL_WEIGHT) / total_weight

            # Clamp to [0.5, 2.0] safety range
            scale = max(0.5, min(2.0, scale))

            # Scale all edges connected to this node (both directions)
            self._dual_write(
                "UPDATE edges SET weight = weight * ? WHERE source_id = ? OR target_id = ?",
                (scale, node_id, node_id),
            )

    def query_by_nodes(
        self,
        node_names: List[str],
        limit: int = 20,
        include_decayed: bool = False,
    ) -> List[Dict]:
        """Query memories that activated specific nodes.

        Thread-safe: runs under _lock.

        Args:
            node_names: List of node names to query
            limit: Maximum results (clamped to 1-500)
            include_decayed: If True, include memories below decay threshold
        """
        # Clamp limit to safe range (H1 fix)
        limit = max(1, min(500, limit))

        with self._lock:
            cursor = self.read_conn.cursor()

            node_ids = []
            for name in node_names:
                node = self.get_node_by_name(name)
                if node:
                    node_ids.append(node["id"])

            if not node_ids:
                return []

            # Parameterized IN clause: placeholders are '?,?,?' with values bound safely
            placeholders = ",".join("?" * len(node_ids))

            # Build decay filter (static SQL fragment, threshold bound via params)
            decay_filter = ""
            decay_params: tuple = ()
            if not include_decayed and Config.DECAY_ENABLED:
                decay_filter = (
                    " AND (m.effective_importance IS NULL OR m.effective_importance >= ?)"
                )
                decay_params = (Config.DECAY_THRESHOLD,)

            cursor.execute(
                f"""
                SELECT DISTINCT m.*,
                       GROUP_CONCAT(n.name || ':' || ma.activation_score) as activations
                FROM memories m
                JOIN memory_activations ma ON m.memory_id = ma.memory_id
                JOIN nodes n ON ma.node_id = n.id
                WHERE ma.node_id IN ({placeholders})
                {decay_filter}
                GROUP BY m.id
                ORDER BY m.created_at DESC
                LIMIT ?
            """,
                (*node_ids, *decay_params, limit),
            )

            results = [dict(row) for row in cursor.fetchall()]

        # Touch accessed memories (fire-and-forget, outside lock)
        if results and hasattr(self, "_decay_engine") and self._decay_engine:
            memory_ids = [r["memory_id"] for r in results]
            try:
                self._decay_engine.touch_memories(memory_ids)
            except Exception:
                pass  # Non-critical

        return results

    def get_related_nodes(self, node_id: int, min_weight: float = 0.1) -> List[Dict]:
        """Get nodes connected via Hebbian edges."""
        cursor = self.read_conn.cursor()
        cursor.execute(
            """
            SELECT n.*, e.weight
            FROM edges e
            JOIN nodes n ON (e.target_id = n.id OR e.source_id = n.id)
            WHERE (e.source_id = ? OR e.target_id = ?)
              AND n.id != ?
              AND e.weight >= ?
            ORDER BY e.weight DESC
        """,
            (node_id, node_id, node_id, min_weight),
        )

        return [dict(row) for row in cursor.fetchall()]

    # ============ STATUS ============

    def get_status(self) -> Dict:
        """Get database status including dual-write info."""
        cursor = self.read_conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM nodes")
        node_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM edges")
        edge_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM memories")
        memory_count = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(activation_count) FROM nodes")
        total_activations = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT n1.name as source, n2.name as target, e.weight
            FROM edges e
            JOIN nodes n1 ON e.source_id = n1.id
            JOIN nodes n2 ON e.target_id = n2.id
            ORDER BY e.weight DESC
            LIMIT 10
        """)
        strongest_edges = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT name, activation_count
            FROM nodes
            ORDER BY activation_count DESC
            LIMIT 10
        """)
        most_active = [dict(row) for row in cursor.fetchall()]

        # Decay stats
        decay_stats = {}
        if hasattr(self, "_decay_engine") and self._decay_engine:
            decay_stats = self._decay_engine.get_decay_stats()

        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "memory_count": memory_count,
            "total_activations": total_activations,
            "strongest_edges": strongest_edges,
            "most_active_nodes": most_active,
            "dual_write": {
                "enabled": self.disk_conn is not None,
                "using_ram": self.using_ram,
                "ram_path": str(self.ram_path) if self.ram_path else None,
                "disk_path": str(self.disk_path),
            },
            "decay": decay_stats,
        }

    def close(self):
        """Close all connections."""
        if self.read_conn:
            self.read_conn.close()
        if self.disk_conn:
            self.disk_conn.close()
            print("[HEBBIAN-MIND] Closed both RAM and Disk connections", file=sys.stderr)


class FaissTetherBridge:
    """Bridge to external FAISS tether (optional integration)."""

    def __init__(self):
        self.host = Config.FAISS_TETHER_HOST
        self.port = Config.FAISS_TETHER_PORT
        self.enabled = Config.FAISS_TETHER_ENABLED

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.host, self.port))
            sock.close()
            return True
        except Exception:
            return False

    def search(self, query: str, top_k: int = 10) -> Dict:
        if not self.enabled:
            return {"status": "error", "message": "FAISS tether not enabled"}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.host, self.port))
            request = json.dumps({"cmd": "search", "query": query, "top_k": top_k})
            sock.sendall(request.encode("utf-8"))
            response = sock.recv(65536).decode("utf-8")
            sock.close()
            return json.loads(response)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def status(self) -> Dict:
        if not self.enabled:
            return {"status": "error", "message": "FAISS tether not enabled"}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.host, self.port))
            request = json.dumps({"cmd": "status"})
            sock.sendall(request.encode("utf-8"))
            response = sock.recv(16384).decode("utf-8")
            sock.close()
            return json.loads(response)
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Initialize database and tether bridge
db = HebbianMindDatabase()
tether = FaissTetherBridge()

# Initialize decay engine
decay_config = Config.get_decay_config()
decay_engine = HebbianDecayEngine(db, decay_config)
db._decay_engine = decay_engine  # Attach for access in query_by_nodes

# Create MCP server
server = Server("hebbian-mind")


@server.list_tools()
async def list_tools() -> List[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="save_to_mind",
            description="Save content to Hebbian Mind with automatic node activation and Hebbian edge strengthening.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to save"},
                    "summary": {"type": "string", "description": "Optional summary"},
                    "source": {
                        "type": "string",
                        "description": "Source identifier (default: HEBBIAN_MIND)",
                    },
                    "importance": {
                        "type": "number",
                        "description": "Importance 0-1 (default: 0.5)",
                    },
                    "emotional_intensity": {
                        "type": "number",
                        "description": "Emotional intensity 0-1 (default: 0.5)",
                    },
                },
                "required": ["content"],
            },
        ),
        types.Tool(
            name="query_mind",
            description="Query memories by concept nodes. Returns memories that activated specified concepts. Decayed memories are hidden by default.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of node names to query",
                    },
                    "limit": {"type": "number", "description": "Max results (default: 20)"},
                    "include_decayed": {
                        "type": "boolean",
                        "description": "Include decayed memories below threshold (default: false)",
                    },
                },
            },
        ),
        types.Tool(
            name="analyze_content",
            description="Analyze content against concept nodes without saving. Preview which concepts would activate.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to analyze"},
                    "threshold": {
                        "type": "number",
                        "description": "Activation threshold 0-1 (default: configured threshold)",
                    },
                },
                "required": ["content"],
            },
        ),
        types.Tool(
            name="get_related_nodes",
            description="Get nodes connected to a given node by Hebbian edges.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "Node name to find related nodes for",
                    },
                    "min_weight": {
                        "type": "number",
                        "description": "Minimum edge weight (default: 0.1)",
                    },
                },
                "required": ["node"],
            },
        ),
        types.Tool(
            name="mind_status",
            description="Get Hebbian Mind health status including node count, edge count, memory count, and strongest connections.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="list_nodes",
            description="List all concept nodes, optionally filtered by category.",
            inputSchema={
                "type": "object",
                "properties": {"category": {"type": "string", "description": "Filter by category"}},
            },
        ),
        types.Tool(
            name="faiss_search",
            description="Search external FAISS tether for semantic similarity search (if enabled).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "number", "description": "Number of results (default: 10)"},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="faiss_status",
            description="Check external FAISS tether status (if enabled).",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


def _validate_string(value: Any, name: str, max_length: int = 100000) -> str:
    """Validate and return a string parameter."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    if len(value) == 0:
        raise ValueError(f"{name} must not be empty")
    if len(value) > max_length:
        raise ValueError(f"{name} exceeds maximum length of {max_length}")
    return value


def _validate_number(
    value: Any, name: str, min_val: Optional[float] = None, max_val: Optional[float] = None
) -> float:
    """Validate and return a numeric parameter."""
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}")
    val = float(value)
    if min_val is not None and val < min_val:
        raise ValueError(f"{name} must be >= {min_val}, got {val}")
    if max_val is not None and val > max_val:
        raise ValueError(f"{name} must be <= {max_val}, got {val}")
    return val


@server.call_tool()
async def call_tool(name: str, arguments: Dict) -> List[types.TextContent]:
    """Handle tool calls with input validation."""

    try:
        if name == "save_to_mind":
            content = _validate_string(arguments.get("content", ""), "content")
            summary = arguments.get("summary", "")
            if summary:
                summary = _validate_string(summary, "summary", max_length=10000)
            source = arguments.get("source", "HEBBIAN_MIND")
            if source:
                source = _validate_string(source, "source", max_length=200)
            importance = _validate_number(arguments.get("importance", 0.5), "importance", 0.0, 1.0)
            emotional_intensity = _validate_number(
                arguments.get("emotional_intensity", 0.5), "emotional_intensity", 0.0, 1.0
            )

            activations = db.analyze_content(content)

            if not activations:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "success": False,
                                "message": "No concept nodes activated above threshold",
                                "threshold": Config.ACTIVATION_THRESHOLD,
                            },
                            indent=2,
                        ),
                    )
                ]

            memory_id = f"hebbian_mind_{uuid.uuid4().hex[:16]}"

            if not summary:
                top_nodes = [a["name"] for a in activations[:5]]
                summary = f"Activated {len(activations)} concepts: {', '.join(top_nodes)}"

            try:
                db.save_memory(
                    memory_id,
                    content,
                    summary,
                    source,
                    activations,
                    importance,
                    emotional_intensity,
                )
                success = True
            except RuntimeError as save_err:
                logger.error(f"save_to_mind: {save_err}")
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "success": False,
                                "error": sanitize_error_message(save_err),
                            },
                            indent=2,
                        ),
                    )
                ]

            # Extract PRECOG concepts from first activation if present
            precog_concepts = activations[0].get("precog_concepts", []) if activations else []
            precog_boosted_count = sum(1 for a in activations if a.get("precog_boosted", False))

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": success,
                            "memory_id": memory_id,
                            "dual_write": db.disk_conn is not None,
                            "precog_available": PRECOG_AVAILABLE,
                            "precog_concepts": precog_concepts,
                            "precog_boosted_nodes": precog_boosted_count,
                            "activations": [
                                {
                                    "node": a["node_name"],
                                    "name": a["name"],
                                    "category": a["category"],
                                    "score": round(a["score"], 3),
                                    "precog_boosted": a.get("precog_boosted", False),
                                }
                                for a in activations
                            ],
                            "edges_strengthened": (len(activations) * (len(activations) - 1)) // 2,
                            "summary": summary,
                        },
                        indent=2,
                    ),
                )
            ]

        elif name == "query_mind":
            nodes = arguments.get("nodes", [])
            if not isinstance(nodes, list):
                raise ValueError("nodes must be a list of strings")
            if len(nodes) > 100:
                raise ValueError("nodes list exceeds maximum of 100 items")
            for n in nodes:
                if not isinstance(n, str):
                    raise ValueError("each node must be a string")
            limit = int(_validate_number(arguments.get("limit", 20), "limit", 1, 500))
            include_decayed = bool(arguments.get("include_decayed", False))

            if not nodes:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {"success": False, "message": "No nodes specified"}, indent=2
                        ),
                    )
                ]

            memories = db.query_by_nodes(nodes, limit, include_decayed=include_decayed)

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "queried_nodes": nodes,
                            "memories_found": len(memories),
                            "memories": [
                                {
                                    "memory_id": m["memory_id"],
                                    "summary": m["summary"],
                                    "source": m["source"],
                                    "activations": m.get("activations", ""),
                                    "created_at": m["created_at"],
                                }
                                for m in memories
                            ],
                        },
                        indent=2,
                    ),
                )
            ]

        elif name == "analyze_content":
            content = _validate_string(arguments.get("content", ""), "content")
            threshold = arguments.get("threshold")
            if threshold is not None:
                threshold = _validate_number(threshold, "threshold", 0.0, 1.0)

            activations = db.analyze_content(content, threshold)

            # Extract PRECOG concepts from first activation if present
            precog_concepts = activations[0].get("precog_concepts", []) if activations else []

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "threshold": threshold if threshold else Config.ACTIVATION_THRESHOLD,
                            "activated_count": len(activations),
                            "precog_available": PRECOG_AVAILABLE,
                            "precog_concepts": precog_concepts,
                            "activations": [
                                {
                                    "node": a["node_name"],
                                    "name": a["name"],
                                    "category": a["category"],
                                    "score": round(a["score"], 3),
                                    "matched_keywords": a["matched_keywords"],
                                    "precog_boosted": a.get("precog_boosted", False),
                                }
                                for a in activations
                            ],
                        },
                        indent=2,
                    ),
                )
            ]

        elif name == "get_related_nodes":
            node_name = _validate_string(arguments.get("node", ""), "node", max_length=500)
            min_weight = _validate_number(arguments.get("min_weight", 0.1), "min_weight", 0.0, 10.0)

            node = db.get_node_by_name(node_name)
            if not node:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {"success": False, "message": f"Node not found: {node_name}"}, indent=2
                        ),
                    )
                ]

            related = db.get_related_nodes(node["id"], min_weight)

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "source_node": node["name"],
                            "related_count": len(related),
                            "related_nodes": [
                                {
                                    "name": r["name"],
                                    "category": r["category"],
                                    "weight": round(r["weight"], 3),
                                }
                                for r in related
                            ],
                        },
                        indent=2,
                    ),
                )
            ]

        elif name == "mind_status":
            status = db.get_status()
            faiss_available = tether.is_available()

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "version": "2.3.1",
                            "status": "operational",
                            "statistics": {
                                "node_count": status["node_count"],
                                "edge_count": status["edge_count"],
                                "memory_count": status["memory_count"],
                                "total_activations": status["total_activations"],
                            },
                            "dual_write": status["dual_write"],
                            "decay": {
                                "engine": decay_engine.get_status(),
                                "stats": status.get("decay", {}),
                            },
                            "precog_integration": {
                                "available": PRECOG_AVAILABLE,
                                "path": str(Config.PRECOG_PATH) if Config.PRECOG_PATH else None,
                                "boost_keywords": 0.15,
                                "boost_node_name": 0.20,
                            },
                            "faiss_tether": {
                                "enabled": Config.FAISS_TETHER_ENABLED,
                                "host": (
                                    Config.FAISS_TETHER_HOST
                                    if Config.FAISS_TETHER_ENABLED
                                    else None
                                ),
                                "port": (
                                    Config.FAISS_TETHER_PORT
                                    if Config.FAISS_TETHER_ENABLED
                                    else None
                                ),
                                "status": "connected" if faiss_available else "offline",
                            },
                            "strongest_connections": status["strongest_edges"][:5],
                            "most_active_nodes": status["most_active_nodes"][:5],
                            "hebbian_principle": "Neurons that fire together, wire together",
                        },
                        indent=2,
                    ),
                )
            ]

        elif name == "list_nodes":
            category = arguments.get("category")
            nodes = db.get_all_nodes()

            if category:
                nodes = [n for n in nodes if n["category"] == category]

            by_category: Dict[str, List[Dict[str, Any]]] = {}
            for node in nodes:
                cat = node["category"]
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(
                    {
                        "node_id": node["node_id"],
                        "name": node["name"],
                        "activation_count": node["activation_count"],
                    }
                )

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {"success": True, "total_nodes": len(nodes), "categories": by_category},
                        indent=2,
                    ),
                )
            ]

        elif name == "faiss_search":
            query = _validate_string(arguments.get("query", ""), "query")
            top_k = int(_validate_number(arguments.get("top_k", 10), "top_k", 1, 100))

            if not tether.is_available():
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "success": False,
                                "message": f"FAISS tether not available (enabled: {Config.FAISS_TETHER_ENABLED})",
                                "suggestion": "Enable and start the FAISS tether",
                            },
                            indent=2,
                        ),
                    )
                ]

            result = tether.search(query, top_k)

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": result.get("status") != "error",
                            "query": query,
                            "results": result.get("results", []),
                            "count": result.get("count", 0),
                        },
                        indent=2,
                    ),
                )
            ]

        elif name == "faiss_status":
            if not tether.is_available():
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "success": False,
                                "status": "offline",
                                "enabled": Config.FAISS_TETHER_ENABLED,
                                "host": Config.FAISS_TETHER_HOST,
                                "port": Config.FAISS_TETHER_PORT,
                            },
                            indent=2,
                        ),
                    )
                ]

            status = tether.status()

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "status": "connected",
                            "host": Config.FAISS_TETHER_HOST,
                            "port": Config.FAISS_TETHER_PORT,
                            "tether_info": status,
                        },
                        indent=2,
                    ),
                )
            ]

        else:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {"success": False, "message": f"Unknown tool: {name}"}, indent=2
                    ),
                )
            ]

    except Exception as e:
        # Sanitize error to prevent internal path leakage to customers
        safe_error = sanitize_error_message(e)
        return [
            types.TextContent(
                type="text", text=json.dumps({"success": False, "error": safe_error}, indent=2)
            )
        ]


async def run_stdio_server():
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


async def run_standalone():
    """Run in standalone mode - keeps container alive for health checks.

    MCP stdio servers need stdin/stdout for communication, but Docker
    containers without TTY have no stdin. This mode keeps the container
    running so health checks pass, while still initializing the database.

    When an MCP client connects (e.g., via docker exec or SSE bridge),
    they spawn a new process with proper stdio.
    """
    print("[HEBBIAN-MIND] Running in standalone mode (container keep-alive)", file=sys.stderr)
    print("[HEBBIAN-MIND] Database initialized and ready", file=sys.stderr)
    print("[HEBBIAN-MIND] For MCP access, connect via SSE bridge or docker exec", file=sys.stderr)

    # Keep the container alive
    while True:
        await asyncio.sleep(3600)  # Sleep for 1 hour, repeat forever


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Hebbian Mind Enterprise MCP Server")
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Run in standalone mode (for Docker containers without TTY)",
    )
    args = parser.parse_args()

    print("[HEBBIAN-MIND] Hebbian Mind Enterprise v2.3.1 starting", file=sys.stderr)
    print(
        f"[HEBBIAN-MIND] Database (read): {db.ram_path if db.using_ram else db.disk_path}",
        file=sys.stderr,
    )
    print(f"[HEBBIAN-MIND] Database (write): {db.disk_path}", file=sys.stderr)
    print(
        f"[HEBBIAN-MIND] Dual-write: {'ENABLED' if db.disk_conn else 'DISABLED'}", file=sys.stderr
    )

    # Decay engine
    dc = Config.get_decay_config()
    if dc["enabled"] or dc["edge_decay_enabled"]:
        parts = []
        if dc["enabled"]:
            parts.append(f"memory(rate={dc['base_rate']})")
        if dc["edge_decay_enabled"]:
            parts.append(f"edge(rate={dc['edge_decay_rate']})")
        print(
            f"[HEBBIAN-MIND] Decay: {', '.join(parts)}, sweep every {dc['sweep_interval_minutes']}m",
            file=sys.stderr,
        )
    else:
        print("[HEBBIAN-MIND] Decay: DISABLED", file=sys.stderr)

    if Config.FAISS_TETHER_ENABLED:
        print(
            f"[HEBBIAN-MIND] FAISS tether: {Config.FAISS_TETHER_HOST}:{Config.FAISS_TETHER_PORT}",
            file=sys.stderr,
        )

    # Start decay engine
    decay_engine.start()

    try:
        if args.standalone:
            await run_standalone()
        else:
            await run_stdio_server()
    finally:
        decay_engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
