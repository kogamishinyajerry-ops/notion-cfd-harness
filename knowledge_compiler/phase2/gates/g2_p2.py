#!/usr/bin/env python3
"""
Phase 2 Gate G2-P2: Authorization Gate

验证知识发布的权限和批准流程。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from knowledge_compiler.phase2.gates.gates import (
    GateStatus,
    GateCheckItem,
    GateResult,
)


G2_P2_GATE_ID = "G2-P2"


class AuthStatus(Enum):
    """授权状态"""
    PENDING = "pending"           # 待授权
    REQUESTED = "requested"       # 已请求授权
    APPROVED = "approved"         # 已批准
    REJECTED = "rejected"         # 已拒绝
    AUTO_APPROVED = "auto_approved"  # 自动批准（低风险知识）


@dataclass
class AuthRequest:
    """授权请求"""
    request_id: str
    spec_id: str
    requester: str  # engineer_id
    risk_level: str  # low, medium, high
    timestamp: float
    status: AuthStatus
    approvers: List[str]  # required approvers
    comments: List[str] = None

    def is_approved(self) -> bool:
        """检查是否已批准"""
        return self.status == AuthStatus.APPROVED


class AuthorizationGate:
    """
    G2-P2: 授权 Gate

    验证知识发布的权限和批准流程。

    这是 Phase 2 的 BLOCK 级别 Gate，未授权的知识不能发布。
    """

    GATE_ID = G2_P2_GATE_ID
    GATE_NAME = "Authorization Gate"

    # 风险等级阈值
    AUTO_APPROVE_THRESHOLD = 0.7  # 置信度高于此值可自动批准
    HIGH_RISK_THRESHOLD = 0.5    # 置信度低于此值需要高级授权

    # 自动批准的条件
    AUTO_APPROVE_CONDITIONS = {
        "is_bug_fix": True,              # Bug 修复可自动批准
        "is_documentation_only": True,   # 仅文档更新可自动批准
        "confidence": 0.8,                # 高置信度可自动批准
        "has_teach_backup": True,        # 有教学记录可自动批准
    }

    def __init__(self, strict_mode: bool = True):
        """
        Initialize the gate

        Args:
            strict_mode: 如果为 True，所有发布需要授权；False 则允许自动批准低风险知识
        """
        self.strict_mode = strict_mode
        self._pending_requests: List[AuthRequest] = []

    def check(self, spec: "CanonicalSpec", context: Dict[str, Any] = None) -> GateResult:
        """
        检查单个 CanonicalSpec 的授权状态

        Args:
            spec: CanonicalSpec 实例
            context: 额外上下文信息（如 risk_level, confidence）

        Returns:
            GateResult 检查结果
        """
        checklist = []
        errors = []
        warnings = []
        score = 100.0

        spec_id = getattr(spec, "spec_id", "unknown")

        # 检查授权状态
        auth_status = self._get_auth_status(spec, context or {})

        # Check 1: 是否有有效的授权请求
        checklist.append(GateCheckItem(
            item="auth_request",
            description="Valid authorization request exists",
            result=GateStatus.PASS if auth_status != AuthStatus.PENDING else GateStatus.FAIL,
            message=f"Authorization status: {auth_status.value}",
        ))

        if auth_status == AuthStatus.PENDING:
            errors.append("Authorization pending")
            score -= 50.0
        elif auth_status == AuthStatus.REJECTED:
            errors.append("Authorization rejected")
            score -= 100.0

        # Check 2: 风险等级评估
        risk_level = self._assess_risk_level(spec, context or {})
        checklist.append(GateCheckItem(
            item="risk_assessment",
            description=f"Risk level: {risk_level}",
            result=GateStatus.PASS if risk_level != "high" else GateStatus.WARN,
            message=f"Risk level assessed as {risk_level}",
        ))

        if risk_level == "high":
            warnings.append("High risk knowledge requires senior approval")
            score -= 25.0
        elif risk_level == "medium":
            score -= 10.0

        # Check 3: 置信度评估
        confidence = self._extract_confidence(spec, context or {})
        checklist.append(GateCheckItem(
            item="confidence_check",
            description=f"Confidence: {confidence}",
            result=GateStatus.PASS if confidence >= 0.5 else GateStatus.WARN,
            message=f"Confidence: {confidence}",
        ))

        if confidence < 0.5:
            warnings.append("Low confidence knowledge requires verification")
            score -= 15.0

        # Check 4: 来源追踪
        source_teach_ids = getattr(spec, "source_teach_ids", [])
        source_case_ids = getattr(spec, "source_case_ids", [])

        if source_teach_ids or source_case_ids:
            checklist.append(GateCheckItem(
                item="source_tracking",
                description="Source tracking exists",
                result=GateStatus.PASS,
                message=f"Tracked from {len(source_teach_ids)} teachings, {len(source_case_ids)} cases",
            ))
        else:
            warnings.append("No source tracking - knowledge has no provenance")
            score -= 20.0

        # Check 5: 自动批准条件检查（非 strict 模式）
        can_auto_approve = self._check_auto_approve(spec, context or {})
        if not self.strict_mode and can_auto_approve:
            checklist.append(GateCheckItem(
                item="auto_approve",
                description="Auto-approve conditions met",
                result=GateStatus.PASS,
                message="Knowledge qualifies for auto-approval",
            ))
        elif self.strict_mode:
            checklist.append(GateCheckItem(
                item="auto_approve",
                description="Auto-approve check",
                result=GateStatus.WARN,
                message="Strict mode: auto-approval disabled",
            ))

        # 确定最终状态
        status = GateStatus.PASS
        if score < 50.0 or (auth_status == AuthStatus.REJECTED):
            status = GateStatus.FAIL
        elif score < 75.0:
            status = GateStatus.WARN

        return GateResult(
            gate_id=self.GATE_ID,
            gate_name=self.GATE_NAME,
            status=status,
            timestamp=time.time(),
            score=max(0.0, score),
            checklist=checklist,
            errors=errors,
            warnings=warnings,
            metadata={
                "spec_id": spec_id,
                "auth_status": auth_status.value,
                "risk_level": risk_level,
                "confidence": confidence,
                "strict_mode": self.strict_mode,
            },
            severity="BLOCK",
        )

    def create_auth_request(
        self,
        spec: "CanonicalSpec",
        requester: str,
        risk_level: str = "medium",
        approvers: Optional[List[str]] = None,
    ) -> AuthRequest:
        """
        创建授权请求

        Args:
            spec: CanonicalSpec 实例
            requester: 请求者 ID
            risk_level: 风险等级 (low, medium, high)
            approvers: 批准者列表

        Returns:
            AuthRequest 授权请求
        """
        request = AuthRequest(
            request_id=f"AUTH-{spec.spec_id}-{int(time.time())}",
            spec_id=spec.spec_id,
            requester=requester,
            risk_level=risk_level,
            timestamp=time.time(),
            status=AuthStatus.REQUESTED,
            approvers=approvers or [],
            comments=[],
        )

        self._pending_requests.append(request)
        return request

    def approve_request(self, request_id: str, approver: str, comment: str = "") -> bool:
        """
        批准授权请求

        Args:
            request_id: 授权请求 ID
            approver: 批准者 ID
            comment: 批准意见

        Returns:
            是否成功批准
        """
        for request in self._pending_requests:
            if request.request_id == request_id:
                request.status = AuthStatus.APPROVED
                if comment:
                    if request.comments is None:
                        request.comments = []
                    request.comments.append(f"Approved by {approver}: {comment}")
                return True
        return False

    def reject_request(self, request_id: str, approver: str, reason: str) -> bool:
        """
        拒绝授权请求

        Args:
            request_id: 授权请求 ID
            approver: 拒绝者 ID
            reason: 拒绝原因

        Returns:
            是否成功拒绝
        """
        for request in self._pending_requests:
            if request.request_id == request_id:
                request.status = AuthStatus.REJECTED
                if request.comments is None:
                    request.comments = []
                request.comments.append(f"Rejected by {approver}: {reason}")
                return True
        return False

    def _get_auth_status(self, spec: "CanonicalSpec", context: Dict) -> AuthStatus:
        """获取授权状态"""
        # 检查是否有授权请求
        for request in self._pending_requests:
            if request.spec_id == spec.spec_id:
                return request.status

        # 检查是否可以自动批准
        if not self.strict_mode:
            can_auto_approve = self._check_auto_approve(spec, context)
            if can_auto_approve:
                return AuthStatus.AUTO_APPROVED

        return AuthStatus.PENDING

    def _assess_risk_level(self, spec: "CanonicalSpec", context: Dict) -> str:
        """评估风险等级"""
        # 检查 knowledge_status
        status = getattr(spec, "knowledge_status", None)
        if status and hasattr(status, "value"):
            if status.value in ["approved", "canonical"]:
                return "low"

        # 检查来源数量
        source_count = len(getattr(spec, "source_teach_ids", []))
        if source_count >= 3:
            return "low"
        elif source_count >= 1:
            return "medium"
        else:
            return "high"

    def _extract_confidence(self, spec: "CanonicalSpec", context: Dict) -> float:
        """提取置信度"""
        # 从上下文中提取置信度
        if "confidence" in context:
            return float(context["confidence"])

        # 从来源数量推断置信度
        source_count = len(getattr(spec, "source_teach_ids", []))
        return min(1.0, source_count * 0.3 + 0.1)

    def _check_auto_approve(self, spec: "CanonicalSpec", context: Dict) -> bool:
        """检查是否可以自动批准"""
        conditions = self.AUTO_APPROVE_CONDITIONS.copy()

        # 检查上下文中的条件
        if "is_bug_fix" in context and context["is_bug_fix"]:
            conditions["is_bug_fix"] = True
        if "is_documentation_only" in context and context["is_documentation_only"]:
            conditions["is_documentation_only"] = True

        # 检查置信度
        confidence = self._extract_confidence(spec, context)
        conditions["confidence"] = confidence >= self.AUTO_APPROVE_THRESHOLD

        # 检查教学备份
        source_count = len(getattr(spec, "source_teach_ids", []))
        conditions["has_teach_backup"] = source_count > 0

        # 所有条件都满足才自动批准
        return all(conditions.values())


# Export
__all__ = [
    "AuthorizationGate",
    "G2_P2_GATE_ID",
    "AuthStatus",
    "AuthRequest",
]
