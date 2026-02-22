#!/usr/bin/env python3
"""Download a skill from GitHub and register it in Skill Compose.

Usage:
    python add_skill.py <owner/repo@skill-name> [--api-url URL] [--skills-dir DIR]

Examples:
    python add_skill.py "vercel-labs/agent-skills@vercel-react-best-practices"
    python add_skill.py "google-labs-code/stitch-skills@react:components"

The script will:
1. Locate the skill in the GitHub repository
2. Download all skill files (SKILL.md, scripts/, references/, assets/)
3. Save to the local skills/ directory
4. Register in Skill Compose via the import-local API
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.request
import urllib.error

API_URL = os.environ.get("SKILL_COMPOSE_API", "http://localhost:62610")
GITHUB_API = "https://api.github.com"


def github_get(url: str) -> dict | list | None:
    """Make a GitHub API request."""
    headers = {"User-Agent": "skill-finder/1.0", "Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"GitHub API rate limit hit. Set GITHUB_TOKEN env var to increase limit.", file=sys.stderr)
        elif e.code == 404:
            return None
        else:
            print(f"GitHub API error {e.code}: {e.reason}", file=sys.stderr)
        return None
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"Network error: {e}", file=sys.stderr)
        return None


def download_raw(url: str) -> bytes | None:
    """Download raw file content."""
    headers = {"User-Agent": "skill-finder/1.0"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        print(f"  Failed to download {url}: {e}", file=sys.stderr)
        return None


def parse_source(source: str) -> tuple[str, str, str]:
    """Parse 'owner/repo@skill-name' into (owner, repo, skill_name)."""
    m = re.match(r"^([^/]+)/([^@]+)@(.+)$", source)
    if not m:
        print(f"Invalid format: {source}", file=sys.stderr)
        print(f"Expected: owner/repo@skill-name", file=sys.stderr)
        sys.exit(1)
    return m.group(1), m.group(2), m.group(3)


def get_default_branch(owner: str, repo: str) -> str:
    """Get the default branch of a repo."""
    data = github_get(f"{GITHUB_API}/repos/{owner}/{repo}")
    if data and isinstance(data, dict):
        return data.get("default_branch", "main")
    return "main"


def find_skill_in_tree(owner: str, repo: str, branch: str, skill_name: str) -> str | None:
    """Find the directory path of a skill in the repo tree.

    Tries multiple strategies:
    1. Exact match: skills/{skill-name}/SKILL.md
    2. Scan skills/ subdirectories for SKILL.md with matching name in frontmatter
    3. Root SKILL.md (repo is a single skill)
    """
    tree_url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    data = github_get(tree_url)
    if not data or not isinstance(data, dict):
        print(f"Failed to fetch repo tree", file=sys.stderr)
        return None

    entries = data.get("tree", [])
    skill_md_paths = []

    for entry in entries:
        if entry.get("type") == "blob" and entry["path"].endswith("SKILL.md"):
            skill_md_paths.append(entry["path"])

    # Strategy 1: Exact directory name match
    for path in skill_md_paths:
        dir_name = path.rsplit("/SKILL.md", 1)[0].split("/")[-1] if "/" in path else ""
        if dir_name == skill_name:
            return path.rsplit("/SKILL.md", 1)[0]

    # Strategy 2: Check SKILL.md frontmatter for name match
    for path in skill_md_paths:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        content = download_raw(raw_url)
        if not content:
            continue
        text = content.decode("utf-8", errors="replace")
        # Parse frontmatter name
        fm_match = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if fm_match:
            name_match = re.search(r"^name:\s*[\"']?([^\"'\n]+)", fm_match.group(1), re.MULTILINE)
            if name_match and name_match.group(1).strip() == skill_name:
                if "/" in path:
                    return path.rsplit("/SKILL.md", 1)[0]
                else:
                    return ""  # Root-level SKILL.md

    print(f"Could not find skill '{skill_name}' in {owner}/{repo}", file=sys.stderr)
    return None


def download_skill_files(owner: str, repo: str, branch: str, skill_dir: str) -> dict[str, bytes]:
    """Download all files under a skill directory from GitHub.

    Returns: {relative_path: content_bytes}
    """
    tree_url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    data = github_get(tree_url)
    if not data or not isinstance(data, dict):
        return {}

    prefix = f"{skill_dir}/" if skill_dir else ""
    files = {}

    for entry in data.get("tree", []):
        if entry.get("type") != "blob":
            continue
        path = entry["path"]
        if prefix and not path.startswith(prefix):
            continue
        if not prefix and "/" in path:
            # Root-level skill: only include SKILL.md and standard subdirs
            parts = path.split("/")
            if parts[0] not in ("scripts", "references", "assets") and path != "SKILL.md":
                continue

        rel_path = path[len(prefix):] if prefix else path
        # Skip hidden files, __pycache__, etc.
        if any(part.startswith(".") or part == "__pycache__" for part in rel_path.split("/")):
            continue
        # Skip compiled artifacts
        if rel_path.endswith((".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".exe", ".wasm")):
            continue

        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        content = download_raw(raw_url)
        if content is not None:
            files[rel_path] = content

    return files


def save_skill(skill_name: str, files: dict[str, bytes], skills_dir: str) -> str:
    """Save downloaded files to skills/{skill_name}/. Returns the skill directory path."""
    skill_path = os.path.join(skills_dir, skill_name)
    os.makedirs(skill_path, exist_ok=True)

    for rel_path, content in files.items():
        file_path = os.path.join(skill_path, rel_path)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(content)
        print(f"  Saved: {rel_path} ({len(content)} bytes)")

    return skill_path


def register_skill(skill_name: str, api_url: str) -> bool:
    """Register the skill in Skill Compose via import-local API."""
    url = f"{api_url}/api/v1/registry/import-local"
    payload = json.dumps({"skill_names": [skill_name]}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "skill-finder/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            if resp.status == 200:
                imported = result.get("imported", [])
                skipped = result.get("skipped", [])
                if imported:
                    print(f"  Registered: {skill_name}")
                    return True
                elif skipped:
                    print(f"  Already registered: {skill_name} (skipped)")
                    return True
            print(f"  Registration response: {result}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  Registration failed ({e.code}): {body}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  Registration failed: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Download and register a skill from GitHub")
    parser.add_argument("source", help="Skill source: owner/repo@skill-name")
    parser.add_argument("--api-url", default=API_URL, help=f"Skill Compose API URL (default: {API_URL})")
    parser.add_argument("--skills-dir", default=None, help="Skills directory (default: auto-detect)")
    args = parser.parse_args()

    # Auto-detect skills directory
    skills_dir = args.skills_dir
    if not skills_dir:
        skills_dir = os.environ.get("SKILLS_DIR")
    if not skills_dir:
        # Docker environment: /app/skills/
        if os.path.isdir("/app/skills"):
            skills_dir = "/app/skills"
        else:
            # Local dev: relative to this script → skill-finder/ → skills/
            script_dir = os.path.dirname(os.path.abspath(__file__))
            candidate = os.path.normpath(os.path.join(script_dir, "..", ".."))
            if os.path.isdir(candidate) and os.path.isfile(os.path.join(candidate, "..", "app", "main.py")):
                skills_dir = candidate
            else:
                skills_dir = os.path.join(os.getcwd(), "skills")

    owner, repo, skill_name = parse_source(args.source)
    print(f"Finding skill '{skill_name}' in {owner}/{repo}...")

    # Step 1: Get default branch
    branch = get_default_branch(owner, repo)
    print(f"  Branch: {branch}")

    # Step 2: Find skill directory in repo
    skill_dir = find_skill_in_tree(owner, repo, branch, skill_name)
    if skill_dir is None:
        print(f"\nFailed: could not locate skill '{skill_name}'")
        sys.exit(1)
    print(f"  Found at: {skill_dir or '(root)'}/")

    # Step 3: Download files
    print(f"\nDownloading files...")
    files = download_skill_files(owner, repo, branch, skill_dir)
    if not files:
        print(f"No files found for skill '{skill_name}'")
        sys.exit(1)
    if "SKILL.md" not in files:
        print(f"Warning: SKILL.md not found in downloaded files", file=sys.stderr)

    # Step 4: Save to disk
    print(f"\nSaving to {skills_dir}/{skill_name}/")
    save_skill(skill_name, files, skills_dir)

    # Step 5: Register in Skill Compose
    print(f"\nRegistering in Skill Compose...")
    success = register_skill(skill_name, args.api_url)

    if success:
        print(f"\nDone! Skill '{skill_name}' is now available in Skill Compose.")
        print(f"  Source: https://github.com/{owner}/{repo}")
        print(f"  Browse: https://skills.sh/{owner}/{repo}/{skill_name}")
    else:
        print(f"\nFiles saved but registration failed. You can manually register:")
        print(f'  curl -X POST "{args.api_url}/api/v1/registry/import-local" \\')
        print(f'    -H "Content-Type: application/json" \\')
        print(f'    -d \'{{"skill_names": ["{skill_name}"]}}\'')


if __name__ == "__main__":
    main()
