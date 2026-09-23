import asyncio
import base64
from io import BytesIO
import json
import random
import re
from typing import Any
import filetype
from PIL import Image
import qrcode
from nonebot import logger
from nonebot_plugin_alconna import UniMessage

from ..config import config
from ..exceptions import SendImageToBotException


async def send_msg_and_revoke(message: UniMessage | str, reply_to: bool = False, delay: int | None = None) -> Any:
    """发送消息并在指定时间后尝试撤回"""
    if isinstance(message, str):
        unimsg = UniMessage.text(message)
    else:
        unimsg = message

    try:
        receipt = await unimsg.send(reply_to=reply_to)
        if receipt:
            recall_delay = delay if delay is not None else random.randint(60, 100)
            async def _delayed_recall():
                await asyncio.sleep(recall_delay)
                try:
                    await receipt.recall()
                except Exception as e:
                    logger.debug(f"消息撤回跳过或失败: {e}")
            asyncio.create_task(_delayed_recall())
        return receipt
    except Exception as e:
        logger.warning(f"发送撤回消息失败: {e}")
        return None


async def send_msg_to_private(bot: Any, user_id: str | int, msg: bytes | str, is_image: bool = True) -> None:
    """向用户私聊发送图片或文本（保留 OneBot V11 优先适配逻辑）"""
    try:
        # 优先尝试 OneBot V11 适配器
        adapters = getattr(bot, "adapter", None)
        adapter_name = getattr(adapters, "get_name", lambda: "")() if adapters else ""
        if "OneBot V11" in adapter_name or hasattr(bot, "send_private_msg"):
            from nonebot.adapters.onebot.v11 import MessageSegment
            message = MessageSegment.image(msg) if is_image else msg
            await bot.send_private_msg(user_id=int(user_id), message=message)
        else:
            if is_image and isinstance(msg, bytes):
                await UniMessage.image(raw=msg).send(target=str(user_id))
            else:
                await UniMessage.text(str(msg)).send(target=str(user_id))
    except Exception as e:
        logger.warning(f"私聊消息发送失败: {e}")
        try:
            await UniMessage.text('私聊发送失败了!是不是没加机器人好友...').send()
        except Exception:
            pass


async def get_qr(msg: bytes, bot: Any) -> tuple[bytes, str]:
    """通过给 Bot 自身发送私聊解析出 CDN 链接并生成二维码（保持原有业务逻辑）"""
    retry_count = 0
    max_retries = 4
    message_data = None

    while retry_count < max_retries:
        try:
            message_data = await bot.send_private_msg(
                user_id=bot.self_id,
                message=await UniMessage.image(raw=msg).export()
            )
            break
        except Exception as e:
            retry_count += 1
            logger.warning(f'私聊图片发送给自身失败 (第 {retry_count} 次重试): {e}')
            await asyncio.sleep(1)

    if not message_data or retry_count >= max_retries:
        raise SendImageToBotException("机器人给自身发送图片获取图片url时失败")

    message_id = message_data["message_id"]
    message_all = await bot.get_msg(message_id=message_id)
    url_regex = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_regex, str(message_all.get("message", "")))
    if not urls:
        raise SendImageToBotException("未能在私聊返回中匹配到图片链接")

    img_url = urls[0].replace("multimedia.nt.qq.com.cn", "gchat.qpic.cn")
    qr = qrcode.make(img_url)

    buf = BytesIO()
    qr.save(buf, format="PNG")
    bytes_img = buf.getvalue()

    return bytes_img, img_url


def extract_first_frame_from_gif(gif_bytes: bytes) -> bytes:
    gif_image = Image.open(BytesIO(gif_bytes))
    gif_image.seek(0)
    first_frame = gif_image.copy()
    buf = BytesIO()
    first_frame.save(buf, format="PNG")
    return buf.getvalue()


async def extract_images_from_event(event: Any, allow_gif: bool = False) -> list[bytes]:
    """从 Event 或回复消息中提取图片二进制数据"""
    from ..services.comfy_client import comfy_client

    img_urls: list[str] = []

    # 1. 检查 At 对象的头像
    event_dict = event.dict() if hasattr(event, "dict") else {}
    if hasattr(event, "get_plaintext"):
        try:
            raw_json = json.loads(event.json()) if hasattr(event, "json") else {}
            orig_msg = raw_json.get('original_message', [])
            if len(orig_msg) > 1 and orig_msg[1].get('type') == 'at':
                at_id = orig_msg[1].get('data', {}).get('qq')
                if at_id:
                    img_urls.append(f"https://q1.qlogo.cn/g?b=qq&nk={at_id}&s=640")
        except Exception:
            pass

    # 2. 从消息的图片段获取
    msg_obj = getattr(event, "message", [])
    for seg in msg_obj:
        if getattr(seg, "type", "") == "image":
            u = seg.data.get("url")
            if u:
                img_urls.append(u)

    # 3. 从引用回复获取
    reply = getattr(event, "reply", None)
    if reply:
        for seg in getattr(reply, "message", []):
            if getattr(seg, "type", "") == "image":
                u = seg.data.get("url")
                if u:
                    img_urls.append(u)

    image_bytes_list: list[bytes] = []
    for u in img_urls:
        clean_url = u.replace("gchat.qpic.cn", "multimedia.nt.qq.com.cn")
        try:
            byte_img = await comfy_client.request("GET", clean_url, as_json=False)
            kind = filetype.guess(byte_img)
            ext = kind.extension if kind else ""
            if not allow_gif and ext == "gif":
                byte_img = extract_first_frame_from_gif(byte_img)
            image_bytes_list.append(byte_img)
        except Exception as e:
            logger.warning(f"下载输入图片失败 [{clean_url}]: {e}")

    return image_bytes_list
