#!/usr/bin/env python3
"""
Phase 2 Teach Layer: Capture Module

从 Phase 1 Output 中提取 TeachCapture 对象。
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from knowledge_compiler.phase1.schema import (
    ProblemType,
    ReportSpec,
    CorrectionSpec,
    TeachRecord,
    TeachOperation,
    Phase1Output,
)
from knowledge_compiler.phase2.schema import (
    CaptureContext,
    TeachCapture,
)


class TeachCaptureExtractor:
    """
    TeachCapture 提取器

    从 Phase1Output 中提取 TeachCapture 对象。
    """

    def __init__(self, engineer_id: Optional[str] = None):
        """
        Initialize the extractor

        Args:
            engineer_id: 工程师 ID，用于标记捕获来源
        """
        self.engineer_id = engineer_id

    def extract_captures(
        self,
        phase1_output: Phase1Output,
    ) -> List[TeachCapture]:
        """
        从 Phase1Output 中提取所有 TeachCapture

        Args:
            phase1_output: Phase 1 的输出

        Returns:
            TeachCapture 列表
        """
        captures = []

        # 从 TeachRecord 中提取
        for teach_record in phase1_output.teach_records:
            capture = self._extract_from_teach_record(teach_record)
            if capture:
                captures.append(capture)

        # 从 ReportSpec 中关联的 TeachRecord 提取
        for report_spec in phase1_output.report_specs:
            associated_captures = self._extract_from_report_spec(report_spec)
            captures.extend(associated_captures)

        # 从 CorrectionSpec 中关联的 TeachRecord 提取
        for correction_spec in phase1_output.correction_specs:
            associated_captures = self._extract_from_correction_spec(correction_spec)
            captures.extend(associated_captures)

        return captures

    def _extract_from_teach_record(
        self,
        teach_record: TeachRecord,
    ) -> Optional[TeachCapture]:
        """
        从单个 TeachRecord 提取 TeachCapture

        Args:
            teach_record: Phase 1 的 TeachRecord

        Returns:
            TeachCapture 或 None
        """
        # 提取上下文信息
        # TeachRecord 没有 solver_type 属性，使用默认值
        context = CaptureContext(
            case_id=teach_record.case_id or "unknown",
            solver_type="openfoam",  # 默认求解器类型
            problem_type=self._infer_problem_type(teach_record),
            timestamp=teach_record.timestamp or time.time(),
            engineer_id=self.engineer_id,
            session_id=getattr(teach_record, "session_id", None),
        )

        # 创建 TeachCapture
        capture = TeachCapture(
            source_case_id=context.case_id,
            context=context,
            capture_id=getattr(teach_record, "capture_id", None) or f"CAPTURE-{uuid.uuid4().hex[:8]}",
            raw_operations=teach_record.operations or [],
            source_report_spec=None,
            source_correction_specs=[],
            captured_at=teach_record.timestamp or time.time(),
            metadata={
                "engineer_id": self.engineer_id,
                "original_record_id": getattr(teach_record, "teach_record_id", None),
            },
        )

        return capture

    def _extract_from_report_spec(
        self,
        report_spec: ReportSpec,
    ) -> List[TeachCapture]:
        """
        从 ReportSpec 关联中提取 TeachCapture

        Args:
            report_spec: ReportSpec 实例

        Returns:
            TeachCapture 列表
        """
        captures = []

        # 如果 ReportSpec 有关联的 TeachRecord
        if hasattr(report_spec, "associated_teach_records"):
            for teach_record in report_spec.associated_teach_records:
                capture = self._extract_from_teach_record(teach_record)
                if capture:
                    # 关联 ReportSpec
                    capture.source_report_spec = report_spec
                    captures.append(capture)

        return captures

    def _extract_from_correction_spec(
        self,
        correction_spec: CorrectionSpec,
    ) -> List[TeachCapture]:
        """
        从 CorrectionSpec 关联中提取 TeachCapture

        Args:
            correction_spec: CorrectionSpec 实例

        Returns:
            TeachCapture 列表
        """
        captures = []

        # 如果 CorrectionSpec 有关联的 TeachRecord
        if hasattr(correction_spec, "associated_teach_records"):
            for teach_record in correction_spec.associated_teach_records:
                capture = self._extract_from_teach_record(teach_record)
                if capture:
                    # 关联 CorrectionSpec
                    capture.source_correction_specs.append(correction_spec)
                    captures.append(capture)

        return captures

    def _infer_problem_type(self, teach_record: TeachRecord) -> ProblemType:
        """
        推断问题类型

        Args:
            teach_record: TeachRecord 实例

        Returns:
            推断的 ProblemType
        """
        # 如果 TeachRecord 有明确的 problem_type
        if hasattr(teach_record, "problem_type") and teach_record.problem_type:
            if isinstance(teach_record.problem_type, ProblemType):
                return teach_record.problem_type
            # 如果是字符串，尝试转换
            try:
                return ProblemType(teach_record.problem_type)
            except (ValueError, KeyError):
                pass

        # 从 operation 类型推断
        if teach_record.operations:
            # 检查第一个 operation 的上下文
            first_op = teach_record.operations[0]
            if hasattr(first_op, "problem_type") and first_op.problem_type:
                try:
                    return ProblemType(first_op.problem_type)
                except (ValueError, KeyError):
                    pass

        # 默认返回 INTERNAL_FLOW
        return ProblemType.INTERNAL_FLOW


def extract_captures(
    phase1_output: Phase1Output,
    engineer_id: Optional[str] = None,
) -> List[TeachCapture]:
    """
    便捷函数：从 Phase1Output 提取所有 TeachCapture

    Args:
        phase1_output: Phase 1 的输出
        engineer_id: 工程师 ID

    Returns:
        TeachCapture 列表
    """
    extractor = TeachCaptureExtractor(engineer_id=engineer_id)
    return extractor.extract_captures(phase1_output)


def capture_teach_session(
    case_id: str,
    solver_type: str,
    problem_type: ProblemType,
    operations: List[TeachOperation],
    engineer_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> TeachCapture:
    """
    便捷函数：捕获一个教学会话

    Args:
        case_id: Case ID
        solver_type: 求解器类型
        problem_type: 问题类型
        operations: 操作列表
        engineer_id: 工程师 ID
        session_id: 会话 ID

    Returns:
        TeachCapture 对象
    """
    context = CaptureContext(
        case_id=case_id,
        solver_type=solver_type,
        problem_type=problem_type,
        timestamp=time.time(),
        engineer_id=engineer_id,
        session_id=session_id,
    )

    capture = TeachCapture(
        source_case_id=case_id,
        context=context,
        raw_operations=operations,
        metadata={"engineer_id": engineer_id},
    )

    return capture


__all__ = [
    "TeachCaptureExtractor",
    "extract_captures",
    "capture_teach_session",
]
