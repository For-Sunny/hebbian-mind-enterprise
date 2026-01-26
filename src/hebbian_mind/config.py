"""
Configuration management for Hebbian Mind Enterprise
All paths are configurable via environment variables

Copyright (c) 2026 CIPS LLC
"""

import os
import platform
from pathlib import Path
from typing import Optional


def _get_default_ram_dir() -> Optional[Path]:
    """Get platform-appropriate RAM disk default.
    
    Returns:
        Path to RAM disk directory on Linux (if /dev/shm exists),
        None on Windows and macOS (require explicit configuration).
    """
    system = platform.system()
    
    if system == "Linux" and Path("/dev/shm").exists():
        return Path("/dev/shm/hebbian_mind")
    # Windows and macOS require explicit configuration via HEBBIAN_MIND_RAM_DIR
    return None


class Config:
    """Centralized configuration for Hebbian Mind"""

    # Base directory for data storage
    BASE_DIR: Path = Path(os.getenv("HEBBIAN_MIND_BASE_DIR", "./hebbian_mind_data"))

    # Disk storage paths (source of truth)
    DISK_DATA_DIR: Path = BASE_DIR / "disk"
    DISK_DB_PATH: Path = DISK_DATA_DIR / "hebbian_mind.db"
    DISK_NODES_PATH: Path = DISK_DATA_DIR / "nodes_v2.json"

    # RAM disk paths (optional high-performance layer)
    RAM_DISK_ENABLED: bool = os.getenv("HEBBIAN_MIND_RAM_DISK", "false").lower() == "true"
    RAM_DATA_DIR: Optional[Path] = (
        Path(os.getenv("HEBBIAN_MIND_RAM_DIR")) if os.getenv("HEBBIAN_MIND_RAM_DIR")
        else _get_default_ram_dir()
    ) if RAM_DISK_ENABLED else None
    RAM_DB_PATH: Optional[Path] = (
        RAM_DATA_DIR / "hebbian_mind.db" if RAM_DATA_DIR else None
    )

    # FAISS tether integration (optional)
    FAISS_TETHER_ENABLED: bool = (
        os.getenv("HEBBIAN_MIND_FAISS_ENABLED", "false").lower() == "true"
    )
    FAISS_TETHER_HOST: str = os.getenv("HEBBIAN_MIND_FAISS_HOST", "localhost")
    FAISS_TETHER_PORT: int = int(os.getenv("HEBBIAN_MIND_FAISS_PORT", "9998"))

    # PRECOG concept extractor integration (optional)
    PRECOG_ENABLED: bool = os.getenv("HEBBIAN_MIND_PRECOG_ENABLED", "false").lower() == "true"
    PRECOG_PATH: Optional[Path] = (
        Path(os.getenv("HEBBIAN_MIND_PRECOG_PATH"))
        if os.getenv("HEBBIAN_MIND_PRECOG_PATH")
        else None
    )

    # Hebbian learning parameters
    ACTIVATION_THRESHOLD: float = float(os.getenv("HEBBIAN_MIND_THRESHOLD", "0.3"))
    EDGE_STRENGTHENING_FACTOR: float = float(
        os.getenv("HEBBIAN_MIND_EDGE_FACTOR", "1.0")
    )
    MAX_EDGE_WEIGHT: float = float(os.getenv("HEBBIAN_MIND_MAX_WEIGHT", "10.0"))

    # Logging
    LOG_LEVEL: str = os.getenv("HEBBIAN_MIND_LOG_LEVEL", "INFO")

    @classmethod
    def ensure_directories(cls) -> None:
        """Ensure all required directories exist"""
        cls.DISK_DATA_DIR.mkdir(parents=True, exist_ok=True)
        if cls.RAM_DATA_DIR and cls.RAM_DISK_ENABLED:
            cls.RAM_DATA_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def check_ram_available(cls) -> bool:
        """Check if RAM disk is available and writable"""
        if not cls.RAM_DISK_ENABLED or not cls.RAM_DATA_DIR:
            return False

        try:
            cls.RAM_DATA_DIR.mkdir(parents=True, exist_ok=True)
            test_file = cls.RAM_DATA_DIR / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except Exception:
            return False

    @classmethod
    def summary(cls) -> dict:
        """Return configuration summary"""
        return {
            "base_dir": str(cls.BASE_DIR),
            "disk_data_dir": str(cls.DISK_DATA_DIR),
            "disk_db_path": str(cls.DISK_DB_PATH),
            "ram_enabled": cls.RAM_DISK_ENABLED,
            "ram_data_dir": str(cls.RAM_DATA_DIR) if cls.RAM_DATA_DIR else None,
            "ram_available": cls.check_ram_available(),
            "faiss_enabled": cls.FAISS_TETHER_ENABLED,
            "faiss_host": cls.FAISS_TETHER_HOST if cls.FAISS_TETHER_ENABLED else None,
            "faiss_port": cls.FAISS_TETHER_PORT if cls.FAISS_TETHER_ENABLED else None,
            "precog_enabled": cls.PRECOG_ENABLED,
            "precog_path": str(cls.PRECOG_PATH) if cls.PRECOG_PATH else None,
            "activation_threshold": cls.ACTIVATION_THRESHOLD,
            "edge_strengthening_factor": cls.EDGE_STRENGTHENING_FACTOR,
            "max_edge_weight": cls.MAX_EDGE_WEIGHT,
        }
