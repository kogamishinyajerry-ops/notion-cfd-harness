#!/usr/bin/env python3
"""
Postprocess Runner - 核心实现

复用策略:
- 残差解析: Phase 3 自有 OpenFOAMResultParser（与 Phase 3 PostprocessResult 类型对齐）
- 场数据提取: Phase 3 FieldDataExtractor（简化版，适配 Phase 3 schema）
- Phase 2 对应组件: knowledge_compiler.phase2.execution_layer.postprocess_runner
  （使用不同类型系统: FieldData/ResidualSummary/StandardPostprocessResult）
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from knowledge_compiler.phase3.schema import (
    PostprocessArtifact,
    PostprocessFormat,
    PostprocessJob,
    PostprocessRequest,
    PostprocessResult,
    PostprocessStatus,
    SolverResult,
)


class OpenFOAMResultParser:
    """OpenFOAM 结果解析器"""

    @staticmethod
    def parse_residuals(log_content: str) -> Dict[str, Any]:
        """解析残差信息"""
        residuals = {"initial": {}, "final": {}, "iterations": []}

        # 解析初始残差
        for match in re.finditer(r'solving for (.+), initial residual = ([\d.e-]+)', log_content):
            var_name = match.group(1)
            residuals["initial"][var_name] = float(match.group(2))

        # 解析最终残差
        for match in re.finditer(r'solving for (.+), Final residual = ([\d.e-]+), No Iterations (\d+)', log_content):
            var_name = match.group(1)
            residuals["final"][var_name] = float(match.group(2))
            residuals["iterations"].append({
                "variable": var_name,
                "final_residual": float(match.group(2)),
                "iterations": int(match.group(3))
            })

        return residuals

    @staticmethod
    def parse_convergence(log_content: str) -> Dict[str, Any]:
        """解析收敛信息"""
        convergence = {
            "converged": False,
            "reason": "",
            "final_time": None,
        }

        # 检查是否收敛
        if "solution converges" in log_content.lower():
            convergence["converged"] = True
            convergence["reason"] = "Solution converges"

        # 提取最终时间
        for match in re.finditer(r'End = ([\d.e-]+)', log_content):
            convergence["final_time"] = float(match.group(1))

        # 检查错误
        if "error" in log_content.lower() or "failed" in log_content.lower():
            convergence["converged"] = False
            convergence["reason"] = "Simulation failed or error detected"

        return convergence

    @staticmethod
    def find_field_files(case_dir: str) -> Dict[str, str]:
        """查找场文件目录"""
        field_dirs = {}
        case_path = Path(case_dir)

        # 检查常见的处理器时间步目录
        for proc_dir in case_path.glob("processor*"):
            if proc_dir.is_dir():
                fields_dir = proc_dir / "0"  # 初始时间步
                if fields_dir.exists():
                    for field_file in fields_dir.glob("*"):
                        if field_file.is_file() and not field_file.name.startswith("."):
                            field_dirs[field_file.name] = str(field_file)

        # 检查串行情况
        serial_fields = case_path / "0"
        if serial_fields.exists():
            for field_file in serial_fields.glob("*"):
                if field_file.is_file() and not field_file.name.startswith("."):
                    field_dirs[field_file.name] = str(field_file)

        return field_dirs


@dataclass
class FieldDataExtractor:
    """场数据提取器"""

    @staticmethod
    def extract_field_summary(field_path: str) -> Dict[str, Any]:
        """提取场文件摘要信息"""
        field_path = Path(field_path)

        if not field_path.exists():
            return {"name": field_path.name, "exists": False}

        # 简单的文件信息
        stat = field_path.stat()

        # 尝试读取并解析场文件 (简化版，实际需要完整的 foamFile 解析)
        info = {
            "name": field_path.name,
            "exists": True,
            "size_bytes": stat.st_size,
            "modified_time": stat.st_mtime,
        }

        # 尝试读取前几行获取场类型信息
        try:
            with open(field_path, 'r') as f:
                first_line = f.readline().strip()
                if first_line.startswith("FoamFile"):
                    info["format"] = "OpenFOAM"
                elif first_line.startswith("volScalarField"):
                    info["class"] = "volScalarField"
                elif first_line.startswith("volVectorField"):
                    info["class"] = "volVectorField"
        except Exception:
            pass

        return info


class PostprocessRunner:
    """后处理运行器"""

    def __init__(self, output_dir: str = ""):
        self.output_dir = output_dir
        self.parser = OpenFOAMResultParser()
        self.extractor = FieldDataExtractor()

    def run(
        self,
        request: PostprocessRequest,
    ) -> PostprocessResult:
        """执行后处理"""
        result = PostprocessResult(
            result_id=f"PP-RESULT-{time.time():.0f}",
            status=PostprocessStatus.RUNNING,
        )

        try:
            # 1. 解析求解器日志
            if request.solver_result:
                result.field_data["residuals"] = self.parser.parse_residuals(
                    request.solver_result.stdout
                )
                result.convergence_info = self.parser.parse_convergence(
                    request.solver_result.stdout
                )

            # 2. 解析结果目录
            if request.result_directory:
                field_files = self.parser.find_field_files(request.result_directory)
                result.field_data["field_files"] = {
                    name: self.extractor.extract_field_summary(path)
                    for name, path in field_files.items()
                }

            # 3. 生成 JSON 格式输出
            if PostprocessFormat.JSON in request.output_formats:
                artifact = self._create_json_artifact(result)
                result.add_artifact(artifact)

            # 4. 生成 CSV 格式输出
            if PostprocessFormat.CSV in request.output_formats:
                artifact = self._create_csv_artifact(result)
                result.add_artifact(artifact)

            # 5. 生成报告
            if request.generate_report:
                artifact = self._create_report_artifact(result)
                result.add_artifact(artifact)

            result.status = PostprocessStatus.COMPLETED
            result.completed_at = time.time()
            result.processing_time = result.completed_at - result.created_at

        except Exception as e:
            result.status = PostprocessStatus.FAILED
            result.error_message = str(e)
            result.completed_at = time.time()

        return result

    def _create_json_artifact(self, result: PostprocessResult) -> PostprocessArtifact:
        """创建 JSON 格式产物"""
        output_path = os.path.join(self.output_dir, "postprocess_result.json")

        output_data = {
            "result_id": result.result_id,
            "status": result.status.value,
            "residuals": result.field_data.get("residuals", {}),
            "convergence": result.convergence_info,
            "field_files": list(result.field_data.get("field_files", {}).keys()),
            "processing_time": result.processing_time,
        }

        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(output_data, f, indent=2)

        return PostprocessArtifact(
            format=PostprocessFormat.JSON,
            file_path=output_path,
            metadata={"fields": list(output_data.keys())}
        )

    def _create_csv_artifact(self, result: PostprocessResult) -> PostprocessArtifact:
        """创建 CSV 格式产物 (残差数据)"""
        import csv

        output_path = os.path.join(self.output_dir, "residuals.csv")

        residuals = result.field_data.get("residuals", {})
        iterations = residuals.get("iterations", [])

        if self.output_dir and iterations:
            with open(output_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=["variable", "final_residual", "iterations"])
                writer.writeheader()
                writer.writerows(iterations)

        return PostprocessArtifact(
            format=PostprocessFormat.CSV,
            file_path=output_path,
            metadata={"n_variables": len(iterations)}
        )

    def _create_report_artifact(self, result: PostprocessResult) -> PostprocessArtifact:
        """创建报告产物"""
        report_path = os.path.join(self.output_dir, "postprocess_report.txt")

        lines = [
            "=" * 60,
            "Postprocess Report",
            "=" * 60,
            f"Result ID: {result.result_id}",
            f"Status: {result.status.value}",
            "",
            "Convergence:",
            "-" * 40,
        ]

        for key, value in result.convergence_info.items():
            lines.append(f"  {key}: {value}")

        lines.extend([
            "",
            "Residuals:",
            "-" * 40,
        ])

        residuals = result.field_data.get("residuals", {})
        iterations = residuals.get("iterations", [])
        for item in iterations:
            lines.append(f"  {item.get('variable')}: {item.get('final_residual')} ({item.get('iterations')} iters)")

        if result.error_message:
            lines.extend([
                "",
                "Error:",
                "-" * 40,
                result.error_message,
            ])

        lines.append(f"\nProcessing Time: {result.processing_time:.2f}s")

        if self.output_dir:
            with open(report_path, 'w') as f:
                f.write('\n'.join(lines))

        return PostprocessArtifact(
            format=PostprocessFormat.HTML_REPORT,
            file_path=report_path,
            metadata={"n_lines": len(lines)}
        )


@dataclass
class BatchPostprocessRunner:
    """批量后处理运行器"""

    output_dir: str = ""
    max_concurrent: int = 2

    def run_batch(self, requests: List[PostprocessRequest]) -> List[PostprocessResult]:
        """批量执行后处理"""
        runner = PostprocessRunner(output_dir=self.output_dir)
        results = []

        for i, request in enumerate(requests):
            # 为每个请求设置单独的输出子目录
            runner.output_dir = os.path.join(self.output_dir, f"job_{i}")
            result = runner.run(request)
            results.append(result)

        return results


def run_postprocess(
    solver_result: SolverResult,
    result_directory: str = "",
    output_formats: Optional[List[PostprocessFormat]] = None,
    output_dir: str = "",
) -> PostprocessResult:
    """便捷函数：执行后处理"""
    if output_formats is None:
        output_formats = [PostprocessFormat.JSON, PostprocessFormat.CSV]

    request = PostprocessRequest(
        solver_result=solver_result,
        result_directory=result_directory,
        output_formats=output_formats,
        generate_report=True,
    )

    runner = PostprocessRunner(output_dir=output_dir)
    return runner.run(request)


def create_postprocess_job(
    solver_result: SolverResult,
    result_directory: str = "",
    output_formats: Optional[List[PostprocessFormat]] = None,
) -> PostprocessJob:
    """创建后处理作业"""
    if output_formats is None:
        output_formats = [PostprocessFormat.JSON]

    request = PostprocessRequest(
        solver_result=solver_result,
        result_directory=result_directory,
        output_formats=output_formats,
        generate_report=True,
    )

    return PostprocessJob(request=request)
