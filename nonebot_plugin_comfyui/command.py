"""
向后兼容模块：command.py
所有具体实现与 Matcher 定义已迁移至 nonebot_plugin_comfyui.commands
"""
from .commands import (
    comfyui_cmd as comfyui,
    queue_cmd as queue,
    api_cmd as api,
    help_cmd as help_,
    view_workflow_cmd as view_workflow,
    backend_status_cmd as backend,
    today_girl_cmd as today_girl,
    dan_cmd,
    llm_cmd as llm,
    get_ckpt_cmd,
    get_loras_cmd,
    get_task_cmd,
    REGISTERED_COMMANDS as reg_command
)

__all__ = [
    "comfyui",
    "queue",
    "api",
    "help_",
    "view_workflow",
    "backend",
    "today_girl",
    "dan_cmd",
    "llm",
    "get_ckpt_cmd",
    "get_loras_cmd",
    "get_task_cmd",
    "reg_command"
]
