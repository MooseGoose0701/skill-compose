#!/usr/bin/env python3
"""
Trace Analyzer - Analyzes skill execution traces to identify issues and improvement opportunities.

Usage:
    analyze_traces.py <traces-file-or-dir> [--skill <skill-name>] [--format json|text]

Examples:
    analyze_traces.py traces.json
    analyze_traces.py ./traces/ --skill pdf-to-md
    analyze_traces.py traces.json --format json
"""

import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Optional


def load_traces(path: str) -> List[Dict[str, Any]]:
    """Load traces from a JSON file or directory of JSON files."""
    path = Path(path)
    traces = []

    if path.is_file():
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                traces.extend(data)
            else:
                traces.append(data)
    elif path.is_dir():
        for json_file in path.glob('*.json'):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    traces.extend(data)
                else:
                    traces.append(data)
    else:
        raise FileNotFoundError(f"Path not found: {path}")

    return traces


def filter_traces_by_skill(traces: List[Dict], skill_name: str) -> List[Dict]:
    """Filter traces to only include those that used a specific skill."""
    filtered = []
    for trace in traces:
        skills_used = trace.get('skills_used') or []
        if skill_name in skills_used:
            filtered.append(trace)
    return filtered


def analyze_single_trace(trace: Dict) -> Dict[str, Any]:
    """Analyze a single trace for issues and patterns."""
    issues = []
    warnings = []
    metrics = {}

    # Basic metrics
    metrics['success'] = trace.get('success', False)
    metrics['total_turns'] = trace.get('total_turns', 0)
    metrics['duration_ms'] = trace.get('duration_ms', 0)
    metrics['total_input_tokens'] = trace.get('total_input_tokens', 0)
    metrics['total_output_tokens'] = trace.get('total_output_tokens', 0)

    steps = trace.get('steps', [])
    llm_calls = trace.get('llm_calls', [])

    # Issue 1: Failure
    if not trace.get('success', True):
        issues.append({
            'type': 'execution_failure',
            'severity': 'high',
            'description': 'Skill execution failed',
            'context': trace.get('error', trace.get('answer', 'No error details'))
        })

    # Issue 2: Too many turns (inefficiency)
    if metrics['total_turns'] > 5:
        warnings.append({
            'type': 'high_turn_count',
            'severity': 'medium',
            'description': f"High number of LLM turns: {metrics['total_turns']}",
            'suggestion': 'Consider optimizing workflow or adding more specific instructions'
        })

    # Issue 3: High token usage
    total_tokens = metrics['total_input_tokens'] + metrics['total_output_tokens']
    if total_tokens > 50000:
        warnings.append({
            'type': 'high_token_usage',
            'severity': 'medium',
            'description': f"High token usage: {total_tokens}",
            'suggestion': 'Consider reducing context or splitting into smaller operations'
        })

    # Issue 4: Long duration
    if metrics['duration_ms'] > 60000:  # > 1 minute
        warnings.append({
            'type': 'long_duration',
            'severity': 'low',
            'description': f"Long execution time: {metrics['duration_ms']/1000:.1f}s",
            'suggestion': 'Consider breaking down the task or optimizing scripts'
        })

    # Analyze steps for patterns
    tool_errors = []
    tool_usage = defaultdict(int)
    repeated_tool_calls = []

    prev_tool = None
    prev_tool_input = None

    for step in steps:
        if step.get('role') == 'tool':
            tool_name = step.get('tool_name')
            tool_input = step.get('tool_input')
            tool_result = step.get('tool_result', '')

            if tool_name:
                tool_usage[tool_name] += 1

            # Check for errors in tool results
            if isinstance(tool_result, str):
                if 'error' in tool_result.lower() or 'failed' in tool_result.lower():
                    tool_errors.append({
                        'tool': tool_name,
                        'result': tool_result[:200]
                    })

            # Check for repeated identical tool calls
            if tool_name == prev_tool and json.dumps(tool_input) == json.dumps(prev_tool_input):
                repeated_tool_calls.append(tool_name)

            prev_tool = tool_name
            prev_tool_input = tool_input

    # Issue 5: Tool errors
    if tool_errors:
        issues.append({
            'type': 'tool_errors',
            'severity': 'high',
            'description': f"Tool errors encountered: {len(tool_errors)}",
            'details': tool_errors
        })

    # Issue 6: Repeated tool calls (potential retry loops)
    if repeated_tool_calls:
        warnings.append({
            'type': 'repeated_tool_calls',
            'severity': 'medium',
            'description': f"Repeated identical tool calls: {repeated_tool_calls}",
            'suggestion': 'Add error handling or clearer instructions to avoid retries'
        })

    # Analyze LLM calls for stop reasons
    for llm_call in llm_calls:
        stop_reason = llm_call.get('stop_reason')
        if stop_reason == 'max_tokens':
            issues.append({
                'type': 'max_tokens_reached',
                'severity': 'high',
                'description': f"LLM response was truncated (max_tokens) at turn {llm_call.get('turn')}",
                'suggestion': 'Task may be too complex or response too long'
            })

    return {
        'trace_id': trace.get('id'),
        'request': trace.get('request'),
        'skills_used': trace.get('skills_used'),
        'metrics': metrics,
        'issues': issues,
        'warnings': warnings,
        'tool_usage': dict(tool_usage)
    }


