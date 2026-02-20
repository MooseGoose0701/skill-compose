#!/usr/bin/env python3
"""
Analyze a skill to understand its structure and contents.
Useful for understanding a skill before making updates.
"""

import sys
import os
import re
import yaml
import zipfile
import tempfile
import shutil
from pathlib import Path


def extract_frontmatter(content):
    """Extract YAML frontmatter from SKILL.md content."""
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        # Try to extract name and description manually if YAML parsing fails
        # This handles cases where description contains special YAML characters
        frontmatter_text = match.group(1)
        result = {}

        # Extract name
        name_match = re.search(r'^name:\s*(.+)$', frontmatter_text, re.MULTILINE)
        if name_match:
            result['name'] = name_match.group(1).strip()

        # Extract description (everything after "description:" until end or next field)
        desc_match = re.search(r'^description:\s*(.+?)(?=\n[a-z]+:|$)', frontmatter_text, re.MULTILINE | re.DOTALL)
        if desc_match:
            result['description'] = desc_match.group(1).strip()

        return result if result else None


def get_body_stats(content):
    """Get statistics about the SKILL.md body."""
    # Remove frontmatter
    match = re.match(r'^---\n.*?\n---\n?(.*)', content, re.DOTALL)
    if match:
        body = match.group(1)
    else:
        body = content

    lines = body.strip().split('\n')
    words = len(body.split())

    return {
        'lines': len(lines),
        'words': words,
        'approaching_limit': len(lines) > 400  # Warn if approaching 500 line limit
    }


def analyze_skill(skill_path):
    """Analyze a skill and return a summary."""
    skill_path = Path(skill_path)
    temp_dir = None

    # Handle .skill files (zip archives)
    if skill_path.suffix == '.skill':
        if not zipfile.is_zipfile(skill_path):
            return None, f"Invalid .skill file: {skill_path}"
        temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(skill_path, 'r') as zf:
            zf.extractall(temp_dir)
        # Find the skill directory inside
        extracted = list(Path(temp_dir).iterdir())
        if len(extracted) == 1 and extracted[0].is_dir():
            skill_path = extracted[0]
        else:
            skill_path = Path(temp_dir)

    if not skill_path.is_dir():
        if temp_dir:
            shutil.rmtree(temp_dir)
        return None, f"Not a valid skill directory: {skill_path}"

    result = {
        'path': str(skill_path),
        'name': None,
        'description': None,
        'body_stats': None,
        'resources': {
            'scripts': [],
            'references': [],
            'assets': []
        },
        'issues': []
    }

    # Check SKILL.md
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        result['issues'].append('SKILL.md not found')
    else:
        content = skill_md.read_text()
        frontmatter = extract_frontmatter(content)

        if frontmatter:
            result['name'] = frontmatter.get('name')
            result['description'] = frontmatter.get('description')
        else:
            result['issues'].append('Invalid or missing frontmatter')

        result['body_stats'] = get_body_stats(content)
        if result['body_stats']['approaching_limit']:
            result['issues'].append(f"SKILL.md is {result['body_stats']['lines']} lines - approaching 500 line limit")

    # Check resources
    for resource_type in ['scripts', 'references', 'assets']:
        resource_dir = skill_path / resource_type
        if resource_dir.exists():
            for f in resource_dir.rglob('*'):
                if f.is_file() and not f.name.startswith('.'):
                    result['resources'][resource_type].append(str(f.relative_to(skill_path)))

    # Cleanup temp directory if created
    if temp_dir:
        shutil.rmtree(temp_dir)

    return result, None


def print_analysis(analysis):
    """Print a formatted analysis report."""
    print("=" * 60)
    print("SKILL ANALYSIS")
    print("=" * 60)

    print(f"\nName: {analysis['name'] or 'Not specified'}")
    print(f"Path: {analysis['path']}")

    if analysis['description']:
        desc = analysis['description']
        if len(desc) > 100:
            desc = desc[:100] + '...'
        print(f"Description: {desc}")

    if analysis['body_stats']:
        stats = analysis['body_stats']
        print(f"\nSKILL.md Stats:")
        print(f"  Lines: {stats['lines']}")
        print(f"  Words: {stats['words']}")

    print("\nResources:")
    for resource_type, files in analysis['resources'].items():
        if files:
            print(f"  {resource_type}/:")
            for f in files:
                print(f"    - {f}")
        else:
            print(f"  {resource_type}/: (empty)")

    if analysis['issues']:
        print("\nIssues Found:")
        for issue in analysis['issues']:
            print(f"  ! {issue}")
    else:
        print("\nNo issues found.")

    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze_skill.py <skill_path>")
        print("  skill_path: Path to skill directory or .skill file")
        sys.exit(1)

    analysis, error = analyze_skill(sys.argv[1])

    if error:
        print(f"Error: {error}")
        sys.exit(1)

    print_analysis(analysis)
