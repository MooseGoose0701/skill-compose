#!/usr/bin/env python3
"""Search the skills.sh ecosystem for agent skills.

Usage:
    python find_skills.py <query> [--limit N]

Examples:
    python find_skills.py "react performance"
    python find_skills.py docker --limit 5
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse
import urllib.error

SEARCH_API = "https://skills.sh/api/search"


def search_skills(query: str, limit: int = 10) -> list[dict]:
    """Search skills.sh API and return results."""
    params = urllib.parse.urlencode({"q": query, "limit": limit})
    url = f"{SEARCH_API}?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": "skill-finder/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"Error searching skills.sh: {e}", file=sys.stderr)
        return []

    skills = data.get("skills", [])
    return [
        {
            "name": s.get("name", ""),
            "source": s.get("source", ""),
            "installs": s.get("installs", 0),
            "slug": s.get("id", ""),
            "url": f"https://skills.sh/{s.get('id', '')}",
        }
        for s in skills
    ]


def format_installs(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M".rstrip("0").rstrip(".") + " installs"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K".rstrip("0").rstrip(".") + " installs"
    if count > 0:
        return f"{count} install{'s' if count != 1 else ''}"
    return ""


def main():
    parser = argparse.ArgumentParser(description="Search skills.sh for agent skills")
    parser.add_argument("query", nargs="+", help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    query = " ".join(args.query)
    results = search_skills(query, args.limit)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if not results:
        print(f"No skills found for \"{query}\"")
        return

    print(f"Found {len(results)} skill(s) for \"{query}\":\n")
    print(f"{'#':<4} {'Source@Name':<55} {'Installs':<15}")
    print("-" * 74)

    for i, skill in enumerate(results, 1):
        pkg = f"{skill['source']}@{skill['name']}" if skill["source"] else skill["name"]
        installs = format_installs(skill["installs"])
        print(f"{i:<4} {pkg:<55} {installs:<15}")

    print(f"\nInstall with: python add_skill.py <source@name>")
    print(f"Browse: https://skills.sh/")


if __name__ == "__main__":
    main()
