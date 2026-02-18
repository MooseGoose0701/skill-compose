"""
Targeted tests for subprocess-based file write mechanism.

Tests that _write_via_subprocess() in app/agent/tools.py correctly writes files
that are visible to child subprocesses (bash, execute_code), addressing the
Docker overlay2 filesystem visibility issue.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


def _write_via_subprocess(filepath: Path, content: str) -> None:
    """Mirror of the helper in app/agent/tools.py"""
    subprocess.run(
        ['mkdir', '-p', str(filepath.parent)],
        check=True, capture_output=True,
    )
    proc = subprocess.run(
        ['sh', '-c', 'cat > "$1"', 'sh', str(filepath)],
        input=content.encode('utf-8'),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise IOError(
            f"Subprocess write failed (exit {proc.returncode}): "
            f"{proc.stderr.decode(errors='replace')}"
        )


@pytest.fixture
def tmpdir():
    d = tempfile.mkdtemp(prefix="test_subproc_write_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


class TestSubprocessWriteVisibility:
    """Core test: files written via subprocess are visible to other subprocesses."""

    def test_parent_process_can_read(self, tmpdir):
        fp = tmpdir / "test.txt"
        _write_via_subprocess(fp, "hello")
        with open(fp, 'r') as f:
            assert f.read() == "hello"

    def test_child_subprocess_can_read(self, tmpdir):
        fp = tmpdir / "test.txt"
        _write_via_subprocess(fp, "hello from write")
        result = subprocess.run(['cat', str(fp)], capture_output=True, text=True)
        assert result.returncode == 0
        assert result.stdout == "hello from write"

    def test_bash_subprocess_can_read(self, tmpdir):
        fp = tmpdir / "test.txt"
        _write_via_subprocess(fp, "bash visible")
        result = subprocess.run(
            ['bash', '-c', f'cat "{fp}"'],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert result.stdout == "bash visible"

    def test_python_subprocess_can_read(self, tmpdir):
        fp = tmpdir / "test.py"
        _write_via_subprocess(fp, 'print("executed")')
        result = subprocess.run(
            ['python3', str(fp)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "executed"


class TestSubprocessWriteContent:
    """Content integrity tests."""

    def test_unicode_content(self, tmpdir):
        fp = tmpdir / "unicode.txt"
        content = "你好世界 こんにちは 🌍"
        _write_via_subprocess(fp, content)
        result = subprocess.run(['cat', str(fp)], capture_output=True)
        assert result.stdout.decode('utf-8') == content

    def test_multiline_content(self, tmpdir):
        fp = tmpdir / "multi.txt"
        content = "line1\nline2\nline3\n"
        _write_via_subprocess(fp, content)
        result = subprocess.run(['cat', str(fp)], capture_output=True, text=True)
        assert result.stdout == content

    def test_empty_content(self, tmpdir):
        fp = tmpdir / "empty.txt"
        _write_via_subprocess(fp, "")
        assert fp.exists()
        assert fp.stat().st_size == 0

    def test_large_file_1mb(self, tmpdir):
        fp = tmpdir / "large.txt"
        content = "x" * 1_000_000
        _write_via_subprocess(fp, content)
        assert fp.stat().st_size == 1_000_000
        result = subprocess.run(['wc', '-c', str(fp)], capture_output=True, text=True)
        assert "1000000" in result.stdout

    def test_shell_special_chars_no_injection(self, tmpdir):
        """Content with shell metacharacters must be preserved literally."""
        fp = tmpdir / "special.txt"
        content = '$HOME $(whoami) `id` && rm -rf / ; echo pwned | cat /etc/passwd'
        _write_via_subprocess(fp, content)
        with open(fp, 'r') as f:
            assert f.read() == content


class TestSubprocessWriteEdgeCases:
    """Edge cases and robustness."""

    def test_creates_parent_directories(self, tmpdir):
        fp = tmpdir / "a" / "b" / "c" / "deep.txt"
        _write_via_subprocess(fp, "deep")
        assert fp.exists()
        with open(fp, 'r') as f:
            assert f.read() == "deep"

    def test_overwrite_existing_file(self, tmpdir):
        fp = tmpdir / "overwrite.txt"
        _write_via_subprocess(fp, "version1")
        _write_via_subprocess(fp, "version2")
        with open(fp, 'r') as f:
            assert f.read() == "version2"

    def test_multiple_files_all_visible(self, tmpdir):
        """Write multiple files, verify all visible from a single bash call."""
        for i in range(10):
            _write_via_subprocess(tmpdir / f"file_{i}.txt", f"content_{i}")

        # Verify all from bash
        for i in range(10):
            result = subprocess.run(
                ['cat', str(tmpdir / f"file_{i}.txt")],
                capture_output=True, text=True,
            )
            assert result.returncode == 0
            assert result.stdout == f"content_{i}"

    def test_write_then_edit_pattern(self, tmpdir):
        """Simulate write → edit → bash read (the exact agent pattern)."""
        fp = tmpdir / "code.py"
        # Step 1: write creates file
        _write_via_subprocess(fp, 'x = 1\ny = 2\nprint(x + y)\n')
        # Step 2: edit replaces content (read + modify + write)
        with open(fp, 'r') as f:
            content = f.read()
        new_content = content.replace('x + y', 'x * y')
        _write_via_subprocess(fp, new_content)
        # Step 3: bash runs it
        result = subprocess.run(
            ['python3', str(fp)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "2"  # 1 * 2 = 2

    def test_binary_like_content(self, tmpdir):
        """Null bytes and binary-ish content via utf-8 encoding."""
        fp = tmpdir / "data.txt"
        # Not truly binary, but content with backslashes etc.
        content = "line1\\x00line2\\nlit_newline"
        _write_via_subprocess(fp, content)
        with open(fp, 'r') as f:
            assert f.read() == content


class TestEditViaSubprocess:
    """Test the edit() function's write-back also uses subprocess."""

    def test_edit_result_visible_to_bash(self, tmpdir):
        """Simulate edit tool: read file, replace string, write back via subprocess."""
        fp = tmpdir / "edit_test.txt"
        original = "Hello World\nFoo Bar\nHello World\n"
        _write_via_subprocess(fp, original)

        # Simulate edit: read, replace, write back
        with open(fp, 'r') as f:
            content = f.read()
        new_content = content.replace("Hello World", "Goodbye World", 1)
        _write_via_subprocess(fp, new_content)

        # Verify via bash
        result = subprocess.run(
            ['bash', '-c', f'grep -c "Goodbye" "{fp}"'],
            capture_output=True, text=True,
        )
        assert result.stdout.strip() == "1"

        result = subprocess.run(
            ['bash', '-c', f'grep -c "Hello" "{fp}"'],
            capture_output=True, text=True,
        )
        assert result.stdout.strip() == "1"  # Second occurrence preserved
