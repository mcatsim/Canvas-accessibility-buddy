"""Standards mapping for WCAG 2.1, Section 508, and VPAT reporting."""

from canvas_a11y.standards.wcag21 import WCAG_CRITERIA, WCAGCriterion
from canvas_a11y.standards.section508 import SECTION_508_PROVISIONS, Section508Provision
from canvas_a11y.standards.mapping import (
    CHECK_STANDARDS_MAP,
    StandardsMapping,
    get_standards_for_check,
)
from canvas_a11y.standards.vpat import VPATReport, VPATRow, build_vpat

__all__ = [
    "WCAG_CRITERIA",
    "WCAGCriterion",
    "SECTION_508_PROVISIONS",
    "Section508Provision",
    "CHECK_STANDARDS_MAP",
    "StandardsMapping",
    "get_standards_for_check",
    "VPATReport",
    "VPATRow",
    "build_vpat",
]
