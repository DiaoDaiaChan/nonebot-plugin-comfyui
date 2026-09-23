import asyncio
from typing import Any
from nonebot import logger
from ...config import config
from .remote import remote_tagger_auditor
from .local_wd import local_wd_auditor
from .local_nudenet import local_nudenet_auditor
from .text_audit import text_audit, clean_llm_response


async def audit_image(image_bytes: bytes, group_id: str = "") -> dict[str, Any]:
    """统一图片审核调度入口"""
    if not config.comfyui_audit:
        return {"is_nsfw": False, "message": "审核已关闭", "tags": {}}

    # 1. 双重本地审核 (WD14 + NudeNet)
    if config.comfyui_dual_audit:
        logger.info("执行双重审核 (WD14 + NudeNet)...")
        res_wd, res_nude = await asyncio.gather(
            local_wd_auditor.audit(image_bytes, group_id),
            local_nudenet_auditor.audit(image_bytes, group_id),
            return_exceptions=False
        )
        is_nsfw = res_wd["is_nsfw"] or res_nude["is_nsfw"]
        return {
            "is_nsfw": is_nsfw,
            "message": f"{res_wd['message']}\n{res_nude['message']}",
            "tags": {"wd": res_wd.get("tags"), "nude": res_nude.get("tags")}
        }

    # 2. 单模型本地审核
    if config.comfyui_audit_local:
        if config.comfyui_audit_model == 1:
            return await local_wd_auditor.audit(image_bytes, group_id)
        elif config.comfyui_audit_model == 2:
            return await local_nudenet_auditor.audit(image_bytes, group_id)

    # 3. 远程审核
    return await remote_tagger_auditor.audit(image_bytes, group_id)


__all__ = [
    "audit_image",
    "text_audit",
    "clean_llm_response",
    "remote_tagger_auditor",
    "local_wd_auditor",
    "local_nudenet_auditor",
]
