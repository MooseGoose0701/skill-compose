"""File scanner for auto-detecting output files created by execute_code/bash.

Provides snapshot/diff logic to detect new or modified files after tool execution.
"""
import base64
import logging
import mimetypes
import os
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("skills_api")

# Extensions that are NOT output files (source, config, system, compiled)
IGNORED_EXTENSIONS = {
    # Compiled Python
    '.pyc', '.pyo', '.pyd',
    # Config
    '.toml', '.cfg', '.ini', '.env', '.lock',
    # System / compiled
    '.o', '.so', '.dll', '.exe', '.class', '.wasm',
    '.dylib', '.a', '.lib',
    # Cache / temp
    '.cache', '.tmp', '.bak', '.swp', '.swo',
}

IGNORED_FILENAMES = {
    '_script.py', 'requirements.txt', 'package.json', 'package-lock.json',
    'SKILL.md', 'CLAUDE.md', '.gitignore', '.dockerignore',
    'Makefile', 'Dockerfile', 'Pipfile', 'Pipfile.lock',
    'setup.py', 'setup.cfg', 'pyproject.toml',
}

IGNORED_PREFIXES = ('_script_', '.', '__')

IGNORED_DIRS = {'__pycache__', '.git', 'node_modules', '.ipynb_checkpoints'}


def _should_ignore(filepath: Path) -> bool:
    """Check if a file should be ignored based on blacklist rules."""
    name = filepath.name

    # Check ignored filenames
    if name in IGNORED_FILENAMES:
        return True

    # Check ignored prefixes
    if any(name.startswith(prefix) for prefix in IGNORED_PREFIXES):
        return True

    # Check ignored extensions
    if filepath.suffix.lower() in IGNORED_EXTENSIONS:
        return True

    # Check if any parent directory is in ignored dirs
    for part in filepath.parts:
        if part in IGNORED_DIRS:
            return True

    return False


def snapshot_files(directory: Path, recursive: bool = False) -> Dict[str, float]:
    """Take a snapshot of files in a directory.

    Args:
        directory: Directory to scan
        recursive: If True, scan recursively. If False, top-level only.

    Returns:
        Dict mapping absolute path string -> mtime
    """
    result: Dict[str, float] = {}

    if not directory.exists() or not directory.is_dir():
        return result

    try:
        if recursive:
            for filepath in directory.rglob('*'):
                if filepath.is_file() and not _should_ignore(filepath):
                    try:
                        result[str(filepath.resolve())] = filepath.stat().st_mtime
                    except OSError:
                        continue
        else:
            for filepath in directory.iterdir():
                if filepath.is_file() and not _should_ignore(filepath):
                    try:
                        result[str(filepath.resolve())] = filepath.stat().st_mtime
                    except OSError:
                        continue
    except OSError:
        pass

    return result


def diff_new_files(
    before: Dict[str, float], after: Dict[str, float]
) -> List[Path]:
    """Find files that are new or modified between two snapshots.

    Args:
        before: Snapshot before execution
        after: Snapshot after execution

    Returns:
        List of Path objects for new or modified files
    """
    new_files = []
    for path_str, mtime in after.items():
        if path_str not in before or mtime > before[path_str]:
            new_files.append(Path(path_str))
    return new_files


def _encode_path(filepath: str) -> str:
    """Base64url-encode an absolute file path for use in download URLs."""
    return base64.urlsafe_b64encode(filepath.encode('utf-8')).decode('ascii')


def build_output_file_infos(
    new_paths: List[Path],
    persist_dir: Optional[Path] = None,
) -> List[Dict]:
    """Build output file info dicts for detected files.

    If persist_dir is provided, copies each file to
    ``persist_dir/output-files/{uuid}/{filename}`` so that the download URL
    remains valid after the workspace is cleaned up.  Uses hard-links when
    possible (instant, no extra disk usage on same filesystem) and falls back
    to a regular copy otherwise.

    Args:
        new_paths: List of new/modified file paths
        persist_dir: Optional directory for long-term storage (e.g. uploads/)

    Returns:
        List of dicts with filename, size, content_type, download_url
    """
    results = []
    for filepath in new_paths:
        if not filepath.exists() or not filepath.is_file():
            continue
        try:
            size = filepath.stat().st_size
            if size == 0:
                continue
            content_type = mimetypes.guess_type(filepath.name)[0] or "application/octet-stream"

            # Persist to durable storage so download URL survives workspace cleanup
            url_path = str(filepath)
            if persist_dir:
                try:
                    file_id = str(uuid.uuid4())
                    dest_dir = persist_dir / "output-files" / file_id
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest_path = dest_dir / filepath.name
                    try:
                        os.link(str(filepath), str(dest_path))
                    except OSError:
                        shutil.copy2(str(filepath), str(dest_path))
                    url_path = str(dest_path)
                except OSError as e:
                    logger.warning(f"[OutputFile] Failed to persist {filepath.name}: {e}")

            encoded_path = _encode_path(url_path)
            results.append({
                "filename": filepath.name,
                "size": size,
                "content_type": content_type,
                "download_url": f"/api/v1/files/output/download?path={encoded_path}",
            })
        except OSError:
            continue
    return results
