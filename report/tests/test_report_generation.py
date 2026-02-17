"""
Tests for report generation.
"""

import pytest
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from data_models import HealthReport, HealthSummary, Severity, HealthCheck
from report_generators.markdown import generate_markdown_report
from report_generators.json_report import generate_json_report, save_json_report
from datetime import datetime


@pytest.fixture
def sample_report():
    """Create sample health report for testing."""
    summary = HealthSummary(
        score=75,
        critical_count=2,
        warning_count=3,
        info_count=1,
        total_checks=6,
    )

    issues = [
        HealthCheck(
            name='critical_issue_1',
            severity=Severity.CRITICAL,
            category='cluster',
            description='Critical issue 1',
            evidence={'value': 95},
            recommendation='Fix immediately',
            failed=True,
        ),
        HealthCheck(
            name='warning_issue_1',
            severity=Severity.WARNING,
            category='node',
            description='Warning issue 1',
            evidence={'value': 80},
            recommendation='Monitor closely',
            failed=True,
        ),
        HealthCheck(
            name='info_issue_1',
            severity=Severity.INFO,
            category='index',
            description='Info issue 1',
            evidence={'count': 5},
            recommendation='Consider optimization',
            failed=True,
        ),
    ]

    return HealthReport(
        timestamp='2026-01-19T10:00:00Z',
        cluster_name='test-cluster',
        summary=summary,
        issues=issues,
    )


def test_generate_markdown_report():
    """Test Markdown report generation."""
    report = sample_report()

    markdown = generate_markdown_report(report)

    assert '# Cluster Health Check Report' in markdown
    assert '**Generated**: 2026-01-19T10:00:00Z' in markdown
    assert 'Critical Issues: 2' in markdown
    assert 'Warnings: 3' in markdown
    assert 'Overall Score: 75/100' in markdown


def test_generate_json_report():
    """Test JSON report generation."""
    report = sample_report()

    json_str = generate_json_report(report)

    assert '"cluster_name": "test-cluster"' in json_str
    assert '"score": 75' in json_str
    assert '"critical_count": 2' in json_str
    assert '"warning_count": 3' in json_str


def test_save_json_report():
    """Test saving JSON report to file."""
    report = sample_report()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'health_report.json'

        result_path = save_json_report(report, str(output_path))

        assert result_path == str(output_path)
        assert output_path.exists()

        with open(output_path, 'r') as f:
            content = f.read()
            assert '"cluster_name": "test-cluster"' in content


def test_empty_report():
    """Test report generation with empty data."""
    summary = HealthSummary(
        score=100,
        critical_count=0,
        warning_count=0,
        info_count=0,
        total_checks=0,
    )

    report = HealthReport(
        timestamp=datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        cluster_name='test-cluster',
        summary=summary,
        issues=[],
        data=None,
    )

    markdown = generate_markdown_report(report)

    assert '# Cluster Health Check Report' in markdown
    assert 'Overall Score: 100/100' in markdown
    assert 'No issues detected' not in markdown or 'Critical Issues: 0' in markdown


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
