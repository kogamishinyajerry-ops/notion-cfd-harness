#!/usr/bin/env python3
"""
Tests for Cold Start Whitelist

验证白名单 YAML 加载、过滤和统计功能。
"""

import pytest
from pathlib import Path

from knowledge_compiler.phase1.gold_standards.cold_start import (
    ColdStartCase,
    ColdStartWhitelist,
    load_cold_start_whitelist,
)


# ============================================================================
# YAML 加载
# ============================================================================

class TestLoadWhitelist:
    def test_load_default_path(self):
        """默认路径加载成功"""
        wl = load_cold_start_whitelist()
        assert isinstance(wl, ColdStartWhitelist)
        assert wl.total_count == 30

    def test_load_explicit_path(self):
        """指定路径加载"""
        path = str(Path(__file__).parent.parent / "data" / "cold_start_whitelist.yaml")
        wl = load_cold_start_whitelist(path=path)
        assert wl.total_count == 30

    def test_load_nonexistent_raises(self):
        """文件不存在抛 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            load_cold_start_whitelist(path="/nonexistent/file.yaml")

    def test_whitelist_metadata(self):
        wl = load_cold_start_whitelist()
        assert wl.name == "ai_cfd_cold_start_official_tutorial_whitelist"
        assert wl.version == "v1"


# ============================================================================
# 算例字段
# ============================================================================

class TestColdStartCaseFields:
    def test_first_case_fields(self):
        wl = load_cold_start_whitelist()
        first = wl.sorted_by_rank()[0]
        assert first.id == "OF-01"
        assert first.platform == "OpenFOAM"
        assert first.tier == "core_seed"
        assert first.case_name == "lid_driven_cavity"

    def test_su2_case_fields(self):
        wl = load_cold_start_whitelist()
        su2_01 = wl.get_by_id("SU2-01")
        assert su2_01 is not None
        assert su2_01.platform == "SU2"
        assert su2_01.mesh_strategy == "A"

    def test_all_cases_have_required_fields(self):
        wl = load_cold_start_whitelist()
        for case in wl.cases:
            assert case.id, f"Missing id"
            assert case.rank > 0, f"{case.id}: rank must be positive"
            assert case.platform in ("OpenFOAM", "SU2"), f"{case.id}: invalid platform"
            assert case.tier in ("core_seed", "bridge", "breadth"), f"{case.id}: invalid tier"
            assert case.case_name, f"{case.id}: missing case_name"


# ============================================================================
# 过滤方法
# ============================================================================

class TestFiltering:
    def test_core_seeds(self):
        wl = load_cold_start_whitelist()
        seeds = wl.core_seeds()
        assert len(seeds) == 13
        assert all(c.is_core_seed for c in seeds)

    def test_by_platform_openfoam(self):
        wl = load_cold_start_whitelist()
        of_cases = wl.by_platform("OpenFOAM")
        assert len(of_cases) == 6
        assert all(c.platform == "OpenFOAM" for c in of_cases)

    def test_by_platform_su2(self):
        wl = load_cold_start_whitelist()
        su2_cases = wl.by_platform("SU2")
        assert len(su2_cases) == 24

    def test_by_tier(self):
        wl = load_cold_start_whitelist()
        bridge = wl.by_tier("bridge")
        breadth = wl.by_tier("breadth")
        assert len(bridge) == 8
        assert len(breadth) == 9

    def test_ready_mesh_cases(self):
        wl = load_cold_start_whitelist()
        ready = wl.ready_mesh_cases()
        # SU2 cases mostly have ready meshes (strategy A)
        assert all(c.mesh_strategy == "A" for c in ready)

    def test_sorted_by_rank(self):
        wl = load_cold_start_whitelist()
        sorted_cases = wl.sorted_by_rank()
        ranks = [c.rank for c in sorted_cases]
        assert ranks == sorted(ranks)
        assert ranks[0] == 1

    def test_get_by_id(self):
        wl = load_cold_start_whitelist()
        case = wl.get_by_id("OF-03")
        assert case is not None
        assert case.case_name == "cylinder_crossflow"

    def test_get_by_id_not_found(self):
        wl = load_cold_start_whitelist()
        assert wl.get_by_id("NONEXISTENT") is None


# ============================================================================
# 统计方法
# ============================================================================

class TestStatistics:
    def test_platform_counts(self):
        wl = load_cold_start_whitelist()
        counts = wl.platform_counts
        assert counts["OpenFOAM"] == 6
        assert counts["SU2"] == 24

    def test_tier_counts(self):
        wl = load_cold_start_whitelist()
        counts = wl.tier_counts
        assert counts["core_seed"] == 13
        assert counts["bridge"] == 8
        assert counts["breadth"] == 9

    def test_total_count(self):
        wl = load_cold_start_whitelist()
        assert wl.total_count == 30


# ============================================================================
# ColdStartCase 属性
# ============================================================================

class TestColdStartCaseProperties:
    def test_is_core_seed_true(self):
        case = ColdStartCase(id="T", rank=1, platform="SU2", tier="core_seed",
                             dimension="2D", difficulty="basic", case_name="test")
        assert case.is_core_seed is True

    def test_is_core_seed_false(self):
        case = ColdStartCase(id="T", rank=1, platform="SU2", tier="bridge",
                             dimension="2D", difficulty="basic", case_name="test")
        assert case.is_core_seed is False

    def test_has_ready_mesh_true(self):
        case = ColdStartCase(id="T", rank=1, platform="SU2", tier="core_seed",
                             dimension="2D", difficulty="basic", case_name="test",
                             mesh_strategy="A")
        assert case.has_ready_mesh is True

    def test_has_ready_mesh_false(self):
        case = ColdStartCase(id="T", rank=1, platform="SU2", tier="core_seed",
                             dimension="2D", difficulty="basic", case_name="test",
                             mesh_strategy="B")
        assert case.has_ready_mesh is False
