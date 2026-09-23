import json
import re
import string
from typing import Any
from nonebot import logger
from ...config import config
from ..comfy_client import comfy_client


def clean_llm_response(text: str) -> str:
    pattern = r'<?think>.*?</think>'
    cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL)
    return cleaned_text.strip()


def remove_punctuation(text: str) -> str:
    for i in range(len(text)):
        if text[i] not in string.punctuation:
            return text[i:]
    return ""


async def text_audit(msg: str, custom_prompt: str | None = None) -> str:
    """文字提示词安全审核"""
    if not config.comfyui_text_audit:
        return "no"

    ban_words_str = ",".join(config.comfyui_ban_words)
    default_prompt = f"""接下来请你对一些聊天内容进行审核,
如果内容出现中国相关的任何内容/政治/暴力/恐怖袭击/血腥以及{ban_words_str}相关内容（特别是中国的政治人物/或者和中国相关的政治）则请你输出yes, 
如果没有则输出no,最后， 只输出yes或者no即可，不需要你输出其他内容"""

    sys_prompt = custom_prompt or default_prompt
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": msg}
    ]

    openai_cfg = config.comfyui_openai
    payload = {
        "model": openai_cfg.get("params", {}).get("model", "gpt-3.5-turbo"),
        "messages": messages,
        "max_tokens": 4000,
        "temperature": 0.1,
    }
    headers = {"Authorization": f"Bearer {openai_cfg.get('token', '')}"}

    try:
        resp = await comfy_client.request(
            "POST",
            f"{openai_cfg['endpoint']}/chat/completions",
            headers=headers,
            json_data=payload,
            proxy=True,
            timeout=10
        )
        content = resp['choices'][0]['message']['content'].strip()
        cleaned = clean_llm_response(remove_punctuation(content)).lower()
        logger.info(f"文字审核结果: 输入='{msg[:50]}...', 判定='{cleaned}'")
        return cleaned
    except Exception as e:
        logger.error(f"文字审核请求失败: {e}")
        return "yes"
