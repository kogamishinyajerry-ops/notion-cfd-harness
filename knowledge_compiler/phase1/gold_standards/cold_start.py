#!/usr/bin/env python3
"""
Phase 1: Cold Start Whitelist Loader

加载 AI-CFD 冷启动白名单，提供算例注册和检索功能。
白名单包含 30 个来自 OpenFOAM/SU2 官方 tutorial 的高质量 CFD 算例。

组件:
- ColdStartCase: 单个白名单算例
- ColdStartWhitelist: 白名单容器
- load_cold_start_whitelist(): YAML 加载函数
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 白名单 YAML 默认路径
_DEFAULT_WHITELIST_PATH = Path(__file__).parent.parent.parent.parent / "data" / "cold_start_whitelist.yaml"


# ============================================================================
# ColdStartCase
# ============================================================================

@dataclass
class ColdStartCase:
    """单个冷启动白名单算例

    Attributes:
        id: 算例唯一标识 (e.g. "OF-01", "SU2-01")
        rank: 执行优先级 (1=最高)
        platform: 求解器平台 ("OpenFOAM" | "SU2")
        tier: 分类层级 ("core_seed" | "bridge" | "breadth")
        dimension: 维度 ("2D" | "3D" | "2D_or_quasi_2D")
        difficulty: 难度 ("basic" | "intermediate" | "advanced")
        case_name: 算例名称
        source_location: 来源信息 (local_case_path, repo_case_dir, tutorial_page)
        source_provenance: 来源证明
        verification_basis: 验证依据
        mesh_strategy: 网格策略 ("A"=ready_mesh, "B"=script_built)
        mesh_details: 网格详情
        solver_command: 求解器执行命令
        success_criteria: 成功标准
        why_whitelisted: 入选理由
    """

    id: str
    rank: int
    platform: str
    tier: str
    dimension: str
    difficulty: str
    case_name: str
    source_location: Dict[str, str] = field(default_factory=dict)
    source_provenance: str = ""
    verification_basis: str = ""
    mesh_strategy: str = ""
    mesh_details: str = ""
    solver_command: str = ""
    success_criteria: str = ""
    why_whitelisted: str = ""

    @property
    def is_core_seed(self) -> bool:
        return self.tier == "core_seed"

    @property
    def has_ready_mesh(self) -> bool:
        return self.mesh_strategy == "A"


# ============================================================================
# ColdStartWhitelist
# ============================================================================

@dataclass
class ColdStartWhitelist:
    """冷启动白名单容器

    包含多个 ColdStartCase 实例，提供过滤和检索方法。
    """

    name: str
    version: str
    cases: List[ColdStartCase] = field(default_factory=list)

    # ── 过滤方法 ──

    def core_seeds(self) -> List[ColdStartCase]:
        """返回所有 core_seed 层级的算例"""
        return [c for c in self.cases if c.is_core_seed]

    def by_platform(self, platform: str) -> List[ColdStartCase]:
        """按平台过滤"""
        return [c for c in self.cases if c.platform.lower() == platform.lower()]

    def by_tier(self, tier: str) -> List[ColdStartCase]:
        """按层级过滤"""
        return [c for c in self.cases if c.tier == tier]

    def by_difficulty(self, difficulty: str) -> List[ColdStartCase]:
        """按难度过滤"""
        return [c for c in self.cases if c.difficulty == difficulty]

    def ready_mesh_cases(self) -> List[ColdStartCase]:
        """返回所有提供现成网格的算例"""
        return [c for c in self.cases if c.has_ready_mesh]

    def sorted_by_rank(self) -> List[ColdStartCase]:
        """按执行优先级排序"""
        return sorted(self.cases, key=lambda c: c.rank)

    def get_by_id(self, case_id: str) -> Optional[ColdStartCase]:
        """按 ID 查找算例"""
        for c in self.cases:
            if c.id == case_id:
                return c
        return None

    # ── 统计方法 ──

    @property
    def total_count(self) -> int:
        return len(self.cases)

    @property
    def platform_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for c in self.cases:
            counts[c.platform] = counts.get(c.platform, 0) + 1
        return counts

    @property
    def tier_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for c in self.cases:
            counts[c.tier] = counts.get(c.tier, 0) + 1
        return counts


# ============================================================================
# YAML Loader
# ============================================================================

def load_cold_start_whitelist(
    path: Optional[str] = None,
) -> ColdStartWhitelist:
    """从 YAML 文件加载冷启动白名单

    Args:
        path: YAML 文件路径（None=使用默认路径）

    Returns:
        ColdStartWhitelist 实例

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: YAML 格式错误
    """
    yaml_path = Path(path) if path else _DEFAULT_WHITELIST_PATH

    if not yaml_path.exists():
        raise FileNotFoundError(f"冷启动白名单文件不存在: {yaml_path}")

    try:
        import yaml
    except ImportError:
        raise ImportError("需要 PyYAML: pip install pyyaml")

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "cases" not in data:
        raise ValueError(f"无效的白名单 YAML: 缺少 'cases' 字段")

    cases = []
    for entry in data["cases"]:
        case = ColdStartCase(
            id=entry["id"],
            rank=entry["rank"],
            platform=entry["platform"],
            tier=entry["tier"],
            dimension=entry["dimension"],
            difficulty=entry["difficulty"],
            case_name=entry["case_name"],
            source_location=entry.get("source_location", {}),
            source_provenance=entry.get("source_provenance", ""),
            verification_basis=entry.get("verification_basis", ""),
            mesh_strategy=entry.get("mesh_strategy", ""),
            mesh_details=entry.get("mesh_details", ""),
            solver_command=entry.get("solver_command", ""),
            success_criteria=entry.get("success_criteria", ""),
            why_whitelisted=entry.get("why_whitelisted", ""),
        )
        cases.append(case)

    whitelist = ColdStartWhitelist(
        name=data.get("whitelist_name", "unknown"),
        version=data.get("version", "unknown"),
        cases=cases,
    )

    logger.info(
        "加载冷启动白名单: %s v%s, %d 个算例",
        whitelist.name,
        whitelist.version,
        whitelist.total_count,
    )

    return whitelist


__all__ = [
    "ColdStartCase",
    "ColdStartWhitelist",
    "load_cold_start_whitelist",
]
