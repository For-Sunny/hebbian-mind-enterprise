"""
Pytest configuration and fixtures for Hebbian Mind Enterprise tests

Copyright (c) 2026 CIPS LLC
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Dict, Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_config(temp_dir: Path) -> Dict:
    """Provide test configuration with temporary paths."""
    return {
        "base_dir": temp_dir,
        "disk_data_dir": temp_dir / "disk",
        "disk_db_path": temp_dir / "disk" / "hebbian_mind.db",
        "disk_nodes_path": temp_dir / "disk" / "nodes_v2.json",
        "ram_data_dir": temp_dir / "ram",
        "ram_db_path": temp_dir / "ram" / "hebbian_mind.db",
        "ram_enabled": False,  # Default to disk-only for tests
        "faiss_enabled": False,
        "precog_enabled": False,
        "activation_threshold": 0.3,
        "edge_strengthening_factor": 1.0,
        "max_edge_weight": 10.0,
    }


@pytest.fixture
def mock_config(test_config: Dict):
    """Mock the Config class with test configuration."""
    with patch("hebbian_mind.config.Config") as mock:
        # Set class attributes
        mock.BASE_DIR = test_config["base_dir"]
        mock.DISK_DATA_DIR = test_config["disk_data_dir"]
        mock.DISK_DB_PATH = test_config["disk_db_path"]
        mock.DISK_NODES_PATH = test_config["disk_nodes_path"]
        mock.RAM_DISK_ENABLED = test_config["ram_enabled"]
        mock.RAM_DATA_DIR = test_config["ram_data_dir"]
        mock.RAM_DB_PATH = test_config["ram_db_path"]
        mock.FAISS_TETHER_ENABLED = test_config["faiss_enabled"]
        mock.PRECOG_ENABLED = test_config["precog_enabled"]
        mock.ACTIVATION_THRESHOLD = test_config["activation_threshold"]
        mock.EDGE_STRENGTHENING_FACTOR = test_config["edge_strengthening_factor"]
        mock.MAX_EDGE_WEIGHT = test_config["max_edge_weight"]
        mock.ensure_directories.return_value = None
        mock.check_ram_available.return_value = test_config["ram_enabled"]
        mock.summary.return_value = test_config
        yield mock


@pytest.fixture
def sample_nodes() -> list:
    """Provide sample test nodes."""
    return [
        {
            "id": "node_1",
            "name": "Test Concept",
            "category": "test",
            "keywords": ["test", "example", "sample"],
            "prototype_phrases": ["this is a test", "example phrase"],
            "description": "Test node for unit tests",
            "weight": 1.0,
        },
        {
            "id": "node_2",
            "name": "Related Concept",
            "category": "test",
            "keywords": ["related", "connected", "linked"],
            "prototype_phrases": ["related concept", "connected idea"],
            "description": "Related test node",
            "weight": 1.0,
        },
        {
            "id": "node_3",
            "name": "Other Category",
            "category": "other",
            "keywords": ["different", "separate"],
            "prototype_phrases": ["other category"],
            "description": "Node in different category",
            "weight": 1.0,
        },
    ]


@pytest.fixture
def nodes_file(test_config: Dict, sample_nodes: list) -> Path:
    """Create a nodes.json file for testing."""
    disk_dir = test_config["disk_data_dir"]
    disk_dir.mkdir(parents=True, exist_ok=True)

    nodes_path = test_config["disk_nodes_path"]
    with open(nodes_path, "w", encoding="utf-8") as f:
        json.dump({"nodes": sample_nodes}, f, indent=2)

    return nodes_path


@pytest.fixture
def test_db(test_config: Dict) -> Generator[sqlite3.Connection, None, None]:
    """Provide a test database connection."""
    disk_dir = test_config["disk_data_dir"]
    disk_dir.mkdir(parents=True, exist_ok=True)

    db_path = test_config["disk_db_path"]
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Create schema
    conn.executescript("""
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
            FOREIGN KEY (source_id) REFERENCES nodes(id),
            FOREIGN KEY (target_id) REFERENCES nodes(id),
            UNIQUE(source_id, target_id)
        );

        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            summary TEXT,
            source TEXT DEFAULT 'TEST',
            frequency REAL DEFAULT 1.0,
            importance REAL DEFAULT 0.5,
            emotional_intensity REAL DEFAULT 0.5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source);
    """)
    conn.commit()

    yield conn

    conn.close()


@pytest.fixture
def populated_db(test_db: sqlite3.Connection, sample_nodes: list) -> sqlite3.Connection:
    """Provide a database populated with test nodes."""
    for node in sample_nodes:
        test_db.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases, description, weight)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            node["id"],
            node["name"],
            node["category"],
            json.dumps(node["keywords"]),
            json.dumps(node["prototype_phrases"]),
            node["description"],
            node["weight"],
        ))

    test_db.commit()
    return test_db


@pytest.fixture
def mock_faiss_tether():
    """Mock FAISS tether for testing."""
    mock = MagicMock()
    mock.is_available.return_value = True
    mock.search.return_value = {
        "status": "success",
        "results": [
            {"content": "Test memory 1", "score": 0.95},
            {"content": "Test memory 2", "score": 0.87},
        ],
        "count": 2,
    }
    mock.status.return_value = {
        "status": "operational",
        "memory_count": 100,
        "index_dimension": 384,
    }
    return mock


@pytest.fixture
def mock_precog():
    """Mock PRECOG concept extractor for testing."""
    mock = MagicMock()
    mock.extract_concepts.return_value = [
        "test_concept",
        "example_phrase",
        "related_idea",
    ]
    return mock


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment variables before each test."""
    # Store original values
    original_env = os.environ.copy()

    # Clear Hebbian Mind related env vars
    env_vars = [
        "HEBBIAN_MIND_BASE_DIR",
        "HEBBIAN_MIND_RAM_DISK",
        "HEBBIAN_MIND_RAM_DIR",
        "HEBBIAN_MIND_FAISS_ENABLED",
        "HEBBIAN_MIND_FAISS_HOST",
        "HEBBIAN_MIND_FAISS_PORT",
        "HEBBIAN_MIND_PRECOG_ENABLED",
        "HEBBIAN_MIND_PRECOG_PATH",
        "HEBBIAN_MIND_THRESHOLD",
        "HEBBIAN_MIND_EDGE_FACTOR",
        "HEBBIAN_MIND_MAX_WEIGHT",
        "HEBBIAN_MIND_LOG_LEVEL",
    ]

    for var in env_vars:
        os.environ.pop(var, None)

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "requires_ram: marks tests that require RAM disk"
    )
    config.addinivalue_line(
        "markers", "requires_faiss: marks tests that require FAISS tether"
    )
    config.addinivalue_line(
        "markers", "requires_precog: marks tests that require PRECOG"
    )
