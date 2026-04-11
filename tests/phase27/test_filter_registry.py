"""
Tests for the UUID filter registry in trame_server.py.

Uses AST to extract individual functions from trame_server.py and tests them
in isolation with mocked ParaView/simple globals, bypassing the module-level
_state = None assignment that would override our mocks.
"""

import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Direct path to project root
PROJECT_ROOT = Path("/Users/Zhuanz/Desktop/notion-cfd-harness")


def _parse_filter_functions():
    """
    Parse trame_server.py and return the AST nodes for the filter-related
    functions we need to test, WITHOUT executing module-level code.
    """
    source_path = PROJECT_ROOT / "trame_server.py"
    with open(source_path) as f:
        source = f.read()

    tree = ast.parse(source)

    # Function names we want to extract
    wanted = {
        "_build_filter_params",
        "_get_filter_list",
        "on_filter_clip_create",
        "on_filter_contour_create",
        "on_filter_streamtracer_create",
        "on_filter_delete",
        "on_filter_list_request",
        "on_volume_rendering_status_request",
    }

    functions = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            functions[node.name] = node

    return functions


class MockTrameState:
    """Mock trame server state used in filter registry tests."""

    def __init__(self):
        self.filters = {}
        self.filter_list = {"filters": []}
        self.volume_rendering_status = {}
        self._slice_filter = None
        self.slice_axis = None
        self.slice_origin = [0.0, 0.0, 0.0]
        self.field = ""
        self.color_preset = "Viridis"
        self.scalar_range_mode = "auto"
        self.scalar_range_min = 0.0
        self.scalar_range_max = 1.0
        self.time_step_index = 0
        self.camera_poll_trigger = 0


class MockTrameCtrl:
    """Mock trame server controller used in filter registry tests."""

    def __init__(self):
        self.view_update_calls = 0

    def view_update(self):
        self.view_update_calls += 1


class MockSimple:
    """Mock paraview.simple module for filter registry tests."""

    def __init__(self):
        self.Render = MagicMock()
        self.Delete = MagicMock()
        self._clip_count = 0
        self._contour_count = 0
        self._streamtracer_count = 0

    def Clip(self, Input=None):
        self._clip_count += 1
        m = MagicMock(name=f"clip_{self._clip_count}")
        m.ClipType = "Scalar"
        m.Scalar = 0.0
        m.InsideOut = False
        return m

    def Contour(self, Input=None):
        self._contour_count += 1
        m = MagicMock(name=f"contour_{self._contour_count}")
        m.ContourBy = ["POINTS", " scalars"]
        m.Isosurfaces = []
        return m

    def StreamTracer(self, Input=None):
        self._streamtracer_count += 1
        m = MagicMock(name=f"streamtracer_{self._streamtracer_count}")
        m.Vectors = ["POINTS", "U"]
        m.IntegrationDirection = "FORWARD"
        m.MaximumSteps = 1000
        m.InitialStepLength = 0.1
        m.MinimumStepLength = 0.001
        return m

    def GetActiveSource(self):
        return MagicMock(name="active_source")

    def GetDataInformation(self, source=None):
        m = MagicMock(name="data_info")
        m.GetNumberOfCells = MagicMock(return_value=1000)
        return m

    def GetActiveView(self):
        return MagicMock(name="active_view")

    def GetDisplayProperties(self, source=None):
        return MagicMock(name="display_props", Representation="Surface")


