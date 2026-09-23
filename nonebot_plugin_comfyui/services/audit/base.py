from abc import ABC, abstractmethod
from typing import Any
import base64
from io import BytesIO
from PIL import Image
from nonebot import logger
from ...config import config


def prepare_audit_image(image_input: bytes | str) -> tuple[str, Image.Image]:
    """预处理图像：转成 PIL 并进行安全缩放，返回 (base64_str, PIL.Image)"""
    if isinstance(image_input, str):
        img_bytes = base64.b64decode(image_input)
    else:
        img_bytes = image_input

    img = Image.open(BytesIO(img_bytes)).convert("RGB")

    # 压缩处理以加速审核 (修复 PIL.resize 原地修改未赋值的 bug)
    if config.comfyui_audit_comp:
        max_res = 640
        w, h = img.size
        old_res = w * h
        if old_res > (max_res ** 2):
            if w <= h:
                ratio = h / w
                new_w = max_res / (ratio ** 0.5)
                new_h = new_w * ratio
            else:
                ratio = w / h
                new_h = max_res / (ratio ** 0.5)
                new_w = new_h * ratio

            new_w_int, new_h_int = round(new_w), round(new_h)
            img = img.resize((new_w_int, new_h_int), Image.LANCZOS)
            logger.info(f"审核图片尺寸已压缩调整至: {new_w_int}x{new_h_int}")

    buf = BytesIO()
    img.save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return b64, img


class BaseAuditor(ABC):
    """审核器抽象基类"""

    @abstractmethod
    async def audit(self, image_bytes: bytes, group_id: str = "") -> dict[str, Any]:
        """
        审核输入图片。
        返回字典结构:
        {
            "is_nsfw": bool,
            "message": str,
            "tags": Any
        }
        """
        pass
