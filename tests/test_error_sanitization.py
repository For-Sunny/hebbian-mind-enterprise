"""
Tests for error message sanitization

Ensures internal paths are not leaked to customers in error messages.

Copyright (c) 2026 CIPS LLC
"""

import pytest

from hebbian_mind.config import sanitize_error_message


class TestErrorSanitization:
    """Test error message sanitization."""

    def test_sanitizes_windows_user_paths(self):
        """Test that Windows user paths are stripped."""
        error = Exception(r"FileNotFoundError: C:\Users\Pirate\Desktop\secret\file.py not found")
        result = sanitize_error_message(error)
        assert r"C:\Users\Pirate" not in result
        assert "file.py" in result

    def test_sanitizes_linux_home_paths(self):
        """Test that Linux home paths are stripped."""
        error = Exception("FileNotFoundError: /home/admin/app/secret/file.py not found")
        result = sanitize_error_message(error)
        assert "/home/admin/" not in result
        assert "file.py" in result

    def test_sanitizes_docker_app_paths(self):
        """Test that Docker /app/ paths are stripped."""
        error = Exception("ImportError: /app/src/hebbian_mind/server.py")
        result = sanitize_error_message(error)
        assert "/app/" not in result

    def test_sanitizes_program_files_paths(self):
        """Test that Program Files paths are stripped."""
        error = Exception(r"C:\Program Files\Python312\lib\site.py")
        result = sanitize_error_message(error)
        assert r"C:\Program Files" not in result

    def test_sanitizes_tmp_paths(self):
        """Test that /tmp/ paths are stripped."""
        error = Exception("Error writing to /tmp/hebbian_cache_123.db")
        result = sanitize_error_message(error)
        assert "/tmp/" not in result

    def test_sanitizes_var_paths(self):
        """Test that /var/ paths are stripped."""
        error = Exception("Permission denied: /var/log/hebbian.log")
        result = sanitize_error_message(error)
        assert "/var/log/" not in result

    def test_sanitizes_python_traceback_files(self):
        """Test that Python traceback file references are sanitized."""
        error = Exception('File "/home/user/app/server.py", line 100, in main')
        result = sanitize_error_message(error)
        assert "/home/user/" not in result

    def test_preserves_error_message_content(self):
        """Test that the actual error message is preserved."""
        error = Exception("Database connection failed: timeout after 30 seconds")
        result = sanitize_error_message(error)
        assert "Database connection failed" in result
        assert "timeout after 30 seconds" in result

    def test_handles_no_paths(self):
        """Test that errors without paths are returned unchanged."""
        error = Exception("Invalid argument: threshold must be between 0 and 1")
        result = sanitize_error_message(error)
        assert result == str(error)

    def test_handles_empty_error(self):
        """Test that empty errors are handled."""
        error = Exception("")
        result = sanitize_error_message(error)
        assert result == ""

    def test_sanitizes_multiple_paths(self):
        """Test that multiple paths in one error are all sanitized."""
        error = Exception(
            r"Error copying C:\Users\admin\source.txt to C:\Users\admin\dest.txt"
        )
        result = sanitize_error_message(error)
        assert r"C:\Users\admin" not in result
        # The filenames should still be referenced
        assert "source.txt" in result
        assert "dest.txt" in result

    def test_sanitizes_opt_paths(self):
        """Test that /opt/ package paths are stripped."""
        error = Exception("Module not found at /opt/hebbian/lib/core.py")
        result = sanitize_error_message(error)
        assert "/opt/hebbian/" not in result

    def test_sanitizes_usr_local_paths(self):
        """Test that /usr/local/ paths are stripped."""
        error = Exception("Binary not found: /usr/local/bin/python3")
        result = sanitize_error_message(error)
        assert "/usr/local/" not in result

    def test_case_insensitive_windows_paths(self):
        """Test that Windows paths with different cases are sanitized."""
        error = Exception(r"Error: c:\users\Admin\file.txt")
        result = sanitize_error_message(error)
        assert r"c:\users\Admin" not in result

    def test_sanitizes_windows_drive_paths(self):
        """Test that various Windows drive paths are sanitized."""
        error = Exception(r"Error: D:\Projects\secret\config.json")
        result = sanitize_error_message(error)
        assert r"D:\Projects" not in result
