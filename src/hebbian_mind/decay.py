"""
Temporal Decay Engine for Hebbian Mind Enterprise
==================================================

Implements exponential decay for both memories and Hebbian edges.

Memory Decay:
  effective_importance = importance * e^(-decay_rate * days_since_access)
  - Memories with importance >= immortal_threshold never decay
  - decay_rate = base_rate * (1 - importance), so important memories decay slower
  - Memories below decay_threshold are considered "decayed" and hidden by default

Edge Decay:
  effective_weight = max(min_weight, weight * e^(-edge_decay_rate * days_since_strengthened))
  - Edges decay toward min_weight (0.1), never to zero
  - Edges at or below min_weight don't decay further
  - Separate rate from memory decay (default 0.005 vs 0.01)

Copyright (c) 2026 CIPS LLC
All rights reserved.
"""

import math
import time
import logging
import threading
from typing import Optional

logger = logging.getLogger("hebbian-mind")


def calculate_effective_importance(
    importance: float,
    last_accessed: float,
    now: float,
    config: dict,
) -> float:
    """Calculate effective importance after temporal decay.

    Args:
        importance: Original importance value (0-1)
        last_accessed: Unix timestamp of last access
        now: Current unix timestamp
        config: Decay config dict with keys:
            - immortal_threshold (float): Importance >= this never decays
            - base_rate (float): Base decay rate
            - threshold (float): Below this, memory is "decayed"

    Returns:
        Effective importance after decay
    """
    if importance >= config["immortal_threshold"]:
        return importance

    days_since_access = (now - last_accessed) / 86400.0
    if days_since_access <= 0:
        return importance

    # Higher importance = slower decay
    decay_rate = config["base_rate"] * (1.0 - importance)
    decay_factor = math.exp(-decay_rate * days_since_access)
    return importance * decay_factor


def calculate_edge_decay(
    weight: float,
    last_strengthened: float,
    now: float,
    config: dict,
) -> float:
    """Calculate effective edge weight after temporal decay.

    Args:
        weight: Current edge weight
        last_strengthened: Unix timestamp of last co-activation
        now: Current unix timestamp
        config: Decay config dict with keys:
            - edge_decay_rate (float): Decay rate for edges
            - edge_decay_min_weight (float): Minimum weight (default 0.1)

    Returns:
        Effective edge weight after decay (never below min_weight)
    """
    min_weight = config["edge_decay_min_weight"]

    if weight <= min_weight:
        return weight

    days_since_strengthened = (now - last_strengthened) / 86400.0
    if days_since_strengthened <= 0:
        return weight

    # Decay the portion above min_weight
    above_min = weight - min_weight
    decay_factor = math.exp(-config["edge_decay_rate"] * days_since_strengthened)
    decayed_above = above_min * decay_factor

    return min_weight + decayed_above


