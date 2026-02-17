"""
Markdown report generator.
"""

from typing import List
from data_models import HealthReport, HealthCheck, Severity
from datetime import datetime


def generate_markdown_report(report: HealthReport) -> str:
    """
    Generate Markdown formatted health report.

    Returns complete Markdown string.
    """
    lines = []

    lines.append("# Cluster Health Check Report\n")
    lines.append(f"**Generated**: {report.timestamp}\n")
    lines.append(f"**Cluster**: {report.cluster_name}\n")

    lines.append("## Executive Summary\n")
    cluster_status = report.data.cluster.status if report.data and report.data.cluster else 'unknown'
    lines.append(f"- **Cluster Status**: {_get_status_emoji(cluster_status)} {cluster_status}")
    lines.append(f"- **Critical Issues**: {report.summary.critical_count}")
    lines.append(f"- **Warnings**: {report.summary.warning_count}")
    lines.append(f"- **Info**: {report.summary.info_count}")
    lines.append(f"- **Overall Score**: {report.summary.score}/100\n")

    if report.summary.critical_count > 0:
        lines.append("## Critical Issues\n")
        critical_issues = report.get_issues_by_severity(Severity.CRITICAL)
        for i, issue in enumerate(critical_issues, 1):
            lines.append(f"### {i}. {issue.name}")
            lines.append(f"- **Description**: {issue.description}")
            lines.append(f"- **Recommendation**: {issue.recommendation}")
            if issue.details:
                lines.append(f"- **Details**: {issue.details}\n")
            else:
                lines.append("")

    if report.summary.warning_count > 0:
        lines.append("## Warnings\n")
        warning_issues = report.get_issues_by_severity(Severity.WARNING)
        for i, issue in enumerate(warning_issues, 1):
            lines.append(f"### {i}. {issue.name}")
            lines.append(f"- **Description**: {issue.description}")
            lines.append(f"- **Recommendation**: {issue.recommendation}")
            if issue.details:
                lines.append(f"- **Details**: {issue.details}\n")
            else:
                lines.append("")

    if report.data and report.data.cluster:
        lines.append("## Cluster Health\n")
        cluster = report.data.cluster
        lines.append(f"- **Status**: {cluster.status}")
        lines.append(f"- **Nodes**: {cluster.number_of_nodes}")
        lines.append(f"- **Active Shards**: {cluster.active_shards}")
        lines.append(f"- **Unassigned Shards**: {cluster.unassigned_shards}")
        lines.append(f"- **Pending Tasks**: {cluster.pending_tasks}\n")

    if report.data and report.data.nodes:
        lines.append("## Node Health\n")
        lines.append("| Node | Heap % | CPU % | Disk % | Rejections |")
        lines.append("|------|--------|-------|--------|-----------|")
        for node in report.data.nodes:
            rejs = sum(node.thread_pool_rejections.values()) if node.thread_pool_rejections else 0
            lines.append(f"| {node.name} | {node.heap_used_percent or 'N/A'}% | {node.cpu_percent or 'N/A'}% | {node.disk_used_percent or 'N/A'}% | {rejs} |")
        lines.append("")

    if report.data and report.data.indices:
        lines.append("## Index Health\n")
        red_indices = [idx for idx in report.data.indices if idx.health == 'red']
        yellow_indices = [idx for idx in report.data.indices if idx.health == 'yellow']
        green_indices = [idx for idx in report.data.indices if idx.health == 'green']

        lines.append(f"- **Green Indices**: {len(green_indices)}")
        lines.append(f"- **Yellow Indices**: {len(yellow_indices)}")
        lines.append(f"- **Red Indices**: {len(red_indices)}\n")

    return "\n".join(lines)


def _get_status_emoji(status: str) -> str:
    """Get emoji for cluster status."""
    if status == 'green':
        return '✅'
    elif status == 'yellow':
        return '⚠️'
    elif status == 'red':
        return '❌'
    return '❓'
