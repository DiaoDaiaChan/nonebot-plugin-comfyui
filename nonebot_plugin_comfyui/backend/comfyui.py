"""
向后兼容模块：backend/comfyui.py
核心实现已全面拆分重构至 services 与 handlers 模块。
此文件提供对旧版 ComfyUI, ComfyuiTaskQueue, RespMsg, ComfyuiHistory 的向下兼容接口。
"""
from typing import Any, Optional
from nonebot import Bot
from nonebot.adapters import Event
from argparse import Namespace
from ..config import config, BACKEND_URL_LIST
from ..constants import REFLEX_DICT, MAX_SEED
from ..handlers.generate import GenerationContext, TaskRecordManager, comfyui_generate_handler
from ..services.comfy_client import comfy_client
from ..services.workflow_engine import workflow_engine


class RespMsg:
    def __init__(self, task_id: str = "", backend_url: str = ""):
        self.task_id = task_id
        self.backend_url = backend_url
        self.backend_index = BACKEND_URL_LIST.index(backend_url) if backend_url in BACKEND_URL_LIST else -1
        self.error_msg = ""
        self.resp_text = ""
        self.resp_img = ""
        self.resp_video: list[Any] = []
        self.resp_audio: list[Any] = []
        self.media_url: dict[str, Any] = {}
        self.image_byte: list[Any] = []


class ComfyuiTaskQueue:
    all_task_id = TaskRecordManager.all_task_ids
    user_task = TaskRecordManager.user_tasks

    @classmethod
    async def get_user_task(cls, user_id: str) -> dict[str, Any]:
        return TaskRecordManager.get_user_tasks(user_id)

    @classmethod
    async def set_user_task(
        cls,
        user_id: str,
        task_id: str,
        backend_index: int,
        work_flow: str,
        status: str = "pending"
    ) -> None:
        TaskRecordManager.record_task(user_id, task_id, backend_index, work_flow, status)

    @classmethod
    async def update_task_status(cls, task_id: str, status: str) -> None:
        TaskRecordManager.update_status(task_id, status)


class ComfyuiHistory:
    def __init__(
        self,
        bot: Bot | None = None,
        event: Event | None = None,
        backend: str | None = None,
        task_id: str | None = None,
        **kwargs: Any
    ):
        self.bot = bot
        self.event = event
        self.task_id = task_id
        if backend and backend.isdigit():
            idx = int(backend)
            self.backend_url = BACKEND_URL_LIST[idx] if 0 <= idx < len(BACKEND_URL_LIST) else config.comfyui_url
        elif backend:
            self.backend_url = backend
        else:
            self.backend_url = config.comfyui_url

        self.all_task_dict: dict[str, Any] = {}

    async def get_history_task(self, backend_url: str) -> set[str]:
        hist = await comfy_client.request("GET", f"{backend_url}/history")
        self.all_task_dict = hist
        return set(hist.keys())

    async def get_task(self, task_id: str | None = None) -> dict[str, Any]:
        if not task_id:
            return {}
        return self.all_task_dict.get(task_id, {})


class ComfyUI(GenerationContext):
    """向下兼容的 ComfyUI 类，继承自新的 GenerationContext"""

    def __init__(self, nb_event: Event, bot: Bot, args: Optional[Namespace] = None, **kwargs: Any):
        if args is None:
            args = Namespace(**kwargs)
        super().__init__(bot=bot, event=nb_event, args=args, **kwargs)
        self.unimessage = None

    async def exec_generate(self, daily_call: Any = None) -> None:
        await self.execute()

    async def send_all_msg(self) -> None:
        await self.send_responses()


__all__ = [
    "ComfyUI",
    "ComfyuiTaskQueue",
    "RespMsg",
    "ComfyuiHistory",
    "MAX_SEED",
    "REFLEX_DICT"
]
