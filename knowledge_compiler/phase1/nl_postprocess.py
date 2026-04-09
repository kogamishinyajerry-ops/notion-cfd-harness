#!/usr/bin/env python3
"""
Phase 1 Module: NL Postprocess Executor (F2)

Core functionality for Phase 1 - converts natural language post-processing
instructions into executable action sequences.

This is the bridge between engineer intent and system action.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from knowledge_compiler.phase1.schema import ResultManifest, ResultAsset


# ============================================================================
# Action Types
# ============================================================================

class ActionType(Enum):
    """Types of post-processing actions"""
    GENERATE_PLOT = "generate_plot"
    EXTRACT_SECTION = "extract_section"
    CALCULATE_METRIC = "calculate_metric"
    COMPARE_DATA = "compare_data"
    REORDER_CONTENT = "reorder_content"


# ============================================================================
# Action and ActionPlan
# ============================================================================

@dataclass
class Action:
    """
    A single post-processing action

    Represents one step in the action plan derived from NL instruction.
    """
    action_type: ActionType
    parameters: Dict[str, Any]
    confidence: float  # 0-1
    requires_assets: List[str]  # Asset types needed

    def __str__(self) -> str:
        return f"{self.action_type.value}({self.parameters})"


@dataclass
class ActionPlan:
    """
    Complete action plan derived from NL instruction

    Contains all actions needed to fulfill the engineer's request.
    """
    actions: List[Action]
    detected_intent: str  # Main intent detected
    missing_assets: List[str]  # Required but unavailable assets
    confidence: float  # Overall plan confidence
    raw_instruction: str  # Original NL instruction

    def is_executable(self) -> bool:
        """Check if plan can be executed (no missing critical assets)"""
        return len(self.missing_assets) == 0

    def add_action(self, action: Action) -> None:
        """Add an action to the plan"""
        self.actions.append(action)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "actions": [
                {
                    "action_type": a.action_type.value,
                    "parameters": a.parameters,
                    "confidence": a.confidence,
                    "requires_assets": a.requires_assets,
                }
                for a in self.actions
            ],
            "detected_intent": self.detected_intent,
            "missing_assets": self.missing_assets,
            "confidence": self.confidence,
            "raw_instruction": self.raw_instruction,
        }


@dataclass
class ActionLog:
    """
    Log of action execution

    Records what actions were taken and their results.
    """
    timestamp: float
    action_plan: ActionPlan
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_result(self, action_index: int, result: Dict[str, Any]) -> None:
        """Add execution result for an action"""
        if 0 <= action_index < len(self.execution_results):
            self.execution_results[action_index] = result
        else:
            self.execution_results.append(result)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp,
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp)),
            "action_plan": self.action_plan.to_dict(),
            "execution_results": self.execution_results,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ============================================================================
# NL Postprocess Executor (CORE)
# ============================================================================

class NLPostprocessExecutor:
    """
    Natural Language Postprocess Executor - CORE of Phase 1

    Converts engineer's natural language instructions into executable
    action plans for post-processing CFD results.

    Key Features:
    - Intent detection (plot/section/metric/compare/reorder)
    - Parameter extraction from NL
    - Asset availability validation
    - Action sequence generation
    """

    def __init__(self):
        # Plot keywords
        self._plot_keywords = {
            "云图": ["contour", "field", "cloud"],
            "等值线": ["contour", "iso", "level"],
            "线图": ["line", "curve", "profile", "plot"],
            "矢量图": ["vector", "arrow"],
            "流线": ["streamline", "pathline", "streakline"],
            "图表": ["plot", "chart", "graph"],
        }

        # Section keywords
        self._section_keywords = {
            "平面": ["plane", "slice", "section"],
            "截面": ["section", "slice", "cut"],
            "壁面": ["wall", "surface"],
            "中心线": ["centerline", "midline"],
            "对称面": ["symmetry", "symmetric"],
        }

        # Metric keywords
        self._metric_keywords = {
            "系数": ["coefficient", "coef", "cd", "cl", "cm"],
            "力": ["force", "drag", "lift"],
            "压力": ["pressure", "p"],
            "温度": ["temperature", "t"],
            "速度": ["velocity", "speed", "u"],
            "流量": ["flow", "rate"],
        }

        # Comparison keywords
        self._comparison_keywords = [
            "vs", "versus", "对比", "比较", "compare", "difference",
            "delta", "ratio", "relative", "和", "与"
        ]

    def parse_instruction(
        self,
        instruction: str,
        manifest: ResultManifest,
    ) -> ActionPlan:
        """
        Parse natural language instruction into action plan

        Args:
            instruction: Natural language instruction from engineer
            manifest: Available resources in result directory

        Returns:
            ActionPlan with derived actions
        """
        instruction_lower = instruction.lower()

        # Detect primary intent
        intent = self._detect_intent(instruction_lower)

        # Extract available asset types
        available_assets = self._get_available_asset_types(manifest)

        # Generate actions based on intent
        actions = []
        missing_assets = []

        if intent == "plot":
            actions, missing_assets = self._parse_plot_instruction(
                instruction, instruction_lower, available_assets
            )
        elif intent == "section":
            actions, missing_assets = self._parse_section_instruction(
                instruction, instruction_lower, available_assets
            )
        elif intent == "metric":
            actions, missing_assets = self._parse_metric_instruction(
                instruction, instruction_lower, available_assets
            )
        elif intent == "compare":
            actions, missing_assets = self._parse_compare_instruction(
                instruction, instruction_lower, available_assets, manifest
            )
        elif intent == "reorder":
            actions, missing_assets = self._parse_reorder_instruction(
                instruction, instruction_lower
            )
        elif intent == "mixed":
            # Multiple intents detected
            if "plot" in instruction_lower or "图" in instruction:
                plot_actions, plot_missing = self._parse_plot_instruction(
                    instruction, instruction_lower, available_assets
                )
                actions.extend(plot_actions)
                missing_assets.extend(plot_missing)
            if "section" in instruction_lower or "截面" in instruction:
                section_actions, section_missing = self._parse_section_instruction(
                    instruction, instruction_lower, available_assets
                )
                actions.extend(section_actions)
                missing_assets.extend(section_missing)
        else:
            # Unknown intent - create generic action
            actions.append(Action(
                action_type=ActionType.GENERATE_PLOT,
                parameters={"description": instruction},
                confidence=0.3,
                requires_assets=["field_data"],
            ))

        # Calculate overall confidence
        confidence = self._calculate_confidence(actions, missing_assets)

        return ActionPlan(
            actions=actions,
            detected_intent=intent,
            missing_assets=list(set(missing_assets)),
            confidence=confidence,
            raw_instruction=instruction,
        )

    def _detect_intent(self, instruction: str) -> str:
        """Detect primary intent from instruction"""
        instruction_lower = instruction.lower()

        # Check for reorder intent
        if any(kw in instruction_lower for kw in ["顺序", "order", "排列", "按"]):
            return "reorder"

        # Check for plot intent first - "对比云图" is a plot, not data comparison
        # If followed by plot keywords, treat as plot
        plot_keywords = ["云图", "等值线", "线图", "矢量图", "流线", "图表",
                        "contour", "plot", "chart", "graph", "line", "vector", "streamline"]
        if any(kw in instruction_lower for kw in plot_keywords):
            return "plot"

        # Check for comparison intent (only if not a plot comparison)
        if any(kw in instruction_lower for kw in self._comparison_keywords):
            return "compare"

        # Check for metric intent
        if any(kw in instruction_lower for kw in ["计算", "calculate", "metric", "度量", "系数"]):
            return "metric"

        # Check for section intent - flatten the values dict to check all keywords
        section_keywords_flat = []
        for kw_list in self._section_keywords.values():
            section_keywords_flat.extend(kw_list)
        # Also include the Chinese keys
        section_keywords_flat.extend(self._section_keywords.keys())

        if any(kw in instruction_lower for kw in section_keywords_flat):
            return "section"

        # Check for plot intent (default)
        if any(kw in instruction_lower for kw in ["图", "plot", "画", "生成", "显示"]):
            return "plot"

        # Default to plot
        return "plot"

    def _parse_plot_instruction(
        self,
        instruction: str,
        instruction_lower: str,
        available_assets: List[str],
    ) -> Tuple[List[Action], List[str]]:
        """Parse plot-related instruction

        Supports multi-field requests like "压力和速度的对比云图"
        """
        actions = []
        missing = []

        # Extract plot type
        plot_type = self._extract_plot_type(instruction_lower)

        # Extract plane/location
        plane = self._extract_plane(instruction_lower)

        # Extract fields - support multiple fields
        fields = self._extract_field_names(instruction_lower)

        # Create an action for each field
        for field in fields:
            # Build parameters
            parameters = {
                "field": field,
                "plot_type": plot_type,
            }
            if plane:
                parameters["plane"] = plane

            # Check required assets
            required = ["field_data"]
            if plot_type == "contour":
                required.append("field_data")
            elif plot_type == "line" and "centerline" in instruction_lower:
                required.append("line_data")

            field_missing = [a for a in required if a not in available_assets]
            missing.extend(field_missing)

            actions.append(Action(
                action_type=ActionType.GENERATE_PLOT,
                parameters=parameters,
                confidence=0.8 if not field_missing else 0.5,
                requires_assets=required,
            ))

        return actions, missing

    def _parse_section_instruction(
        self,
        instruction: str,
        instruction_lower: str,
        available_assets: List[str],
    ) -> Tuple[List[Action], List[str]]:
        """Parse section extraction instruction

        Supports multi-section requests like "提取三个截面：z=0.2, z=0.5, z=0.8"
        """
        actions = []
        missing = []

        # Extract planes/locations - support multiple planes
        planes = self._extract_planes(instruction_lower)
        if not planes:
            planes = ["auto"]  # Auto-detect

        # Extract field
        field = self._extract_field_name(instruction_lower)

        # Create an action for each plane
        for plane in planes:
            parameters = {
                "plane": plane,
                "field": field,
            }

            # Check required assets
            required = ["field_data"]
            plane_missing = [a for a in required if a not in available_assets]
            missing.extend(plane_missing)

            actions.append(Action(
                action_type=ActionType.EXTRACT_SECTION,
                parameters=parameters,
                confidence=0.8 if not plane_missing else 0.5,
                requires_assets=required,
            ))

        return actions, missing

    def _parse_metric_instruction(
        self,
        instruction: str,
        instruction_lower: str,
        available_assets: List[str],
    ) -> Tuple[List[Action], List[str]]:
        """Parse metric calculation instruction"""
        actions = []
        missing_assets = []

        # Extract metric type
        metric_type = self._extract_metric_type(instruction_lower)

        # Extract location/filter
        location = self._extract_location(instruction_lower)

        parameters = {
            "metric_type": metric_type,
        }
        if location:
            parameters["location"] = location

        # Check required assets
        required = ["field_data"]
        missing = [a for a in required if a not in available_assets]

        actions.append(Action(
            action_type=ActionType.CALCULATE_METRIC,
            parameters=parameters,
            confidence=0.8 if not missing else 0.5,
            requires_assets=required,
        ))

        return actions, missing

    def _parse_compare_instruction(
        self,
        instruction: str,
        instruction_lower: str,
        available_assets: List[str],
        manifest: ResultManifest,
    ) -> Tuple[List[Action], List[str]]:
        """Parse comparison instruction"""
        actions = []
        missing = []

        # Extract items to compare
        items = self._extract_comparison_items(instruction_lower)

        if len(items) < 2:
            # Need at least 2 items to compare
            missing.append("comparison_targets")
        else:
            # Extract field/variable
            field = self._extract_field_name(instruction_lower)

            parameters = {
                "items": items,
                "field": field,
                "comparison_type": "side_by_side",
            }

            required = ["field_data"]
            required_missing = [a for a in required if a not in available_assets]
            missing.extend(required_missing)

            actions.append(Action(
                action_type=ActionType.COMPARE_DATA,
                parameters=parameters,
                confidence=0.8 if not required_missing else 0.5,
                requires_assets=required,
            ))

        return actions, missing

    def _parse_reorder_instruction(
        self,
        instruction: str,
        instruction_lower: str,
    ) -> Tuple[List[Action], List[str]]:
        """Parse content reordering instruction"""
        actions = []
        missing_assets = []

        # Extract sequence
        sequence = self._extract_sequence(instruction_lower)

        parameters = {
            "sequence": sequence,
        }

        actions.append(Action(
            action_type=ActionType.REORDER_CONTENT,
            parameters=parameters,
            confidence=0.7,
            requires_assets=[],  # Reordering doesn't need specific assets
        ))

        return actions, missing_assets

    # ========================================================================
    # Helper Methods for NL Parsing
    # ========================================================================

    def _extract_field_name(self, instruction: str) -> str:
        """Extract field/variable name from instruction"""
        fields = self._extract_field_names(instruction)
        return fields[0] if fields else "magnitude"  # Default

    def _extract_field_names(self, instruction: str) -> List[str]:
        """Extract all field/variable names from instruction

        Supports multi-field requests like "压力和速度"
        """
        # Common CFD field names
        field_patterns = {
            "压力": "pressure",
            "pressure": "pressure",
            "p": "pressure",
            "速度": "velocity",
            "velocity": "velocity",
            "u": "velocity",
            "温度": "temperature",
            "temperature": "temperature",
            "t": "temperature",
            "湍动能": "k",
            "tke": "k",
            "壁面距离": "wall_distance",
            "y_plus": "y_plus",
        }

        found_fields = []
        for keyword, field in field_patterns.items():
            if keyword in instruction:
                if field not in found_fields:
                    found_fields.append(field)

        return found_fields if found_fields else ["magnitude"]  # Default

    def _extract_plot_type(self, instruction: str) -> str:
        """Extract plot type from instruction"""
        if "云图" in instruction or "contour" in instruction:
            return "contour"
        if "等值线" in instruction or "iso" in instruction:
            # "等值线" typically means line plot of contours, not filled contour
            return "line"
        if "线图" in instruction or "line" in instruction:
            return "line"
        if "矢量" in instruction or "vector" in instruction:
            return "vector"
        if "流线" in instruction or "streamline" in instruction:
            return "streamline"
        return "contour"  # Default

    def _extract_plane(self, instruction: str) -> Optional[str]:
        """Extract plane specification from instruction"""
        planes = self._extract_planes(instruction)
        return planes[0] if planes else None

    def _extract_planes(self, instruction: str) -> List[str]:
        """Extract all plane specifications from instruction

        Supports multi-plane requests like "z=0.2, z=0.5, z=0.8"
        """
        planes = []

        # Look for multiple z= patterns (e.g., "z=0.2, z=0.5, z=0.8")
        z_matches = re.findall(r'z\s*=\s*([\d.]+)', instruction)
        for z_val in z_matches:
            planes.append(f"z={z_val}")

        # If no specific z values found, look for explicit plane names
        if not planes:
            if "xy" in instruction or "水平" in instruction:
                planes.append("xy")
            elif "xz" in instruction or "侧视" in instruction:
                planes.append("xz")
            elif "yz" in instruction or "正视" in instruction:
                planes.append("yz")
            elif "中平面" in instruction:
                planes.append("midplane")
            elif "壁面" in instruction:
                planes.append("wall")

        return planes

    def _extract_metric_type(self, instruction: str) -> str:
        """Extract metric type from instruction"""
        if "阻力" in instruction or "drag" in instruction:
            return "drag_coefficient"
        if "升力" in instruction or "lift" in instruction:
            return "lift_coefficient"
        if "压力" in instruction or "pressure" in instruction:
            return "pressure_drop"
        if "最高" in instruction:
            return "max_value"
        if "最低" in instruction:
            return "min_value"
        if "平均" in instruction:
            return "average"
        return "value"  # Default

    def _extract_location(self, instruction: str) -> Optional[str]:
        """Extract location specification from instruction"""
        if "inlet" in instruction or "入口" in instruction:
            return "inlet"
        if "outlet" in instruction or "出口" in instruction:
            return "outlet"
        if "wall" in instruction or "壁面" in instruction:
            return "wall"
        return None

    def _extract_comparison_items(self, instruction: str) -> List[str]:
        """Extract items to compare from instruction"""
        items = []

        # Look for common patterns like "A vs B" or "A 和 B"
        # Use a more permissive regex that handles Unicode word characters
        vs_match = re.search(r'([\w\u4e00-\u9fff]+)\s+(?:vs|和|与)\s+([\w\u4e00-\u9fff]+)', instruction)
        if vs_match:
            items.extend([vs_match.group(1), vs_match.group(2)])

        # Look for "inlet/outlet" pattern
        if "inlet" in instruction and "outlet" in instruction:
            items.extend(["inlet", "outlet"])

        # Look for Chinese "入口" and "出口"
        if "入口" in instruction and "出口" in instruction:
            items.extend(["inlet", "outlet"])

        return list(set(items))

    def _extract_sequence(self, instruction: str) -> List[str]:
        """Extract content sequence from instruction"""
        sequence = []

        # Look for patterns like "A -> B -> C" or "A, then B, then C"
        if "->" in instruction:
            sequence = [s.strip() for s in instruction.split("->")]
        elif "，" in instruction:
            parts = instruction.split("，")
            for part in parts:
                if "然后" in part:
                    sub_parts = part.split("然后")
                    sequence.extend([s.strip() for s in sub_parts])
                else:
                    sequence.append(part.strip())
        elif "," in instruction:
            # Handle English commas
            parts = instruction.split(",")
            for part in parts:
                if " then " in part:
                    sub_parts = part.split("then")
                    sequence.extend([s.strip() for s in sub_parts])
                else:
                    sequence.append(part.strip())
        else:
            # Try to extract keywords
            if "总览" in instruction:
                sequence.append("overview")
            if "截面" in instruction:
                sequence.append("sections")
            if "图表" in instruction:
                sequence.append("plots")
            if "数据表" in instruction:
                sequence.append("tables")

        return sequence

    def _get_available_asset_types(self, manifest: ResultManifest) -> List[str]:
        """Get list of available asset types from manifest

        Maps ResultAsset.asset_type to logical asset names used by actions.
        """
        # Mapping from ResultAsset asset_type to logical asset names
        asset_type_mapping = {
            "field": ["field_data"],
            "contour_plot": ["plot_data", "field_data"],
            "line_plot": ["line_data", "plot_data"],
            "vector_plot": ["vector_data", "plot_data"],
            "metric": ["metric_data"],
        }

        logical_assets = set()

        for asset in manifest.assets:
            # Add direct asset type
            logical_assets.add(asset.asset_type)

            # Add mapped logical types
            if asset.asset_type in asset_type_mapping:
                logical_assets.update(asset_type_mapping[asset.asset_type])

        return list(logical_assets)

    def _calculate_confidence(self, actions: List[Action], missing: List[str]) -> float:
        """Calculate overall confidence for the action plan"""
        if not actions:
            return 0.0

        # Average action confidence
        action_confidence = sum(a.confidence for a in actions) / len(actions)

        # Penalize missing assets
        missing_penalty = 0.2 * len(missing)

        return max(0.0, min(1.0, action_confidence - missing_penalty))


# ============================================================================
# Convenience Functions
# ============================================================================

def create_action_plan(
    instruction: str,
    manifest: ResultManifest,
    executor: Optional[NLPostprocessExecutor] = None,
) -> ActionPlan:
    """
    Convenience function to create action plan from NL instruction

    Args:
        instruction: Natural language instruction
        manifest: Available resources
        executor: Optional existing executor instance

    Returns:
        ActionPlan
    """
    if executor is None:
        executor = NLPostprocessExecutor()

    return executor.parse_instruction(instruction, manifest)


def execute_action_plan(
    action_plan: ActionPlan,
    manifest: ResultManifest,
) -> ActionLog:
    """
    Execute an action plan (placeholder - actual execution in Phase 2)

    Args:
        action_plan: Action plan to execute
        manifest: Available resources

    Returns:
        ActionLog with execution results
    """
    log = ActionLog(
        timestamp=time.time(),
        action_plan=action_plan,
    )

    if not action_plan.is_executable():
        log.errors.append(f"Cannot execute: missing assets {action_plan.missing_assets}")
        return log

    # Placeholder execution
    for i, action in enumerate(action_plan.actions):
        try:
            result = {
                "action": action.action_type.value,
                "parameters": action.parameters,
                "status": "pending",  # Will be filled by actual executor
            }
            log.add_result(i, result)
        except Exception as e:
            log.errors.append(f"Action {i} failed: {e}")

    return log


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "ActionType",
    "Action",
    "ActionPlan",
    "ActionLog",
    "NLPostprocessExecutor",
    "create_action_plan",
    "execute_action_plan",
]
