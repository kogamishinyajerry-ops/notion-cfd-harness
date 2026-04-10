#!/usr/bin/env python3
"""
Phase 9 Correction Callback Endpoint

D-09: Inline HTML correction mechanism.
Processes /correct?record=<id>&field=<f>&value=<v> query params,
records corrections to CorrectionRecorder.

D-07: Errors logged but do NOT block pipeline.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from knowledge_compiler.phase2c.correction_recorder import (
    CorrectionRecorder,
    CorrectionRecord,
)
from knowledge_compiler.phase1.schema import (
    ErrorType,
    ImpactScope,
)

logger = logging.getLogger(__name__)


class FailureContext:
    """Minimal FailureContext for correction recording"""
    def __init__(self):
        self.validation_result = type('obj', (object,), {
            'validation_id': f'REPORT-{int(time.time())}',
            'anomalies': []
        })()
        self.attempt_count = 1
        self.metadata: Dict[str, Any] = {}


class FailureHandlingResult:
    """Minimal FailureHandlingResult for correction recording"""
    def __init__(self, message: str = "", action: str = "corrected"):
        self.message = message
        self.action = type('obj', (object,), {'value': action})()
        self.retry_with: Dict[str, Any] = {}


@dataclass
class CorrectionCallback:
    """
    Handles inline correction requests from HTML report.

    D-09: User clicks value in HTML -> query param -> CorrectionCallback -> CorrectionRecorder
    """
    storage_path: str = "data/corrections"

    def __post_init__(self):
        self.recorder = CorrectionRecorder(storage_path=self.storage_path)

    def process_correction(
        self,
        record_id: str,
        field_name: str,
        corrected_value: Any,
        engineer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a correction request from inline HTML.

        Args:
            record_id: Report result ID being corrected
            field_name: Field name being corrected (e.g., "max_u_centerline_sim")
            corrected_value: The correct value
            engineer_id: Optional engineer identifier

        Returns:
            Dict with status, correction_id, message
        """
        try:
            # Build spec_output for record_from_generator
            spec_output = {
                "suggested_actions": [f"Corrected {field_name} from report"],
                "retry_with": {},
                "validation_result": {
                    "field_name": field_name,
                    "corrected_value": corrected_value,
                    "source": "report_inline_correction",
                },
            }

            # Build FailureContext
            context = FailureContext()
            context.metadata["source_report_id"] = record_id
            context.metadata["corrected_field"] = field_name

            # Build FailureHandlingResult
            handling_result = FailureHandlingResult(
                message=f"Inline correction: {field_name} = {corrected_value}",
                action="corrected",
            )

            # Record the correction
            correction_record = self.recorder.record_from_generator(
                spec_generator_output=spec_output,
                context=context,
                handling_result=handling_result,
                human_reason=f"Inline correction from report {record_id}: {field_name}",
                engineer_id=engineer_id,
            )

            # Validate
            violations = self.recorder.validate(correction_record)
            if violations:
                logger.warning(f"Correction validation warnings: {violations}")

            # Save
            filepath = self.recorder.save(correction_record)

            logger.info(f"Correction recorded: {correction_record.record_id} -> {filepath}")

            return {
                "status": "recorded",
                "correction_id": correction_record.record_id,
                "filepath": filepath,
                "violations": violations,
            }

        except Exception as e:
            logger.error(f"Correction recording failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
            }


def process_correction_request(
    record_id: str,
    field_name: str,
    value: str,
    engineer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Standalone function for processing correction requests.

    Called by web endpoint: /correct?record=<id>&field=<f>&value=<v>
    """
    callback = CorrectionCallback()

    # Try to parse value as appropriate type
    corrected_value: Any = value
    try:
        if "." in value:
            corrected_value = float(value)
        else:
            corrected_value = int(value)
    except ValueError:
        pass  # Keep as string

    return callback.process_correction(
        record_id=record_id,
        field_name=field_name,
        corrected_value=corrected_value,
        engineer_id=engineer_id,
    )