def aggregate_analyses(analyses: List[Dict]) -> Dict[str, Any]:
    """Aggregate multiple trace analyses into a summary."""
    if not analyses:
        return {'error': 'No traces to analyze'}

    summary = {
        'total_traces': len(analyses),
        'success_rate': 0,
        'avg_turns': 0,
        'avg_duration_ms': 0,
        'avg_tokens': 0,
        'common_issues': defaultdict(int),
        'common_warnings': defaultdict(int),
        'tool_usage_total': defaultdict(int),
        'failed_traces': [],
        'problematic_traces': []
    }

    success_count = 0
    total_turns = 0
    total_duration = 0
    total_tokens = 0

    for analysis in analyses:
        metrics = analysis['metrics']

        if metrics['success']:
            success_count += 1
        else:
            summary['failed_traces'].append({
                'id': analysis['trace_id'],
                'request': analysis['request'][:100] if analysis['request'] else None
            })

        total_turns += metrics['total_turns']
        total_duration += metrics['duration_ms']
        total_tokens += metrics['total_input_tokens'] + metrics['total_output_tokens']

        for issue in analysis['issues']:
            summary['common_issues'][issue['type']] += 1

        for warning in analysis['warnings']:
            summary['common_warnings'][warning['type']] += 1

        for tool, count in analysis['tool_usage'].items():
            summary['tool_usage_total'][tool] += count

        # Mark as problematic if has high-severity issues
        if any(i['severity'] == 'high' for i in analysis['issues']):
            summary['problematic_traces'].append({
                'id': analysis['trace_id'],
                'request': analysis['request'][:100] if analysis['request'] else None,
                'issues': [i['type'] for i in analysis['issues']]
            })

    summary['success_rate'] = success_count / len(analyses) if analyses else 0
    summary['avg_turns'] = total_turns / len(analyses) if analyses else 0
    summary['avg_duration_ms'] = total_duration / len(analyses) if analyses else 0
    summary['avg_tokens'] = total_tokens / len(analyses) if analyses else 0
    summary['common_issues'] = dict(summary['common_issues'])
    summary['common_warnings'] = dict(summary['common_warnings'])
    summary['tool_usage_total'] = dict(summary['tool_usage_total'])

    return summary


