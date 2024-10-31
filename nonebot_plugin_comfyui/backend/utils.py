import base64
import json

import aiohttp

from nonebot import logger
from ..config import config

from io import BytesIO
from PIL import Image
from asyncio import get_running_loop

async def run_later(func, delay=1):
    loop = get_running_loop()
    loop.call_later(
        delay,
        lambda: loop.create_task(
            func
        )
    )


async def set_res(new_img: Image) -> str:
    max_res = 640
    old_res = new_img.width * new_img.height
    width = new_img.width
    height = new_img.height

    if old_res > pow(max_res, 2):
        if width <= height:
            ratio = height / width
            width: float = max_res / pow(ratio, 0.5)
            height: float = width * ratio
        else:
            ratio = width / height
            height: float = max_res / pow(ratio, 0.5)
            width: float = height * ratio
        logger.info(f"图片尺寸已调整至{round(width)}x{round(height)}")
        new_img.resize((round(width), round(height)))
    img_bytes = BytesIO()
    new_img.save(img_bytes, format="JPEG")
    img_bytes = img_bytes.getvalue()
    img_base64 = base64.b64encode(img_bytes).decode("utf-8")
    return img_base64


async def pic_audit_standalone(
        img_base64,
        is_return_tags=False,
        audit=False,
        return_bool=False
):

    byte_img = (
        img_base64 if isinstance(img_base64, bytes)
        else base64.b64decode(img_base64)
    )
    img = Image.open(BytesIO(byte_img)).convert("RGB")
    img_base64 = await set_res(img)

    async def get_caption(payload):

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    url=f"{config.comfyui_audit_site}/tagger/v1/interrogate",
                    json=payload
            ) as resp:

                if resp.status not in [200, 201]:
                    resp_text = await resp.text()
                    logger.error(f"API失败，错误信息:{resp.status, resp_text}")
                    return None
                resp_dict = await resp.json()
                return resp_dict

    payload = {"image": img_base64, "model": "wd14-vit-v2-git", "threshold": 0.35}
    resp_dict = await get_caption(payload)

    tags = resp_dict["caption"]
    replace_list = ["general", "sensitive", "questionable", "explicit"]
    to_user_list = ["这张图很安全!", "较为安全", "色情", "泰色辣!"]
    possibilities = {}
    to_user_dict = {}
    message = "这是审核结果:\n"

    for i, to_user in zip(replace_list, to_user_list):
        possibilities[i] = tags[i]
        percent = f":{tags[i] * 100:.2f}".rjust(6)
        message += f"[{to_user}{percent}%]\n"
        to_user_dict[to_user] = tags[i]

    value = list(to_user_dict.values())
    value.sort(reverse=True)
    reverse_dict = {value: key for key, value in to_user_dict.items()}
    message += (f"最终结果为:{reverse_dict[value[0]].rjust(5)}")

    if return_bool:
        value = list(possibilities.values())
        value.sort(reverse=True)
        reverse_dict = {value: key for key, value in possibilities.items()}
        logger.info(message)
        return True if reverse_dict[value[0]] == "questionable" or reverse_dict[value[0]] == "explicit" else False

    if is_return_tags:
        return message, tags
    if audit:
        return possibilities, message
    return message