class TestFilterRegistryUnit:
    """Unit tests for UUID filter registry using AST-extracted functions."""

    @pytest.fixture
    def ns(self):
        """
        Build a test namespace by compiling the AST of filter functions
        with mocked simple/_state/_ctrl globals.
        """
        functions = _parse_filter_functions()

        simple = MockSimple()
        _state = MockTrameState()
        _ctrl = MockTrameCtrl()

        # Build namespace with mocked dependencies
        ns = {
            "simple": simple,
            "_state": _state,
            "_ctrl": _ctrl,
            "_build_filter_params": None,  # filled below
            "_get_filter_list": None,
            "on_filter_clip_create": None,
            "on_filter_contour_create": None,
            "on_filter_streamtracer_create": None,
            "on_filter_delete": None,
            "on_filter_list_request": None,
            "on_volume_rendering_status_request": None,
            "uuid": __import__("uuid"),
            "get_server": None,
            "_server": None,
            "_detect_gpu": lambda: (True, "NVIDIA"),  # mock GPU detector
            "__builtins__": __builtins__,
        }

        for fname, fnode in functions.items():
            code = _compile_function(fnode)
            exec_ns = dict(ns)
            exec(code, exec_ns)
            ns[fname] = exec_ns[fname]

        # Attach mocks to namespace for test access
        ns["_simple_mock"] = simple
        ns["_state_mock"] = _state
        ns["_ctrl_mock"] = _ctrl

        return ns

    def test_filter_clip_creates_uuid_key(self, ns):
        """on_filter_clip_create generates a UUID key (32-char hex from uuid.uuid4().hex)."""
        result = ns["on_filter_clip_create"](inside_out=False, scalar_value=0.0)

        assert result["success"] is True
        filter_id = result["filterId"]
        # uuid.uuid4().hex is always 32 hex chars (128-bit UUID)
        assert len(filter_id) == 32, f"Expected 32-char hex UUID, got {len(filter_id)}: {filter_id}"
        assert all(c in "0123456789abcdef" for c in filter_id), f"Not hex: {filter_id}"
        assert filter_id in ns["_state_mock"].filters

    def test_filter_contour_creates_uuid_key(self, ns):
        """on_filter_contour_create generates a UUID key."""
        result = ns["on_filter_contour_create"](isovalues=[0.5])

        assert result["success"] is True
        filter_id = result["filterId"]
        assert len(filter_id) == 32
        assert filter_id in ns["_state_mock"].filters

    def test_filter_streamtracer_creates_uuid_key(self, ns):
        """on_filter_streamtracer_create generates a UUID key."""
        result = ns["on_filter_streamtracer_create"](
            integration_direction="FORWARD", max_steps=1000
        )

        assert result["success"] is True
        filter_id = result["filterId"]
        assert len(filter_id) == 32
        assert filter_id in ns["_state_mock"].filters

    def test_filter_delete_removes_uuid_key(self, ns):
        """on_filter_delete removes the filter from _state.filters."""
        fake_uuid = "deadbeef12345678"
        ns["_state_mock"].filters[fake_uuid] = {
            "type": "clip",
            "proxy": MagicMock(),
            "params": {"insideOut": False, "scalarValue": 0.0},
        }

        result = ns["on_filter_delete"](fake_uuid)

        assert result["success"] is True
        assert fake_uuid not in ns["_state_mock"].filters

    def test_filter_list_builds_correct_structure(self, ns):
        """_get_filter_list returns {"filters": [...]} with id/type/parameters keys."""
        # Add 3 filters directly
        for ftype in ("clip", "contour", "streamtracer"):
            fid = __import__("uuid").uuid4().hex
            ns["_state_mock"].filters[fid] = {
                "type": ftype,
                "proxy": MagicMock(),
                "params": {},
            }

        result = ns["_get_filter_list"]()

        assert "filters" in result
        assert len(result["filters"]) == 3
        for entry in result["filters"]:
            assert "id" in entry
            assert "type" in entry
            assert "parameters" in entry

    def test_volume_rendering_status_detects_mesa(self, ns):
        """Volume rendering status sets gpu_available=False for Mesa."""
        # Use patch.dict to add/replace _detect_gpu in the function's globals
        with patch.dict(
            ns["on_volume_rendering_status_request"].__globals__,
            {"_detect_gpu": lambda: (False, "Mesa")},
        ):
            ns["on_volume_rendering_status_request"](volume_rendering_status_request=True)

        status = ns["_state_mock"].volume_rendering_status
        assert status["gpu_vendor"] == "Mesa"
        assert status["gpu_available"] is False

    def test_volume_rendering_status_warns_over_2m_cells(self, ns):
        """Cell count > 2M sets cell_count_warning = True."""
        # Override GetDataInformation to return 3M cells
        ns["simple"].GetDataInformation = MagicMock(
            return_value=MagicMock(
                name="data_info_3m",
                GetNumberOfCells=MagicMock(return_value=3_000_000),
            )
        )

        with patch.dict(
            ns["on_volume_rendering_status_request"].__globals__,
            {"_detect_gpu": lambda: (True, "NVIDIA")},
        ):
            ns["on_volume_rendering_status_request"](volume_rendering_status_request=True)

        status = ns["_state_mock"].volume_rendering_status
        assert status["cell_count_warning"] is True
        assert status["cell_count"] == 3_000_000

    def test_filter_delete_unknown_id_returns_error(self, ns):
        """Deleting an unknown filter ID returns success=False with error."""
        result = ns["on_filter_delete"]("nonexistent-uuid-1234")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_filter_clip_rejects_invalid_scalar(self, ns):
        """on_filter_clip_create rejects out-of-range scalar values."""
        result = ns["on_filter_clip_create"](inside_out=False, scalar_value=1e20)
        assert result["success"] is False
        assert "invalid" in result["error"].lower()

    def test_filter_contour_rejects_too_many_isovalues(self, ns):
        """on_filter_contour_create rejects isovalues list > 20 elements."""
        result = ns["on_filter_contour_create"](isovalues=list(range(25)))
        assert result["success"] is False

    def test_filter_streamtracer_rejects_bad_direction(self, ns):
        """on_filter_streamtracer_create rejects invalid integration_direction."""
        result = ns["on_filter_streamtracer_create"](
            integration_direction="NOWHERE", max_steps=100
        )
        assert result["success"] is False
        assert "integrationdirection" in result["error"].lower()

    def test_filter_streamtracer_caps_max_steps(self, ns):
        """on_filter_streamtracer_create caps max_steps at 10000."""
        result = ns["on_filter_streamtracer_create"](
            integration_direction="FORWARD", max_steps=99999
        )
        assert result["success"] is True
        filter_uuid = result["filterId"]
        registered = ns["_state"].filters[filter_uuid]
        assert registered["params"]["maxSteps"] <= 10000

    def test_build_filter_params_clip(self, ns):
        """_build_filter_params extracts Clip parameters correctly."""
        mock_proxy = MagicMock()
        mock_proxy.ClipType = "Scalar"
        mock_proxy.Scalar = 1.5
        mock_proxy.InsideOut = True

        result = ns["_build_filter_params"](mock_proxy, "clip")

        assert result["insideOut"] is True
        assert result["scalarValue"] == 1.5

    def test_build_filter_params_contour(self, ns):
        """_build_filter_params extracts Contour parameters correctly."""
        mock_proxy = MagicMock()
        mock_proxy.Isosurfaces = [0.1, 0.5, 1.0]

        result = ns["_build_filter_params"](mock_proxy, "contour")

        assert result["isovalues"] == [0.1, 0.5, 1.0]

    def test_build_filter_params_streamtracer(self, ns):
        """_build_filter_params extracts StreamTracer parameters correctly."""
        mock_proxy = MagicMock()
        mock_proxy.IntegrationDirection = "BACKWARD"
        mock_proxy.MaximumSteps = 500

        result = ns["_build_filter_params"](mock_proxy, "streamtracer")

        assert result["integrationDirection"] == "BACKWARD"
        assert result["maxSteps"] == 500


# ---------------------------------------------------------------------------
# Helper: wrap a FunctionDef in a Module for compilation
# ---------------------------------------------------------------------------

def _fn_to_module(fn_node: ast.FunctionDef) -> ast.Module:
    """Wrap a FunctionDef in a Module AST node, stripping decorators."""
    import copy
    new_fn = copy.deepcopy(fn_node)
    new_fn.decorator_list = []
    # Fix missing arg defaults
    ast.fix_missing_locations(new_fn)
    module = ast.Module(body=[new_fn], type_ignores=[])
    ast.fix_missing_locations(module)
    return module


def _compile_function(fn_node: ast.FunctionDef) -> str:
    """Compile a FunctionDef to code object, return the function name."""
    mod = _fn_to_module(fn_node)
    code = compile(mod, "<filter_fn>", "exec")
    return code
