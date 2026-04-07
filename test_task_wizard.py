#!/usr/bin/env python3
"""
Well-Harness M1-3 TaskWizard pytest 单元测试
覆盖：parse_natural_language / create_notion_task / validate_g0
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from task_wizard import TaskWizard, NOTION_API_KEY, TASKS_DB_ID


class TestParseNaturalLanguage:
    """parse_natural_language 测试"""

    def test_parses_steady_state(self):
        """稳态描述 → task_type=稳态仿真"""
        tw = TaskWizard()
        result = tw.parse_natural_language("稳态圆柱绕流仿真，入口速度5m/s")
        assert result["task_type"] == "稳态仿真"

    def test_parses_transient(self):
        """瞬态描述 → task_type=瞬态仿真"""
        tw = TaskWizard()
        result = tw.parse_natural_language("瞬态翼型气动仿真，非定常计算")
        assert result["task_type"] == "瞬态仿真"

    def test_parses_priority_p0(self):
        """高优先级/P0 → priority=P0"""
        tw = TaskWizard()
        result = tw.parse_natural_language("高优先级任务，紧急需要")
        assert result["priority"] == "P0"

    def test_parses_priority_p2(self):
        """低优先级 → priority=P2"""
        tw = TaskWizard()
        result = tw.parse_natural_language("低优先级参数研究")
        assert result["priority"] == "P2"

    def test_parses_cylinder_geometry(self):
        """圆柱描述 → geometry_features 包含圆柱绕流"""
        tw = TaskWizard()
        result = tw.parse_natural_language("圆柱绕流稳态仿真")
        assert "圆柱绕流" in result["geometry_features"]

    def test_parses_airfoil_geometry(self):
        """翼型描述 → geometry_features 包含翼型气动"""
        tw = TaskWizard()
        result = tw.parse_natural_language("翼型气动优化仿真")
        assert "翼型气动" in result["geometry_features"]

    def test_parses_inlet_type_only(self):
        """速度入口描述（无数值） → boundary_conditions 包含 inlet_type"""
        tw = TaskWizard()
        result = tw.parse_natural_language("速度入口的稳态仿真")
        bc = result["boundary_conditions"]
        assert "inlet_type" in bc

    def test_parses_inlet_type_without_velocity_value(self):
        """有速度入口但无数值 → inlet_type"""
        tw = TaskWizard()
        result = tw.parse_natural_language("速度入口的稳态仿真")
        bc = result["boundary_conditions"]
        assert "inlet_type" in bc

    def test_parses_convergence_criteria(self):
        """收敛标准 → convergence_criteria 正确提取"""
        tw = TaskWizard()
        result = tw.parse_natural_language("收敛标准10^-5的稳态仿真")
        assert result["convergence_criteria"] == "10^-5"

    def test_parses_solver_komega(self):
        """k-omega 描述 → solver_type 包含 k-omega"""
        tw = TaskWizard()
        result = tw.parse_natural_language("使用k-omega SST求解器")
        assert "k-omega" in result["solver_type"]

    def test_parses_solver_simple(self):
        """SIMPLE 描述 → solver_type = SIMPLE"""
        tw = TaskWizard()
        result = tw.parse_natural_language("SIMPLE算法稳态计算")
        assert result["solver_type"] == "SIMPLE"

    def test_parses_water_fluid(self):
        """水描述 → fluid_properties.medium = 水"""
        tw = TaskWizard()
        result = tw.parse_natural_language("水作为流体，收敛标准10^-4")
        assert result["fluid_properties"]["medium"] == "水"
        assert "density" in result["fluid_properties"]

    def test_parses_air_fluid(self):
        """空气描述 → fluid_properties.medium = 空气"""
        tw = TaskWizard()
        result = tw.parse_natural_language("空气作为流体")
        assert result["fluid_properties"]["medium"] == "空气"

    def test_fallback_default_geometry(self):
        """未匹配几何特征 → 默认为通用几何"""
        tw = TaskWizard()
        result = tw.parse_natural_language("某CFD仿真任务")
        assert "通用几何" in result["geometry_features"]

    def test_returns_raw_description(self):
        """原始描述被保留"""
        tw = TaskWizard()
        raw = "稳态管道流动仿真"
        result = tw.parse_natural_language(raw)
        assert result["raw_description"] == raw

    def test_boundary_conditions_empty_when_not_specified(self):
        """无边界条件描述时为空字典"""
        tw = TaskWizard()
        result = tw.parse_natural_language("某CFD仿真任务")
        assert result["boundary_conditions"] == {}

    def test_convergence_criteria_default(self):
        """无收敛标准时 → 默认10^-4"""
        tw = TaskWizard()
        result = tw.parse_natural_language("某CFD仿真任务")
        assert result["convergence_criteria"] == "10^-4"


class TestCreateNotionTask:
    """create_notion_task 测试"""

    def test_returns_string_page_id(self):
        """返回非空字符串 page_id"""
        mock_resp = MagicMock(status_code=200, json=lambda: {"id": "fake-page-id-12345"})
        with patch('task_wizard.requests.post', return_value=mock_resp):
            tw = TaskWizard()
            task_data = tw.parse_natural_language("稳态圆柱绕流仿真")
            page_id = tw.create_notion_task(task_data, parent_page_id=None)
            assert isinstance(page_id, str)
            assert len(page_id) > 0

    def test_calls_notion_api(self):
        """调用 requests.post 到正确端点"""
        mock_resp = MagicMock(status_code=200, json=lambda: {"id": "fake-page-id-123"})
        with patch('task_wizard.requests.post', return_value=mock_resp) as mock_post:
            tw = TaskWizard()
            task_data = tw.parse_natural_language("稳态仿真")
            tw.create_notion_task(task_data, parent_page_id=None)
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert "pages" in args[0]

    def test_payload_has_database_parent(self):
        """parent 设为 TASKS_DB_ID"""
        mock_resp = MagicMock(status_code=200, json=lambda: {"id": "fake-page-id-123"})
        with patch('task_wizard.requests.post', return_value=mock_resp) as mock_post:
            tw = TaskWizard()
            task_data = tw.parse_natural_language("仿真")
            tw.create_notion_task(task_data)
            call_json = mock_post.call_args[1]["json"]
            assert call_json["parent"] == {"database_id": TASKS_DB_ID}

    def test_properties_has_task_id(self):
        """Task ID 字段有内容"""
        mock_resp = MagicMock(status_code=200, json=lambda: {"id": "fake-page-id-123"})
        with patch('task_wizard.requests.post', return_value=mock_resp) as mock_post:
            tw = TaskWizard()
            task_data = tw.parse_natural_language("高优先级翼型仿真")
            tw.create_notion_task(task_data)
            props = mock_post.call_args[1]["json"]["properties"]
            assert "Task ID" in props
            title = props["Task ID"]["title"]
            assert len(title) > 0
            assert "P0" in title[0]["text"]["content"]

    def test_parent_page_maps_to_linked_project(self):
        """parent_page_id 写入 Linked Project"""
        mock_resp = MagicMock(status_code=200, json=lambda: {"id": "fake-page-id-123"})
        with patch('task_wizard.requests.post', return_value=mock_resp) as mock_post:
            tw = TaskWizard()
            task_data = tw.parse_natural_language("稳态圆柱绕流仿真")
            tw.create_notion_task(task_data, parent_page_id="project-page-123")
            props = mock_post.call_args[1]["json"]["properties"]
            assert "Linked Project" in props
            rt = props["Linked Project"]["rich_text"]
            assert len(rt) > 0
            assert rt[0]["text"]["content"] == "project-page-123"

    def test_properties_has_task_type(self):
        """Task Type 字段有内容"""
        mock_resp = MagicMock(status_code=200, json=lambda: {"id": "fake-page-id-123"})
        with patch('task_wizard.requests.post', return_value=mock_resp) as mock_post:
            tw = TaskWizard()
            task_data = tw.parse_natural_language("稳态仿真")
            tw.create_notion_task(task_data)
            props = mock_post.call_args[1]["json"]["properties"]
            assert props["Task Type"]["select"]["name"] == "任务"

    def test_properties_has_priority(self):
        """Priority 映射到 v1 选项"""
        mock_resp = MagicMock(status_code=200, json=lambda: {"id": "fake-page-id-123"})
        with patch('task_wizard.requests.post', return_value=mock_resp) as mock_post:
            tw = TaskWizard()
            task_data = tw.parse_natural_language("高优先级圆柱绕流仿真")
            tw.create_notion_task(task_data)
            props = mock_post.call_args[1]["json"]["properties"]
            assert props["Priority"]["select"]["name"] == "P1"

    def test_properties_has_executor_and_fallback_models(self):
        """Executor/Fallback Model 写入默认值"""
        mock_resp = MagicMock(status_code=200, json=lambda: {"id": "fake-page-id-123"})
        with patch('task_wizard.requests.post', return_value=mock_resp) as mock_post:
            tw = TaskWizard()
            task_data = tw.parse_natural_language("仿真")
            tw.create_notion_task(task_data)
            props = mock_post.call_args[1]["json"]["properties"]
            assert props["Executor Model"]["rich_text"][0]["text"]["content"] == "codex"
            assert props["Fallback Model"]["rich_text"][0]["text"]["content"] == "glm_51"

    def test_task_status_defaults_to_pending(self):
        """Task Status 默认 = 待领取"""
        mock_resp = MagicMock(status_code=200, json=lambda: {"id": "fake-page-id-123"})
        with patch('task_wizard.requests.post', return_value=mock_resp) as mock_post:
            tw = TaskWizard()
            task_data = tw.parse_natural_language("仿真")
            tw.create_notion_task(task_data)
            props = mock_post.call_args[1]["json"]["properties"]
            assert props["Task Status"]["select"]["name"] == "待领取"

    def test_retry_count_defaults_to_zero(self):
        """Retry Count 默认 = 0"""
        mock_resp = MagicMock(status_code=200, json=lambda: {"id": "fake-page-id-123"})
        with patch('task_wizard.requests.post', return_value=mock_resp) as mock_post:
            tw = TaskWizard()
            task_data = tw.parse_natural_language("仿真")
            tw.create_notion_task(task_data)
            props = mock_post.call_args[1]["json"]["properties"]
            assert props["Retry Count"]["number"] == 0

    def test_last_run_summary_has_content(self):
        """Last Run Summary 字段包含任务摘要"""
        mock_resp = MagicMock(status_code=200, json=lambda: {"id": "fake-page-id-123"})
        with patch('task_wizard.requests.post', return_value=mock_resp) as mock_post:
            tw = TaskWizard()
            task_data = tw.parse_natural_language("圆柱绕流仿真，入口速度5m/s")
            tw.create_notion_task(task_data)
            props = mock_post.call_args[1]["json"]["properties"]
            content = props["Last Run Summary"]["rich_text"][0]["text"]["content"]
            assert "原始描述" in content
            assert "几何" in content

    def test_children_blocks_created(self):
        """页面 children blocks 被创建"""
        mock_resp = MagicMock(status_code=200, json=lambda: {"id": "fake-page-id-123"})
        with patch('task_wizard.requests.post', return_value=mock_resp) as mock_post:
            tw = TaskWizard()
            task_data = tw.parse_natural_language("圆柱绕流仿真")
            tw.create_notion_task(task_data)
            children = mock_post.call_args[1]["json"]["children"]
            assert len(children) > 0

    def test_returns_raises_on_api_error(self):
        """API 失败时 raise_for_status 抛出 HTTPError"""
        import requests as req
        mock_resp = MagicMock(status_code=400, text="bad request")
        mock_resp.raise_for_status.side_effect = req.HTTPError("400 Bad Request")
        with patch('task_wizard.requests.post', return_value=mock_resp):
            tw = TaskWizard()
            task_data = tw.parse_natural_language("仿真")
            with pytest.raises(req.HTTPError):
                tw.create_notion_task(task_data)


class TestValidateG0:
    """validate_g0 测试"""

    def test_returns_dict(self):
        """返回 dict"""
        mock_page = {
            "properties": {
                "Task ID": {"title": [{"plain_text": "TEST-001"}]},
                "Linked Project": {"rich_text": [{"plain_text": "PRJ-001"}]},
                "Linked Phase": {"rich_text": []},
                "Task Type": {"select": {"name": "任务"}},
                "Priority": {"select": {"name": "P1"}},
                "Last Run Summary": {"rich_text": [{"plain_text": "原始描述: 需求内容\nHarness摘要: 几何=圆柱绕流"}]},
            }
        }
        with patch('task_wizard.requests.get', return_value=MagicMock(status_code=200, json=lambda: mock_page)):
            tw = TaskWizard()
            result = tw.validate_g0("fake-page-id")
            assert isinstance(result, dict)

    def test_has_required_fields(self):
        """evidence 包含必需字段"""
        mock_page = {
            "properties": {
                "Task ID": {"title": [{"plain_text": "TEST-001"}]},
                "Linked Project": {"rich_text": [{"plain_text": "PRJ-001"}]},
                "Linked Phase": {"rich_text": []},
                "Task Type": {"select": {"name": "任务"}},
                "Priority": {"select": {"name": "P1"}},
                "Last Run Summary": {"rich_text": [{"plain_text": "原始描述: 需求内容\nHarness摘要: 几何=圆柱绕流"}]},
            }
        }
        with patch('task_wizard.requests.get', return_value=MagicMock(status_code=200, json=lambda: mock_page)):
            tw = TaskWizard()
            result = tw.validate_g0("fake-page-id")
            assert "gate" in result
            assert result["gate"] == "G0"
            assert "checks" in result
            assert "result" in result
            assert "message" in result

    def test_g0_pass_when_all_checks_pass(self):
        """所有字段非空且包含几何特征 → result=PASS"""
        mock_page = {
            "properties": {
                "Task ID": {"title": [{"plain_text": "TEST-001"}]},
                "Linked Project": {"rich_text": [{"plain_text": "PRJ-001"}]},
                "Linked Phase": {"rich_text": []},
                "Task Type": {"select": {"name": "任务"}},
                "Priority": {"select": {"name": "P1"}},
                "Last Run Summary": {"rich_text": [{"plain_text": "原始描述: 需求内容\nHarness摘要: 几何=圆柱绕流"}]},
            }
        }
        with patch('task_wizard.requests.get', return_value=MagicMock(status_code=200, json=lambda: mock_page)):
            tw = TaskWizard()
            result = tw.validate_g0("fake-page-id")
            assert result["result"] == "PASS"

    def test_g0_fail_on_missing_linked_context(self):
        """Linked Project/Phase 都为空 → result=FAIL"""
        mock_page = {
            "properties": {
                "Task ID": {"title": [{"plain_text": "TEST-001"}]},
                "Linked Project": {"rich_text": []},
                "Linked Phase": {"rich_text": []},
                "Task Type": {"select": {"name": "任务"}},
                "Priority": {"select": {"name": "P1"}},
                "Last Run Summary": {"rich_text": [{"plain_text": "原始描述: 需求内容\nHarness摘要: 几何=圆柱绕流"}]},
            }
        }
        with patch('task_wizard.requests.get', return_value=MagicMock(status_code=200, json=lambda: mock_page)):
            tw = TaskWizard()
            result = tw.validate_g0("fake-page-id")
            assert result["result"] == "FAIL"

    def test_g0_checks_has_5_items(self):
        """G0 校验包含 5 项检查"""
        mock_page = {
            "properties": {
                "Task ID": {"title": [{"plain_text": "TEST-001"}]},
                "Linked Project": {"rich_text": [{"plain_text": "PRJ-001"}]},
                "Linked Phase": {"rich_text": []},
                "Task Type": {"select": {"name": "任务"}},
                "Priority": {"select": {"name": "P1"}},
                "Last Run Summary": {"rich_text": [{"plain_text": "Harness摘要: 几何=圆柱"}]},
            }
        }
        with patch('task_wizard.requests.get', return_value=MagicMock(status_code=200, json=lambda: mock_page)):
            tw = TaskWizard()
            result = tw.validate_g0("fake-page-id")
            assert len(result["checks"]) == 5

    def test_validate_g0_handles_network_error(self):
        """网络错误时返回 error message"""
        with patch('task_wizard.requests.get', side_effect=Exception("Network error")):
            tw = TaskWizard()
            result = tw.validate_g0("fake-page-id")
            assert "error" in result["message"].lower() or "异常" in result["message"]

    def test_gate_name_is_task_gate(self):
        """gate_name = 任务门"""
        mock_page = {
            "properties": {
                "Task ID": {"title": [{"plain_text": "TEST-001"}]},
                "Linked Project": {"rich_text": [{"plain_text": "PRJ-001"}]},
                "Linked Phase": {"rich_text": []},
                "Task Type": {"select": {"name": "任务"}},
                "Priority": {"select": {"name": "P1"}},
                "Last Run Summary": {"rich_text": [{"plain_text": "原始描述: x\nHarness摘要: 几何=圆柱"}]},
            }
        }
        with patch('task_wizard.requests.get', return_value=MagicMock(status_code=200, json=lambda: mock_page)):
            tw = TaskWizard()
            result = tw.validate_g0("fake-page-id")
            assert result["gate_name"] == "任务门"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