def generate_recommendations(summary: Dict, analyses: List[Dict]) -> List[Dict]:
    """Generate improvement recommendations based on analysis."""
    recommendations = []

    # Recommendation 1: Low success rate
    if summary['success_rate'] < 0.9:
        recommendations.append({
            'priority': 'high',
            'area': 'reliability',
            'issue': f"Low success rate: {summary['success_rate']*100:.1f}%",
            'recommendation': 'Review failed traces and add error handling or clearer instructions',
            'affected_traces': summary['failed_traces']
        })

    # Recommendation 2: High turn count
    if summary['avg_turns'] > 4:
        recommendations.append({
            'priority': 'medium',
            'area': 'efficiency',
            'issue': f"High average turn count: {summary['avg_turns']:.1f}",
            'recommendation': 'Simplify workflows, add more specific instructions, or use scripts for complex operations'
        })

    # Recommendation 3: Tool errors
    if summary['common_issues'].get('tool_errors', 0) > 0:
        recommendations.append({
            'priority': 'high',
            'area': 'reliability',
            'issue': f"Tool errors in {summary['common_issues']['tool_errors']} traces",
            'recommendation': 'Review and fix scripts, add input validation, improve error messages'
        })

    # Recommendation 4: High token usage
    if summary['avg_tokens'] > 30000:
        recommendations.append({
            'priority': 'medium',
            'area': 'cost',
            'issue': f"High average token usage: {summary['avg_tokens']:.0f}",
            'recommendation': 'Reduce SKILL.md verbosity, use progressive disclosure, optimize prompts'
        })

    # Recommendation 5: Repeated tool calls
    if summary['common_warnings'].get('repeated_tool_calls', 0) > 0:
        recommendations.append({
            'priority': 'medium',
            'area': 'efficiency',
            'issue': 'Repeated identical tool calls detected',
            'recommendation': 'Add better error handling, clearer success/failure conditions'
        })

    return recommendations


def format_text_report(summary: Dict, recommendations: List[Dict], analyses: List[Dict]) -> str:
    """Format the analysis as a text report."""
    lines = []
    lines.append("=" * 70)
    lines.append("SKILL TRACE ANALYSIS REPORT")
    lines.append("=" * 70)

    lines.append(f"\nTotal traces analyzed: {summary['total_traces']}")
    lines.append(f"Success rate: {summary['success_rate']*100:.1f}%")
    lines.append(f"Average turns: {summary['avg_turns']:.1f}")
    lines.append(f"Average duration: {summary['avg_duration_ms']/1000:.1f}s")
    lines.append(f"Average tokens: {summary['avg_tokens']:.0f}")

    if summary['common_issues']:
        lines.append("\n--- Common Issues ---")
        for issue, count in sorted(summary['common_issues'].items(), key=lambda x: -x[1]):
            lines.append(f"  {issue}: {count} occurrences")

    if summary['common_warnings']:
        lines.append("\n--- Common Warnings ---")
        for warning, count in sorted(summary['common_warnings'].items(), key=lambda x: -x[1]):
            lines.append(f"  {warning}: {count} occurrences")

    if recommendations:
        lines.append("\n--- Recommendations ---")
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"\n{i}. [{rec['priority'].upper()}] {rec['area']}")
            lines.append(f"   Issue: {rec['issue']}")
            lines.append(f"   Action: {rec['recommendation']}")

    if summary['failed_traces']:
        lines.append("\n--- Failed Traces ---")
        for trace in summary['failed_traces'][:5]:
            lines.append(f"  - {trace['id']}: {trace['request']}")
        if len(summary['failed_traces']) > 5:
            lines.append(f"  ... and {len(summary['failed_traces']) - 5} more")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='Analyze skill execution traces')
    parser.add_argument('traces_path', help='Path to traces JSON file or directory')
    parser.add_argument('--skill', help='Filter to specific skill name')
    parser.add_argument('--format', choices=['json', 'text'], default='text', help='Output format')

    args = parser.parse_args()

    try:
        traces = load_traces(args.traces_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if args.skill:
        traces = filter_traces_by_skill(traces, args.skill)
        if not traces:
            print(f"No traces found for skill: {args.skill}", file=sys.stderr)
            sys.exit(1)

    # Analyze each trace
    analyses = [analyze_single_trace(trace) for trace in traces]

    # Aggregate results
    summary = aggregate_analyses(analyses)

    # Generate recommendations
    recommendations = generate_recommendations(summary, analyses)

    if args.format == 'json':
        output = {
            'summary': summary,
            'recommendations': recommendations,
            'individual_analyses': analyses
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(format_text_report(summary, recommendations, analyses))


if __name__ == "__main__":
    main()
