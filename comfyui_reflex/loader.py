"""
Workflow and Reflex JSON file discovery and loading utilities.
Supports both synchronous and asynchronous operations.
Pure Python, zero framework dependencies.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from .exceptions import ReflexNotFoundError, ReflexConfigError
from .models import ReflexConfig


class WorkflowLoader:
    """工作流定义与其 Reflex 配置文件的检索与加载管理器"""

    @staticmethod
    def get_workflow_paths(workflows_dir: str | Path, wf_name: str) -> tuple[Path, Path]:
        """获取工作流 API JSON 和 Reflex JSON 的路径"""
        wf_dir = Path(workflows_dir).resolve()
        api_path = wf_dir / f"{wf_name}.json"
        reflex_path = wf_dir / f"{wf_name}_reflex.json"
        return api_path, reflex_path

    @classmethod
    def list_workflows(
        cls,
        workflows_dir: str | Path,
        search: str | None = None,
        index: int | None = None
    ) -> list[str]:
        """
        列出并筛选指定目录下所有合法的工作流名称（即同时存在 .json 和 _reflex.json 的工作流）。
        
        参数:
            workflows_dir: 工作流存放目录路径
            search: 按名称子串检索
            index: 1-based 下标筛选（与旧版兼容）
        """
        wf_dir = Path(workflows_dir).resolve()
        if not wf_dir.exists():
            return []

        wf_files: list[str] = []
        for file in os.listdir(wf_dir):
            if file.endswith('.json') and not file.endswith('_reflex.json'):
                name = file[:-5]
                # 检查是否存在匹配的 reflex 文件
                reflex_file = wf_dir / f"{name}_reflex.json"
                if reflex_file.exists():
                    if search and search in name:
                        wf_files.append(name)
                    elif not search:
                        wf_files.append(name)

        if index is not None:
            if 1 <= index <= len(wf_files):
                return [wf_files[index - 1]]
            return []

        return wf_files

    @classmethod
    def load_workflow_pair(
        cls,
        workflows_dir: str | Path,
        wf_name: str,
        as_config_model: bool = False
    ) -> tuple[dict[str, Any], dict[str, Any] | ReflexConfig]:
        """
        同步加载指定工作流的 API JSON 和 Reflex JSON。
        
        参数:
            workflows_dir: 工作流目录路径
            wf_name: 工作流文件名（不含扩展名）
            as_config_model: 是否将 reflex_json 包装为 ReflexConfig 对象
        
        返回:
            (api_json, reflex_json_or_config)
        """
        api_path, reflex_path = cls.get_workflow_paths(workflows_dir, wf_name)

        if not api_path.exists() or not reflex_path.exists():
            raise ReflexNotFoundError(f"未找到工作流 {wf_name} 的完整定义文件 ({api_path} 或 {reflex_path})")

        try:
            with open(api_path, 'r', encoding='utf-8') as f:
                api_json = json.load(f)
        except Exception as e:
            raise ReflexConfigError(f"解析 API 工作流文件失败 [{api_path}]: {e}") from e

        try:
            with open(reflex_path, 'r', encoding='utf-8') as f:
                reflex_raw = json.load(f)
        except Exception as e:
            raise ReflexConfigError(f"解析 Reflex 配置文件失败 [{reflex_path}]: {e}") from e

        if as_config_model:
            return api_json, ReflexConfig(reflex_raw)
        return api_json, reflex_raw

    @classmethod
    async def load_workflow_pair_async(
        cls,
        workflows_dir: str | Path,
        wf_name: str,
        as_config_model: bool = False
    ) -> tuple[dict[str, Any], dict[str, Any] | ReflexConfig]:
        """
        异步加载指定工作流的 API JSON 和 Reflex JSON。
        使用 asyncio.to_thread 进行无阻塞文件 I/O，无需任何第三方异步文件库。
        """
        return await asyncio.to_thread(
            cls.load_workflow_pair,
            workflows_dir=workflows_dir,
            wf_name=wf_name,
            as_config_model=as_config_model
        )


load_workflow_pair = WorkflowLoader.load_workflow_pair
load_workflow_pair_async = WorkflowLoader.load_workflow_pair_async
list_workflows = WorkflowLoader.list_workflows
