from typing import Any
from nonebot import logger
from comfyui_reflex.lora import (
    LORA_NODE_TEMPLATE,
    extract_loras_from_prompt as _extract_loras,
    apply_loras_to_api_json as _apply_loras
)
from .comfy_client import comfy_client


class LoraEngine:
    """LoRA 提示词解析与 API JSON 节点注入引擎 (核心图重构委派至 comfyui_reflex)"""

    LORA_NODE_TEMPLATE: dict[str, Any] = LORA_NODE_TEMPLATE

    @staticmethod
    def extract_loras_from_prompt(prompt: str) -> tuple[str, list[tuple[str, float]]]:
        """
        从 prompt 中提取 `<lora:name:weight>` 结构。
        返回 (清洗后的 prompt, [(lora_name, weight)])
        """
        return _extract_loras(prompt)

    @classmethod
    async def match_available_loras(
        cls,
        backend_url: str,
        parsed_loras: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        """与 ComfyUI 后端现存的 LoRA 文件进行模糊匹配"""
        if not parsed_loras:
            return []

        all_backend_loras = await comfy_client.get_loras(backend_url)
        matched: list[tuple[str, float]] = []

        for lora_name, weight in parsed_loras:
            found = False
            for real_lora in all_backend_loras:
                if lora_name in real_lora:
                    logger.info(f"LoRA 匹配成功: '{lora_name}' -> '{real_lora}' (权重: {weight})")
                    matched.append((real_lora, weight))
                    found = True
                    break
            if not found:
                logger.warning(f"未能找到匹配的 LoRA: '{lora_name}'")

        return matched

    @classmethod
    def apply_loras_to_api_json(
        cls,
        api_json: dict[str, Any],
        lora_config: Any,
        loras: list[tuple[str, float]]
    ) -> dict[str, Any]:
        """
        根据 reflex 中的 lora 配置，将 LoRA 节点串联插入到 api_json 图结构中
        """
        return _apply_loras(api_json=api_json, lora_config=lora_config, loras=loras)


lora_engine = LoraEngine()