class HebbianDecayEngine:
    """Manages temporal decay for memories and edges in Hebbian Mind.

    Runs periodic sweeps to recalculate effective_importance for memories
    and apply weight decay to edges.
    """

    def __init__(self, db, config: dict):
        """Initialize the decay engine.

        Args:
            db: HebbianMindDatabase instance (module-level global)
            config: Decay config dict from Config.get_decay_config()
        """
        self.db = db
        self.config = config
        self._timer: Optional[threading.Timer] = None
        self._running = False
        self._sweep_count = 0
        self._last_sweep_time: Optional[float] = None
        self._last_sweep_stats: Optional[dict] = None

    def start(self):
        """Start the periodic decay sweep timer."""
        if not self.config["enabled"] and not self.config["edge_decay_enabled"]:
            logger.info("[DECAY] Both memory and edge decay disabled, not starting")
            return

        self._running = True
        interval_seconds = self.config["sweep_interval_minutes"] * 60
        self._schedule_sweep(interval_seconds)

        enabled_parts = []
        if self.config["enabled"]:
            enabled_parts.append("memory")
        if self.config["edge_decay_enabled"]:
            enabled_parts.append("edge")
        logger.info(
            f"[DECAY] Started ({', '.join(enabled_parts)} decay), "
            f"sweep every {self.config['sweep_interval_minutes']}m"
        )

    def stop(self):
        """Stop the periodic decay sweep timer."""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        logger.info("[DECAY] Stopped")

    def _schedule_sweep(self, interval_seconds: float):
        """Schedule the next sweep."""
        if not self._running:
            return
        self._timer = threading.Timer(interval_seconds, self._sweep_tick)
        self._timer.daemon = True
        self._timer.start()

    def _sweep_tick(self):
        """Timer callback - run sweep and reschedule."""
        if not self._running:
            return
        try:
            self.run_sweep()
        except Exception as e:
            logger.error(f"[DECAY] Sweep failed: {e}")
        finally:
            if self._running:
                interval_seconds = self.config["sweep_interval_minutes"] * 60
                self._schedule_sweep(interval_seconds)

    def run_sweep(self) -> dict:
        """Run a full decay sweep on memories and edges.

        Returns:
            Dict with sweep statistics
        """
        now = time.time()
        stats = {
            "timestamp": now,
            "memories_swept": 0,
            "memories_decayed": 0,
            "memories_immortal": 0,
            "edges_swept": 0,
            "edges_decayed": 0,
        }

        if self.config["enabled"]:
            mem_stats = self._sweep_memories(now)
            stats.update(mem_stats)

        if self.config["edge_decay_enabled"]:
            edge_stats = self._sweep_edges(now)
            stats.update(edge_stats)

        self._sweep_count += 1
        self._last_sweep_time = now
        self._last_sweep_stats = stats

        logger.info(
            f"[DECAY] Sweep #{self._sweep_count}: "
            f"{stats['memories_swept']} memories ({stats['memories_decayed']} decayed, "
            f"{stats['memories_immortal']} immortal), "
            f"{stats['edges_swept']} edges ({stats['edges_decayed']} decayed)"
        )

        return stats

    def _sweep_memories(self, now: float) -> dict:
        """Sweep all memories and recalculate effective_importance.

        Args:
            now: Current unix timestamp

        Returns:
            Dict with memory sweep stats
        """
        stats = {
            "memories_swept": 0,
            "memories_decayed": 0,
            "memories_immortal": 0,
        }

        conn = self.db.read_conn
        disk_conn = self.db.disk_conn

        cursor = conn.cursor()
        cursor.execute("""
            SELECT memory_id, importance, last_accessed, effective_importance
            FROM memories
            WHERE last_accessed IS NOT NULL
        """)
        rows = cursor.fetchall()

        for row in rows:
            memory_id = row["memory_id"]
            importance = row["importance"]
            last_accessed = row["last_accessed"]

            if importance >= self.config["immortal_threshold"]:
                stats["memories_immortal"] += 1
                stats["memories_swept"] += 1
                continue

            new_effective = calculate_effective_importance(
                importance, last_accessed, now, self.config
            )

            # Only update if value changed meaningfully (avoid unnecessary writes)
            old_effective = row["effective_importance"]
            if old_effective is not None and abs(new_effective - old_effective) < 0.0001:
                stats["memories_swept"] += 1
                continue

            # Dual-write: disk first (crash-safe truth), then RAM
            if disk_conn:
                try:
                    disk_conn.execute(
                        "UPDATE memories SET effective_importance = ? WHERE memory_id = ?",
                        (new_effective, memory_id),
                    )
                except Exception as e:
                    logger.warning(f"[DECAY] Disk write failed for memory {memory_id}: {e}")

            conn.execute(
                "UPDATE memories SET effective_importance = ? WHERE memory_id = ?",
                (new_effective, memory_id),
            )

            if new_effective < self.config["threshold"]:
                stats["memories_decayed"] += 1

            stats["memories_swept"] += 1

        # Commit disk first, then RAM
        if disk_conn:
            try:
                disk_conn.commit()
            except Exception:
                pass
        conn.commit()

        return stats

    def _sweep_edges(self, now: float) -> dict:
        """Sweep all edges and apply weight decay.

        Args:
            now: Current unix timestamp

        Returns:
            Dict with edge sweep stats
        """
        stats = {
            "edges_swept": 0,
            "edges_decayed": 0,
        }

        conn = self.db.read_conn
        disk_conn = self.db.disk_conn
        min_weight = self.config["edge_decay_min_weight"]

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, source_id, target_id, weight, last_strengthened
            FROM edges
            WHERE weight > ? AND last_strengthened IS NOT NULL
        """,
            (min_weight,),
        )
        rows = cursor.fetchall()

        for row in rows:
            edge_id = row["id"]
            weight = row["weight"]
            last_strengthened_str = row["last_strengthened"]

            # Convert timestamp string to epoch
            try:
                last_strengthened = self._parse_timestamp(last_strengthened_str)
            except (ValueError, TypeError):
                stats["edges_swept"] += 1
                continue

            new_weight = calculate_edge_decay(weight, last_strengthened, now, self.config)

            # Only update if weight changed meaningfully
            if abs(new_weight - weight) < 0.0001:
                stats["edges_swept"] += 1
                continue

            # Dual-write: disk first (crash-safe truth), then RAM
            if disk_conn:
                try:
                    disk_conn.execute(
                        "UPDATE edges SET weight = ? WHERE id = ?",
                        (new_weight, edge_id),
                    )
                except Exception as e:
                    logger.warning(f"[DECAY] Disk write failed for edge {edge_id}: {e}")

            conn.execute(
                "UPDATE edges SET weight = ? WHERE id = ?",
                (new_weight, edge_id),
            )

            if new_weight <= min_weight + 0.0001:
                stats["edges_decayed"] += 1

            stats["edges_swept"] += 1

        # Commit disk first, then RAM
        if disk_conn:
            try:
                disk_conn.commit()
            except Exception:
                pass
        conn.commit()

        return stats

    def _parse_timestamp(self, ts) -> float:
        """Parse a timestamp value to epoch seconds.

        Handles:
        - float/int (already epoch)
        - string epoch
        - ISO format / SQLite CURRENT_TIMESTAMP format
        """
        if ts is None:
            raise ValueError("Timestamp is None")

        if isinstance(ts, (int, float)):
            return float(ts)

        ts_str = str(ts).strip()

        # Try as numeric epoch
        try:
            return float(ts_str)
        except ValueError:
            pass

        # Try SQLite CURRENT_TIMESTAMP format: "YYYY-MM-DD HH:MM:SS"
        from datetime import datetime

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                dt = datetime.strptime(ts_str, fmt)
                return dt.timestamp()
            except ValueError:
                continue

        raise ValueError(f"Cannot parse timestamp: {ts_str}")

    def touch_memories(self, memory_ids: list):
        """Update last_accessed and access_count for queried memories.

        Thread-safe: acquires db._lock to prevent concurrent modification.

        Args:
            memory_ids: List of memory_id strings to touch
        """
        if not memory_ids:
            return

        now = time.time()
        conn = self.db.read_conn
        disk_conn = self.db.disk_conn

        with self.db._lock:
            for memory_id in memory_ids:
                # Disk first (crash-safe truth), then RAM
                if disk_conn:
                    try:
                        disk_conn.execute(
                            """UPDATE memories SET
                                last_accessed = ?,
                                access_count = COALESCE(access_count, 0) + 1
                            WHERE memory_id = ?""",
                            (now, memory_id),
                        )
                    except Exception as e:
                        logger.warning(f"[DECAY] Disk touch failed for {memory_id}: {e}")

                conn.execute(
                    """UPDATE memories SET
                        last_accessed = ?,
                        access_count = COALESCE(access_count, 0) + 1
                    WHERE memory_id = ?""",
                    (now, memory_id),
                )

            # Commit disk first, then RAM
            if disk_conn:
                try:
                    disk_conn.commit()
                except Exception:
                    pass
            conn.commit()

    def get_status(self) -> dict:
        """Return decay engine status."""
        return {
            "memory_decay_enabled": self.config["enabled"],
            "edge_decay_enabled": self.config["edge_decay_enabled"],
            "running": self._running,
            "sweep_count": self._sweep_count,
            "last_sweep_time": self._last_sweep_time,
            "sweep_interval_minutes": self.config["sweep_interval_minutes"],
            "config": {
                "base_rate": self.config["base_rate"],
                "threshold": self.config["threshold"],
                "immortal_threshold": self.config["immortal_threshold"],
                "edge_decay_rate": self.config["edge_decay_rate"],
                "edge_decay_min_weight": self.config["edge_decay_min_weight"],
            },
        }

    def get_decay_stats(self) -> dict:
        """Return decay statistics from the database.

        Returns:
            Dict with counts of immortal, active, and decayed memories,
            plus edge weight distribution.
        """
        conn = self.db.read_conn
        cursor = conn.cursor()

        # Memory stats
        cursor.execute("SELECT COUNT(*) FROM memories")
        total_memories = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM memories WHERE importance >= ?",
            (self.config["immortal_threshold"],),
        )
        immortal_count = cursor.fetchone()[0]

        cursor.execute(
            """SELECT COUNT(*) FROM memories
            WHERE effective_importance IS NOT NULL
              AND effective_importance < ?
              AND importance < ?""",
            (self.config["threshold"], self.config["immortal_threshold"]),
        )
        decayed_count = cursor.fetchone()[0]

        active_count = total_memories - immortal_count - decayed_count

        # Edge stats
        min_weight = self.config["edge_decay_min_weight"]
        cursor.execute("SELECT COUNT(*) FROM edges")
        total_edges = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM edges WHERE weight <= ?",
            (min_weight + 0.0001,),
        )
        edges_at_min = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(weight) FROM edges")
        avg_edge_weight_row = cursor.fetchone()[0]
        avg_edge_weight = round(avg_edge_weight_row, 4) if avg_edge_weight_row else 0.0

        return {
            "memories": {
                "total": total_memories,
                "immortal": immortal_count,
                "active": active_count,
                "decayed": decayed_count,
            },
            "edges": {
                "total": total_edges,
                "at_minimum_weight": edges_at_min,
                "above_minimum": total_edges - edges_at_min,
                "average_weight": avg_edge_weight,
            },
            "last_sweep": self._last_sweep_stats,
        }
