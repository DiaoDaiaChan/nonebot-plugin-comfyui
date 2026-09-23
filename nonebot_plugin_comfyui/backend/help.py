"""
向后兼容模块：backend/help.py
实现已迁移至 nonebot_plugin_comfyui.utils.render 与 services.workflow_engine
"""
from typing import Any
from ..services.workflow_engine import workflow_engine
from ..utils.render import render_workflows_html


class ComfyuiHelp:
    def __init__(self) -> None:
        pass

    @staticmethod
    async def get_reflex_json(search: Any = None) -> tuple[int, list[dict], list[str]]:
        wf_names = workflow_engine.list_workflows()
        matched_names = []
        matched_reflex = []

        if isinstance(search, int):
            if 1 <= search <= len(wf_names):
                name = wf_names[search - 1]
                _, r = await workflow_engine.load_workflow_files(name)
                return 1, [r], [name]
            return 0, [], []

        for name in wf_names:
            if not search or (isinstance(search, str) and search in name):
                try:
                    _, r = await workflow_engine.load_workflow_files(name)
                    matched_names.append(name)
                    matched_reflex.append(r)
                except Exception:
                    pass

        return len(matched_names), matched_reflex, matched_names

    async def get_html(self, search: Any = None) -> tuple[str, Any]:
        s_str = str(search) if search is not None else None
        return await render_workflows_html(s_str)


__all__ = ["ComfyuiHelp"]