#!/usr/bin/env python3
"""
Quick test runner script for Hebbian Mind Enterprise

Copyright (c) 2026 CIPS LLC
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and report results."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"{'='*60}")
    try:
        subprocess.run(cmd, check=True, capture_output=False)
        print(f"✓ {description} passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed with exit code {e.returncode}")
        return False


def main():
    """Run test suite with various configurations."""

    # Change to project root
    project_root = Path(__file__).parent.parent

    print("Hebbian Mind Enterprise Test Suite")
    print(f"Project root: {project_root}")

    results = []

    # 1. Run all tests
    results.append(run_command(["pytest", "-v"], "All tests"))

    # 2. Run with coverage
    results.append(
        run_command(
            ["pytest", "--cov=hebbian_mind", "--cov-report=term-missing"], "Tests with coverage"
        )
    )

    # 3. Run specific test files
    test_files = [
        "tests/test_graph.py",
        "tests/test_hebbian.py",
        "tests/test_mcp_server.py",
        "tests/test_persistence.py",
    ]

    for test_file in test_files:
        results.append(run_command(["pytest", "-v", test_file], f"Test file: {test_file}"))

    # 4. Run only fast tests (exclude slow)
    results.append(run_command(["pytest", "-v", "-m", "not slow"], "Fast tests only"))

    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✓ All test suites passed!")
        return 0
    else:
        print(f"✗ {total - passed} test suite(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
