#!/usr/bin/env python3
"""
diff_engine.py — Knowledge Compiler change detection and impact engine.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Optional, Sequence

try:
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised in pytest env without PyYAML
    yaml = None


MANIFEST_FILE = "BASELINE_MANIFEST.json"
MISSING = object()
UNIT_ID_KEYS = ("case_id", "chain_id", "type_id", "field_id", "artifact_id", "id")
ANCHOR_KEYS = UNIT_ID_KEYS + ("tsr", "level", "airfoil", "y_H", "symbol", "name")
CORE_UNIT_PREFIXES = ("CH-", "FORM-", "CASE-", "EVID-CHAIN-", "CHART-")
TRACKED_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".py"}
DATA_POINT_THRESHOLDS = {
    "coordinate": 0.1,
    "velocity": 0.01,
    "integral": 0.1,
}
EXECUTABLE_IDS = {
    "formula_validator": "EXEC-FORMULA-VALIDATOR-001",
    "chart_template": "EXEC-CHART-TEMPLATE-001",
    "bench_ghia": "EXEC-BENCH-GHIA-001",
    "bench_naca": "EXEC-BENCH-NACA-001",
    "diff_engine": "EXEC-DIFF-ENGINE-001",
}


class ChangeType(str, Enum):
    NEW = "NEW"
    DELETE = "DELETE"
    TEXT_EDIT = "TEXT_EDIT"
    SEMANTIC_EDIT = "SEMANTIC_EDIT"
    EVIDENCE_EDIT = "EVIDENCE_EDIT"
    CHART_RULE_EDIT = "CHART_RULE_EDIT"


@dataclass(frozen=True)
class DiffReport:
    change_type: ChangeType
    unit_id: str
    field: str
    old_value: Any
    new_value: Any
    impacted_executables: list[str]


@dataclass(frozen=True)
class _AtomicDiff:
    unit_id: str
    field: str
    old_value: Any
    new_value: Any


class _Snapshot:
    def exists(self, relative_path: str) -> bool:
        raise NotImplementedError

    def read_text(self, relative_path: str) -> str:
        raise NotImplementedError

    def list_files(self) -> set[str]:
        raise NotImplementedError


class _PathSnapshot(_Snapshot):
    def __init__(self, root: Path) -> None:
        self.root = root

    def exists(self, relative_path: str) -> bool:
        return (self.root / relative_path).is_file()

    def read_text(self, relative_path: str) -> str:
        return (self.root / relative_path).read_text(encoding="utf-8")

    def list_files(self) -> set[str]:
        files: set[str] = set()
        for child in self.root.iterdir():
            if child.is_file() and child.name != MANIFEST_FILE and child.suffix.lower() in TRACKED_EXTENSIONS:
                files.add(child.name)
        for folder in ("units", "schema", "executables"):
            folder_path = self.root / folder
            if not folder_path.exists():
                continue
            for child in folder_path.rglob("*"):
                if child.is_file() and child.suffix.lower() in TRACKED_EXTENSIONS:
                    files.add(child.relative_to(self.root).as_posix())
        return files


class _GitSnapshot(_Snapshot):
    def __init__(self, repo_root: Path, commit: str, root_prefix: PurePosixPath) -> None:
        self.repo_root = repo_root
        self.commit = commit
        self.root_prefix = root_prefix

    def _full_git_path(self, relative_path: str) -> str:
        full_path = self.root_prefix / relative_path
        return full_path.as_posix()

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.repo_root), *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def exists(self, relative_path: str) -> bool:
        target = f"{self.commit}:{self._full_git_path(relative_path)}"
        result = self._git("cat-file", "-e", target)
        return result.returncode == 0

    def read_text(self, relative_path: str) -> str:
        target = f"{self.commit}:{self._full_git_path(relative_path)}"
        result = self._git("show", target)
        if result.returncode != 0:
            raise FileNotFoundError(result.stderr.strip() or target)
        return result.stdout

    def list_files(self) -> set[str]:
        result = self._git("ls-tree", "-r", "--name-only", self.commit, self.root_prefix.as_posix())
        if result.returncode != 0:
            raise ValueError(result.stderr.strip() or f"Cannot list files for {self.commit}")

        files: set[str] = set()
        prefix = self.root_prefix.as_posix().rstrip("/") + "/"
        for line in result.stdout.splitlines():
            if not line.startswith(prefix):
                continue
            relative_path = line[len(prefix):]
            path_obj = PurePosixPath(relative_path)
            if path_obj.name == MANIFEST_FILE:
                continue
            if path_obj.suffix.lower() not in TRACKED_EXTENSIONS:
                continue
            if len(path_obj.parts) == 1 or path_obj.parts[0] in {"units", "schema", "executables"}:
                files.add(relative_path)
        return files


def _run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def _resolve_knowledge_root(path_value: str | Path) -> Path:
    candidate = Path(path_value).expanduser().resolve()
    if candidate.is_file():
        candidate = candidate.parent

    direct_manifest = candidate / MANIFEST_FILE
    nested_manifest = candidate / "knowledge_compiler" / MANIFEST_FILE
    if direct_manifest.is_file():
        return candidate
    if nested_manifest.is_file():
        return nested_manifest.parent
    raise ValueError(f"Cannot resolve knowledge_compiler root from {path_value}")


def _find_git_root(path_value: Path) -> Optional[Path]:
    result = subprocess.run(
        ["git", "-C", str(path_value), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def _load_manifest(knowledge_root: Path) -> dict[str, Any]:
    manifest_path = knowledge_root / MANIFEST_FILE
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _flatten_manifest_files(manifest: dict[str, Any]) -> list[str]:
    baseline_files = manifest["baseline_files"]
    files: list[str] = []
    for file_name in baseline_files.get("root", []):
        files.append(file_name)
    for bucket in ("units", "schema", "executables"):
        files.extend(baseline_files.get(bucket, []))
    return files


def _validate_manifest_layout(manifest: dict[str, Any]) -> list[str]:
    expected = _flatten_manifest_files(manifest)
    declared_total = manifest["baseline_files"]["total"]
    if len(expected) != declared_total:
        raise ValueError(
            f"Manifest baseline_files.total={declared_total} does not match enumerated files={len(expected)}"
        )
    return expected


def _validate_baseline_complete(snapshot: _Snapshot, manifest: dict[str, Any]) -> list[str]:
    expected = _validate_manifest_layout(manifest)
    missing = [path for path in expected if not snapshot.exists(path)]
    if missing:
        raise ValueError(f"Baseline snapshot is incomplete: missing {', '.join(missing)}")
    return expected


def _build_baseline_snapshot(baseline: str | Path, current_root: Path) -> _Snapshot:
    baseline_path = Path(str(baseline)).expanduser()
    if baseline_path.exists():
        return _PathSnapshot(_resolve_knowledge_root(baseline_path))

    repo_root = _find_git_root(current_root)
    if repo_root is None:
        raise ValueError("Baseline commit comparison requires current snapshot inside a git repository")
    try:
        _run_git(repo_root, "rev-parse", "--verify", f"{baseline}^{{commit}}")
    except ValueError as exc:
        raise ValueError(f"Baseline commit {baseline} was not found in repository {repo_root}") from exc

    root_prefix = PurePosixPath(current_root.relative_to(repo_root).as_posix())
    return _GitSnapshot(repo_root=repo_root, commit=str(baseline), root_prefix=root_prefix)


def _load_structured_content(relative_path: str, content: str) -> Any:
    suffix = Path(relative_path).suffix.lower()
    if suffix == ".json":
        return json.loads(content)
    if suffix in {".yaml", ".yml"}:
        if yaml is not None:
            return yaml.safe_load(content)
        return _fallback_yaml_load(content)
    return None


def _fallback_yaml_load(content: str) -> Any:
    script = (
        "import json, sys\n"
        "import yaml\n"
        "print(json.dumps(yaml.safe_load(sys.stdin.read())))\n"
    )
    result = subprocess.run(
        ["python3", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        input=content,
    )
    if result.returncode != 0:
        raise ModuleNotFoundError("PyYAML is required to parse YAML content")
    return json.loads(result.stdout)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_unit_id(node: Any) -> Optional[str]:
    if not isinstance(node, dict):
        return None
    for key in UNIT_ID_KEYS:
        value = node.get(key)
        if value is None:
            continue
        return str(value)
    return None


def _normalize_unit_id(relative_path: str, candidate: Optional[str], fallback: Optional[str]) -> str:
    if candidate:
        if relative_path.startswith("schema/") and not candidate.startswith(CORE_UNIT_PREFIXES):
            return f"{relative_path}#{candidate}"
        return candidate
    return fallback or relative_path


def _join_field(parent: str, child: str) -> str:
    return f"{parent}.{child}" if parent else child


def _select_anchor_key(old_list: list[Any], new_list: list[Any]) -> Optional[str]:
    combined = [item for item in old_list + new_list if isinstance(item, dict)]
    if not combined or len(combined) != len(old_list) + len(new_list):
        return None

    for key in ANCHOR_KEYS:
        values: list[str] = []
        valid = True
        for item in combined:
            if key not in item:
                valid = False
                break
            values.append(str(item[key]))
        if valid and len(values) == len(set(values)):
            return key
    return None


def _build_anchored_map(items: list[Any], anchor_key: str) -> dict[str, Any]:
    anchored: dict[str, Any] = {}
    for item in items:
        anchored[str(item[anchor_key])] = item
    return anchored


def _compare_nodes(
    old_node: Any,
    new_node: Any,
    field_path: str,
    current_unit_id: Optional[str],
    relative_path: str,
) -> list[_AtomicDiff]:
    if old_node is MISSING and new_node is MISSING:
        return []

    if isinstance(old_node, dict) or isinstance(new_node, dict):
        old_dict = old_node if isinstance(old_node, dict) else {}
        new_dict = new_node if isinstance(new_node, dict) else {}
        dict_unit_id = _normalize_unit_id(
            relative_path,
            _extract_unit_id(new_dict) or _extract_unit_id(old_dict),
            current_unit_id,
        )

        if (old_node is MISSING or new_node is MISSING) and _extract_unit_id(new_dict or old_dict):
            return [
                _AtomicDiff(
                    unit_id=dict_unit_id,
                    field="__unit__",
                    old_value=None if old_node is MISSING else old_node,
                    new_value=None if new_node is MISSING else new_node,
                )
            ]

        diffs: list[_AtomicDiff] = []
        for key in sorted(set(old_dict) | set(new_dict)):
            diffs.extend(
                _compare_nodes(
                    old_dict.get(key, MISSING),
                    new_dict.get(key, MISSING),
                    _join_field(field_path, key),
                    dict_unit_id,
                    relative_path,
                )
            )
        return diffs

    if isinstance(old_node, list) or isinstance(new_node, list):
        old_list = old_node if isinstance(old_node, list) else []
        new_list = new_node if isinstance(new_node, list) else []
        anchor_key = _select_anchor_key(old_list, new_list)

        diffs: list[_AtomicDiff] = []
        if anchor_key:
            old_map = _build_anchored_map(old_list, anchor_key)
            new_map = _build_anchored_map(new_list, anchor_key)
            for anchor_value in sorted(set(old_map) | set(new_map), key=str):
                label = f"{field_path}[{anchor_key}={anchor_value}]"
                diffs.extend(
                    _compare_nodes(
                        old_map.get(anchor_value, MISSING),
                        new_map.get(anchor_value, MISSING),
                        label,
                        current_unit_id,
                        relative_path,
                    )
                )
            return diffs

        max_length = max(len(old_list), len(new_list))
        for index in range(max_length):
            old_item = old_list[index] if index < len(old_list) else MISSING
            new_item = new_list[index] if index < len(new_list) else MISSING
            diffs.extend(
                _compare_nodes(
                    old_item,
                    new_item,
                    f"{field_path}[{index}]",
                    current_unit_id,
                    relative_path,
                )
            )
        return diffs

    if old_node == new_node:
        return []

    return [
        _AtomicDiff(
            unit_id=current_unit_id or relative_path,
            field=field_path or "content",
            old_value=None if old_node is MISSING else old_node,
            new_value=None if new_node is MISSING else new_node,
        )
    ]


def _safe_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            return float(match.group(0))
    return None


def _field_leaf(field: str) -> str:
    leaf = field.split(".")[-1]
    if "]" in leaf:
        leaf = leaf.split("]")[-1] or field.split(".")[-1]
    return leaf


def _data_point_category(field: str) -> str:
    field_lower = field.lower()
    leaf = _field_leaf(field).lower()

    if leaf in {"y_h", "x_h", "x_l", "y_l", "center_x_h", "center_y_h", "tsr", "at_tsr"}:
        return "coordinate"
    if leaf.startswith(("u_", "v_")) or "velocity" in leaf or leaf == "lid_velocity":
        return "velocity"
    if leaf == "error_pct" and "velocity" in field_lower:
        return "velocity"
    if any(token in leaf for token in ("cp", "ct", "psi", "torque", "power", "thrust", "gci", "error_pct")):
        return "integral"
    return "coordinate"


def _relative_delta_pct(old_value: float, new_value: float) -> float:
    baseline = max(abs(old_value), abs(new_value), 1.0)
    return abs(new_value - old_value) / baseline * 100.0


def _within_data_tolerance(field: str, old_value: Any, new_value: Any) -> bool:
    old_number = _safe_float(old_value)
    new_number = _safe_float(new_value)
    if old_number is None or new_number is None:
        return False

    category = _data_point_category(field)
    threshold = DATA_POINT_THRESHOLDS[category]
    return _relative_delta_pct(old_number, new_number) <= threshold


def classify_change(unit_id: str, field: str, old_value: Any, new_value: Any) -> ChangeType:
    if field == "__unit__":
        if old_value is None:
            return ChangeType.NEW
        if new_value is None:
            return ChangeType.DELETE

    if unit_id.endswith("chart_rules.yaml") or unit_id.startswith("CHART-"):
        return ChangeType.CHART_RULE_EDIT

    if unit_id.endswith("data_points.yaml") or unit_id.endswith("evidence.yaml") or unit_id.startswith(("CASE-", "EVID-CHAIN-")):
        if _within_data_tolerance(field, old_value, new_value):
            return ChangeType.TEXT_EDIT
        return ChangeType.EVIDENCE_EDIT

    if isinstance(old_value, str) and isinstance(new_value, str) and _normalize_text(old_value) == _normalize_text(new_value):
        return ChangeType.TEXT_EDIT

    if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)) and old_value == new_value:
        return ChangeType.TEXT_EDIT

    return ChangeType.SEMANTIC_EDIT


def track_impact(change: DiffReport) -> list[str]:
    if change.change_type == ChangeType.TEXT_EDIT:
        return []

    unit_id = change.unit_id

    if change.change_type == ChangeType.CHART_RULE_EDIT:
        return [EXECUTABLE_IDS["chart_template"]]

    if change.change_type == ChangeType.EVIDENCE_EDIT:
        if "CASE-001" in unit_id or "EVID-CHAIN-001" in unit_id or "bench_ghia1982.py" in unit_id:
            return [EXECUTABLE_IDS["bench_ghia"]]
        if "CASE-002" in unit_id or "EVID-CHAIN-002" in unit_id or "bench_naca.py" in unit_id:
            return [EXECUTABLE_IDS["bench_naca"]]
        return [EXECUTABLE_IDS["bench_ghia"], EXECUTABLE_IDS["bench_naca"]]

    if unit_id.startswith("FORM-") or "formulas.yaml" in unit_id or "formula_validator.py" in unit_id:
        return [
            EXECUTABLE_IDS["formula_validator"],
            EXECUTABLE_IDS["bench_ghia"],
            EXECUTABLE_IDS["bench_naca"],
        ]

    if unit_id.startswith("CHART-") or "chart_template.py" in unit_id or "chart_rules.yaml" in unit_id:
        return [EXECUTABLE_IDS["chart_template"]]

    if unit_id.startswith("CASE-001") or "bench_ghia1982.py" in unit_id:
        return [EXECUTABLE_IDS["bench_ghia"]]

    if unit_id.startswith("CASE-002") or "bench_naca.py" in unit_id:
        return [EXECUTABLE_IDS["bench_naca"]]

    if "schema/" in unit_id:
        return [
            EXECUTABLE_IDS["formula_validator"],
            EXECUTABLE_IDS["chart_template"],
            EXECUTABLE_IDS["bench_ghia"],
            EXECUTABLE_IDS["bench_naca"],
            EXECUTABLE_IDS["diff_engine"],
        ]

    if "publish_contract.md" in unit_id or "diff_engine" in unit_id:
        return [EXECUTABLE_IDS["diff_engine"]]

    if unit_id.endswith("executables/chart_template.py"):
        return [EXECUTABLE_IDS["chart_template"]]
    if unit_id.endswith("executables/formula_validator.py"):
        return [
            EXECUTABLE_IDS["formula_validator"],
            EXECUTABLE_IDS["bench_ghia"],
            EXECUTABLE_IDS["bench_naca"],
        ]

    return []


def _build_change(unit_id: str, field: str, old_value: Any, new_value: Any) -> DiffReport:
    provisional = DiffReport(
        change_type=classify_change(unit_id, field, old_value, new_value),
        unit_id=unit_id,
        field=field,
        old_value=old_value,
        new_value=new_value,
        impacted_executables=[],
    )
    return DiffReport(
        change_type=provisional.change_type,
        unit_id=provisional.unit_id,
        field=provisional.field,
        old_value=provisional.old_value,
        new_value=provisional.new_value,
        impacted_executables=track_impact(provisional),
    )


def _infer_version(snapshot: _Snapshot, fallback: str) -> str:
    if snapshot.exists("BASELINE-v1.md"):
        content = snapshot.read_text("BASELINE-v1.md")
        match = re.search(r"BASELINE\s+(v\d+\.\d+)", content)
        if match:
            return match.group(1)
    return fallback


def diff_files(baseline: str | Path, current: str | Path) -> list[DiffReport]:
    current_root = _resolve_knowledge_root(current)
    current_manifest = _load_manifest(current_root)
    current_snapshot = _PathSnapshot(current_root)
    baseline_snapshot = _build_baseline_snapshot(baseline, current_root)

    expected_files = _validate_baseline_complete(baseline_snapshot, current_manifest)
    candidate_files = set(expected_files) | baseline_snapshot.list_files() | current_snapshot.list_files()

    diffs: list[DiffReport] = []

    for relative_path in sorted(candidate_files):
        baseline_exists = baseline_snapshot.exists(relative_path)
        current_exists = current_snapshot.exists(relative_path)

        if not baseline_exists and current_exists:
            diffs.append(_build_change(relative_path, "__unit__", None, {"path": relative_path}))
            continue
        if baseline_exists and not current_exists:
            diffs.append(_build_change(relative_path, "__unit__", {"path": relative_path}, None))
            continue
        if not baseline_exists and not current_exists:
            continue

        old_text = baseline_snapshot.read_text(relative_path)
        new_text = current_snapshot.read_text(relative_path)
        if old_text == new_text:
            continue

        old_structured = _load_structured_content(relative_path, old_text)
        new_structured = _load_structured_content(relative_path, new_text)

        if old_structured is not None and new_structured is not None:
            if old_structured == new_structured:
                diffs.append(_build_change(relative_path, "content", old_text, new_text))
                continue

            for atomic in _compare_nodes(old_structured, new_structured, "", None, relative_path):
                diffs.append(_build_change(atomic.unit_id, atomic.field, atomic.old_value, atomic.new_value))
            continue

        if _normalize_text(old_text) == _normalize_text(new_text):
            diffs.append(_build_change(relative_path, "content", old_text, new_text))
        else:
            diffs.append(_build_change(relative_path, "content", old_text, new_text))

    return diffs


def generate_report(
    changes: Sequence[DiffReport],
    from_version: str,
    to_version: str,
) -> dict[str, Any]:
    new_assets = sorted({change.unit_id for change in changes if change.change_type == ChangeType.NEW})
    deleted_assets = sorted({change.unit_id for change in changes if change.change_type == ChangeType.DELETE})
    invalidated_executables = sorted(
        {
            executable
            for change in changes
            if change.change_type != ChangeType.TEXT_EDIT
            for executable in change.impacted_executables
        }
    )

    semantic_units = {
        change.unit_id
        for change in changes
        if change.change_type == ChangeType.SEMANTIC_EDIT
    }
    requires_review = any(
        change.change_type in {ChangeType.EVIDENCE_EDIT, ChangeType.CHART_RULE_EDIT}
        for change in changes
    ) or len(semantic_units) > 3

    return {
        "diff_id": f"DIFF-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "from_version": from_version,
        "to_version": to_version,
        "changes": [asdict(change) for change in changes],
        "new_assets": new_assets,
        "deleted_assets": deleted_assets,
        "invalidated_executables": invalidated_executables,
        "requires_review": requires_review,
    }


def _report_versions(current_root: Path, baseline_snapshot: _Snapshot, manifest: dict[str, Any]) -> tuple[str, str]:
    baseline_version = str(manifest.get("baseline_version", "baseline"))
    current_snapshot = _PathSnapshot(current_root)
    return baseline_version, _infer_version(current_snapshot, _infer_version(baseline_snapshot, baseline_version))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Knowledge Compiler diff engine")
    parser.add_argument("--baseline", required=True, help="Baseline commit hash or knowledge_compiler path")
    parser.add_argument("--current", required=True, help="Current knowledge_compiler path or repo root")
    args = parser.parse_args(argv)

    current_root = _resolve_knowledge_root(args.current)
    manifest = _load_manifest(current_root)
    baseline_snapshot = _build_baseline_snapshot(args.baseline, current_root)
    changes = diff_files(args.baseline, current_root)
    from_version, to_version = _report_versions(current_root, baseline_snapshot, manifest)
    report = generate_report(changes, from_version=from_version, to_version=to_version)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


__all__ = [
    "ChangeType",
    "DiffReport",
    "diff_files",
    "classify_change",
    "track_impact",
    "generate_report",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
