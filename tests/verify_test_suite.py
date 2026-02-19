#!/usr/bin/env python3
"""
Verify test suite structure and completeness

Copyright (c) 2026 CIPS LLC
"""

import ast
from pathlib import Path


def count_test_functions(filepath: Path) -> int:
    """Count test functions in a Python file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("test_"):
                    count += 1
        return count
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return 0


def count_test_classes(filepath: Path) -> int:
    """Count test classes in a Python file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name.startswith("Test"):
                    count += 1
        return count
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return 0


def main():
    """Verify test suite structure."""
    tests_dir = Path(__file__).parent

    print("Hebbian Mind Enterprise - Test Suite Verification")
    print("=" * 60)

    # Required files
    required_files = [
        "__init__.py",
        "conftest.py",
        "test_graph.py",
        "test_hebbian.py",
        "test_mcp_server.py",
        "test_persistence.py",
        "README.md",
        "TEST_SUITE_SUMMARY.md",
    ]

    print("\n1. Checking required files...")
    all_present = True
    for filename in required_files:
        filepath = tests_dir / filename
        if filepath.exists():
            print(f"   [OK] {filename}")
        else:
            print(f"   [MISSING] {filename}")
            all_present = False

    if all_present:
        print("   All required files present!")

    # Count test functions and classes
    test_files = [
        "test_graph.py",
        "test_hebbian.py",
        "test_mcp_server.py",
        "test_persistence.py",
    ]

    print("\n2. Test statistics:")
    total_classes = 0
    total_functions = 0

    for filename in test_files:
        filepath = tests_dir / filename
        if filepath.exists():
            num_classes = count_test_classes(filepath)
            num_functions = count_test_functions(filepath)
            total_classes += num_classes
            total_functions += num_functions

            print(f"\n   {filename}:")
            print(f"     Classes:   {num_classes}")
            print(f"     Functions: {num_functions}")

    print(f"\n   Total test classes:   {total_classes}")
    print(f"   Total test functions: {total_functions}")

    # Check pytest.ini
    print("\n3. Checking pytest configuration...")
    pytest_ini = tests_dir.parent / "pytest.ini"
    if pytest_ini.exists():
        print("   [OK] pytest.ini present")
    else:
        print("   [MISSING] pytest.ini")

    # Check GitHub Actions workflow
    print("\n4. Checking CI/CD configuration...")
    workflow = tests_dir.parent / ".github" / "workflows" / "tests.yml"
    if workflow.exists():
        print("   [OK] GitHub Actions workflow present")
    else:
        print("   [MISSING] GitHub Actions workflow")

    # Count total lines
    print("\n5. Code statistics:")
    total_lines = 0
    for filepath in tests_dir.glob("*.py"):
        with open(filepath, "r", encoding="utf-8") as f:
            lines = len(f.readlines())
            total_lines += lines

    print(f"   Total lines of test code: {total_lines}")

    # Check fixtures
    print("\n6. Checking conftest.py fixtures...")
    conftest = tests_dir / "conftest.py"
    if conftest.exists():
        with open(conftest, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        fixtures = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "fixture":
                        fixtures.append(node.name)
                    elif isinstance(decorator, ast.Attribute) and decorator.attr == "fixture":
                        fixtures.append(node.name)

        print(f"   Found {len(fixtures)} fixtures:")
        for fixture in fixtures[:10]:  # Show first 10
            print(f"     - {fixture}")
        if len(fixtures) > 10:
            print(f"     ... and {len(fixtures) - 10} more")

    # Final summary
    print("\n" + "=" * 60)
    print("Test Suite Verification Complete!")
    print("=" * 60)

    if all_present and total_functions > 0:
        print("[PASS] Test suite structure is valid")
        print(f"[PASS] {total_functions} test functions ready to run")
        print("\nRun tests with: pytest -v")
        return 0
    else:
        print("[FAIL] Test suite has issues - see above")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
