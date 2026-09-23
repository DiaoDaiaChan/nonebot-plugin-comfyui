"""
向后兼容模块：handler.py
具体处理器逻辑已解耦迁移至 nonebot_plugin_comfyui.handlers
"""
from .handlers import (
    comfyui_generate_handler as comfyui_handler,
    queue_handler,
    api_handler,
    today_girl_handler,
    danbooru_handler,
    llm_handler,
    get_checkpoints_handler as get_checkpoints,
    get_loras_handler as get_loras,
    get_user_tasks_handler as get_task
)

__all__ = [
    "comfyui_handler",
    "queue_handler",
    "api_handler",
    "today_girl_handler",
    "danbooru_handler",
    "llm_handler",
    "get_checkpoints",
    "get_loras",
    "get_task"
]
