"""
向后兼容模块：backend/utils.py
所有底层能力已拆分解耦至 services 与 utils 模块。
保留此文件以确保对旧版本调用者的向后兼容。
"""
import random
from typing import Any
from ..services.comfy_client import comfy_client
from ..services.workflow_engine import workflow_engine
from ..services.audit import audit_image, text_audit, clean_llm_response
from ..utils.media import (
    send_msg_and_revoke,
    get_qr,
    extract_first_frame_from_gif,
    extract_images_from_event as get_image
)
from ..utils.render import render_help_html as build_help_text, get_backend_status_data as get_backend_status


async def run_later(coro, delay: float = 1):
    import asyncio
    await asyncio.sleep(delay)
    if asyncio.iscoroutine(coro):
        await coro


async def http_request(
    method: str,
    target_url: str,
    headers: dict | None = None,
    params: dict | None = None,
    content: Any = None,
    format: bool = True,
    timeout: int = 5000,
    verify: bool = True,
    proxy: bool = False,
    text: bool = False
) -> Any:
    return await comfy_client.request(
        method=method,
        target_url=target_url,
        headers=headers,
        params=params,
        data=content,
        timeout=timeout,
        as_json=format,
        as_text=text,
        proxy=proxy
    )


async def pic_audit_standalone(img_bytes_or_b64: bytes | str, group_id: str | None = None) -> dict[str, Any]:
    import base64
    if isinstance(img_bytes_or_b64, str):
        img_b = base64.b64decode(img_bytes_or_b64)
    else:
        img_b = img_bytes_or_b64
    return await audit_image(img_b, group_id=group_id or "")


async def txt_audit(msg: str, prompt: str | None = None) -> str:
    return await text_audit(msg, custom_prompt=prompt)


def get_and_filter_work_flows(search: str | None = None, index: int | None = None) -> list[str]:
    return workflow_engine.list_workflows(search=search, index=index)


async def get_ava_backends() -> tuple[set[int], dict[str, Any]]:
    return await comfy_client.get_available_backends()


async def get_all_loras(backend_url: str) -> list[str]:
    return await comfy_client.get_loras(backend_url)


def weighted_choice(choices: list[tuple[Any, float]]) -> Any:
    total = sum(w for c, w in choices)
    r = random.uniform(0, total)
    cumulative_weight = 0
    for c, w in choices:
        cumulative_weight += w
        if r < cumulative_weight:
            return c
    return choices[0][0] if choices else None


async def download_img(url: str) -> tuple[str, bytes]:
    import base64
    clean_url = url.replace("gchat.qpic.cn", "multimedia.nt.qq.com.cn")
    b = await comfy_client.request("GET", clean_url, as_json=False)
    b64 = base64.b64encode(b).decode("utf-8")
    return b64, b


async def translate_api(tags: str, to: str = "en") -> str:
    return tags


__all__ = [
    "run_later",
    "clean_llm_response",
    "http_request",
    "pic_audit_standalone",
    "txt_audit",
    "send_msg_and_revoke",
    "get_image",
    "build_help_text",
    "get_and_filter_work_flows",
    "get_backend_status",
    "get_qr",
    "get_ava_backends",
    "get_all_loras",
    "weighted_choice",
    "download_img",
    "translate_api"
]
