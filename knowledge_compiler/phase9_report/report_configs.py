"""
ReportConfig dataclass for Phase 9 ReportGenerator
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple


@dataclass
class ReportConfig:
    """
    Configuration for CFD report generation.

    Attributes:
        output_dir: Directory for generated reports
        dpi: Chart DPI for HTML embedding (D-08: self-contained)
        precision_threshold: % error threshold for PASS/WARN/FAIL
        chart_figsize: matplotlib figure size tuple
        template_name: Jinja2 template filename
    """

    output_dir: str = "knowledge_compiler/reports"
    dpi: int = 150
    precision_threshold: float = 5.0
    chart_figsize: Tuple[int, int] = (10, 6)
    template_name: str = "report_template.html"

    def __post_init__(self) -> None:
        """Ensure output directory exists."""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
