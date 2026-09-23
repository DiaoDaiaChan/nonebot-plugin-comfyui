import asyncio
import os
import tempfile
from typing import Any
from nonebot import logger
from ...config import config
from ...constants import NUDENET_UNSAFE_LABELS
from .base import BaseAuditor


class LocalNudeNetAuditor(BaseAuditor):
    """本地 NudeNet 审核器（延迟加载）"""

    def __init__(self) -> None:
        self._detector = None
        self._load_lock = asyncio.Lock()

    def _ensure_loaded(self) -> Any:
        if self._detector is not None:
            return self._detector

        try:
            from nudenet import NudeDetector
        except ImportError as e:
            logger.error(
                f"本地 NudeNet 依赖缺失: {e}。\n"
                f"请手动安装: pip install nudenet"
            )
            raise e

        model_path = config.comfyui_nude_model_path if config.comfyui_nude_model_path else None
        logger.info("正在加载本地 NudeNet 检测器...")
        self._detector = NudeDetector(model_path=model_path, inference_resolution=640)
        logger.info("NudeNet 检测器加载就绪")
        return self._detector

    async def audit(self, image_bytes: bytes, group_id: str = "") -> dict[str, Any]:
        audit_info = {
            "is_nsfw": False,
            "message": "",
            "tags": []
        }

        try:
            async with self._load_lock:
                detector = await asyncio.to_thread(self._ensure_loaded)
        except Exception as e:
            audit_info["message"] = f"NudeNet 加载失败: {e}"
            return audit_info

        # 写入临时文件供 NudeNet 检测
        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
                tmp_file.write(image_bytes)
                tmp_path = tmp_file.name

            detections = await asyncio.to_thread(detector.detect, tmp_path)
        except Exception as e:
            logger.error(f"NudeNet 检测失败: {e}")
            audit_info["is_nsfw"] = True
            audit_info["message"] = f"NudeNet 检测错误: {e}"
            return audit_info
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        unsafe_found = []
        msg_lines = []

        for item in detections:
            label = item.get('class')
            score = item.get('score', 0.0)
            if score < 0.5:
                continue

            pct = f"{int(score * 100)}%"
            if label in NUDENET_UNSAFE_LABELS:
                unsafe_found.append(f"{label} ({pct})")
                msg_lines.append(f"⚠️ [{label}]: {pct}")
            else:
                msg_lines.append(f"ℹ️ [{label}]: {pct}")

        is_nsfw = len(unsafe_found) > 0
        status_text = "包含敏感内容" if is_nsfw else "图片安全"
        full_msg = f"NudeNet 结果: {status_text}\n" + "\n".join(msg_lines)

        audit_info["tags"] = detections
        audit_info["message"] = full_msg
        audit_info["is_nsfw"] = is_nsfw
        return audit_info


local_nudenet_auditor = LocalNudeNetAuditor()
