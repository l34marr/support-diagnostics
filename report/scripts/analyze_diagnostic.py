#!/usr/bin/env python3
"""
ELK Diagnostic Data Analysis & Health Check Tool
Main CLI entry point.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from diagnostic_parser import parse_diagnostic_archive
from check_registry import run_health_checks
from data_models import HealthReport, HealthSummary, Severity
from report_generators.markdown import generate_markdown_report
from report_generators.json_report import save_json_report
from utils.thresholds import load_thresholds
from utils.recommendations import load_recommendations


def calculate_health_score(issues: list) -> int:
    """
    Calculate overall health score based on issues.

    Returns score from 0-100.
    """
    if not issues:
        return 100

    score = 100

    for issue in issues:
        if issue.severity == Severity.CRITICAL:
            score -= 20
        elif issue.severity == Severity.WARNING:
            score -= 5
        elif issue.severity == Severity.INFO:
            score -= 1

    return max(0, min(100, score))


def analyze_diagnostic(archive_path: str, config_file: Optional[str] = None) -> HealthReport:
    """
    Main analysis pipeline.

    Returns complete health report.
    """
    print(f"Analyzing diagnostic archive: {archive_path}")

    thresholds = load_thresholds(config_file)
    recommendations = load_recommendations(config_file)

    data = parse_diagnostic_archive(archive_path)

    issues = run_health_checks(data, thresholds)

    summary = HealthSummary(
        score=calculate_health_score(issues),
        critical_count=sum(1 for i in issues if i.severity == Severity.CRITICAL),
        warning_count=sum(1 for i in issues if i.severity == Severity.WARNING),
        info_count=sum(1 for i in issues if i.severity == Severity.INFO),
        total_checks=len(issues),
    )

    cluster_name = data.cluster.name if data.cluster else "unknown"

    report = HealthReport(
        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        cluster_name=cluster_name,
        summary=summary,
        issues=issues,
        data=data,
    )

    print(f"Analysis complete. Score: {summary.score}/100")
    print(f"Critical issues: {summary.critical_count}")
    print(f"Warnings: {summary.warning_count}")
    print(f"Info: {summary.info_count}")

    return report


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze ELK diagnostic archives and generate health check reports"
    )

    parser.add_argument(
        "archive",
        type=str,
        #required=True,
        help="Path to diagnostic ZIP archive",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=".",
        help="Output directory for reports (default: current directory)",
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to custom thresholds configuration file",
    )

    parser.add_argument(
        "--format",
        "-f",
        type=str,
        default="json,markdown",
        help="Report format(s): json, markdown (default: both)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    try:
        report = analyze_diagnostic(args.archive, args.config)

        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        formats = args.format.split(',')

        if 'json' in formats or 'all' in formats:
            json_path = output_dir / "health_report.json"
            save_json_report(report, str(json_path))
            print(f"JSON report saved to: {json_path}")

        if 'markdown' in formats or 'all' in formats:
            md_path = output_dir / "health_report.md"
            md_content = generate_markdown_report(report)
            with open(md_path, 'w') as f:
                f.write(md_content)
            print(f"Markdown report saved to: {md_path}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
