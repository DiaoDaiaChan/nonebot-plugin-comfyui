from typing import Any
from nonebot import logger
from ...config import config
from ..comfy_client import comfy_client
from .base import BaseAuditor, prepare_audit_image


class RemoteTaggerAuditor(BaseAuditor):
    """远程 WD14 Tagger 审核器"""

    async def audit(self, image_bytes: bytes, group_id: str = "") -> dict[str, Any]:
        audit_info = {
            "is_nsfw": False,
            "message": "",
            "tags": {}
        }

        try:
            b64, _ = prepare_audit_image(image_bytes)
        except Exception as e:
            logger.error(f"图片预处理失败: {e}")
            audit_info["is_nsfw"] = True
            audit_info["message"] = "图片预处理失败"
            return audit_info

        payload = {"image": b64, "model": "wd14-vit-v2-git", "threshold": 0.35}
        try:
            resp_dict = await comfy_client.request(
                "POST",
                f"{config.comfyui_audit_site}/tagger/v1/interrogate",
                json_data=payload,
                timeout=15
            )
        except Exception as e:
            logger.error(f"远程审核 API 请求失败: {e}")
            audit_info["message"] = f"远程审核请求失败: {e}"
            return audit_info

        if not isinstance(resp_dict, dict) or "caption" not in resp_dict:
            audit_info["message"] = "远程审核返回异常格式"
            return audit_info

        tags = resp_dict["caption"]
        replace_list = ["general", "sensitive", "questionable", "explicit"]
        to_user_list = ["这张图很安全!", "较为安全", "色情", "泰色辣!"]
        possibilities = {}
        to_user_dict = {}
        message = "审核结果:\n"

        for key, user_label in zip(replace_list, to_user_list):
            score = tags.get(key, 0.0)
            possibilities[key] = score
            percent = f":{score * 100:.2f}".rjust(6)
            message += f"[{user_label}{percent}%]\n"
            to_user_dict[user_label] = score

        max_user_label, max_score = max(to_user_dict.items(), key=lambda item: item[1])
        reverse_dict = {v: k for k, v in possibilities.items()}
        sorted_scores = sorted(possibilities.values(), reverse=True)
        top_category = reverse_dict.get(sorted_scores[0], "general")

        # 确定群或全局等级
        audit_level = config.comfyui_audit_level
        group_cfg = config.comfyui_group_config.get("audit_level_group", {})
        if group_id and group_id in group_cfg:
            try:
                audit_level = int(group_cfg[group_id])
            except ValueError:
                pass

        is_nsfw = False
        if audit_level == 1:
            is_nsfw = (top_category == "explicit")
        elif audit_level == 2:
            is_nsfw = top_category in ("questionable", "explicit")
        elif audit_level == 3:
            is_nsfw = top_category in ("questionable", "explicit", "sensitive")
        elif audit_level >= 100:
            is_nsfw = True
        elif audit_level == 0:
            is_nsfw = False

        audit_info["tags"] = possibilities
        audit_info["message"] = f"{message}最终判定: {max_user_label}"
        audit_info["is_nsfw"] = is_nsfw
        return audit_info


remote_tagger_auditor = RemoteTaggerAuditor()
