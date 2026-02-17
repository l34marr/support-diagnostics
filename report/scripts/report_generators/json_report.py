"""
JSON report generator.
"""

import json
from typing import Dict, Any
from data_models import HealthReport


def generate_json_report(report: HealthReport) -> str:
    """
    Generate JSON formatted health report.

    Returns complete JSON string.
    """
    report_dict = report.to_dict()
    return json.dumps(report_dict, indent=2, default=str)


def save_json_report(report: HealthReport, output_path: str):
    """
    Save JSON report to file.

    Args:
        report: Health report object
        output_path: Path to output file
    """
    report_json = generate_json_report(report)

    with open(output_path, 'w') as f:
        f.write(report_json)

    return output_path
