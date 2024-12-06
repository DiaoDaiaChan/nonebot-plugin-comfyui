
import json
import traceback
from datetime import datetime

import datetime

from argparse import Namespace

from nonebot import logger, Bot
from nonebot.adapters import Event
from nonebot.params import ShellCommandArgs
from nonebot.plugin import require
require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import UniMessage

from .backend.comfyui import ComfyUI
from .backend.utils import send_msg_and_revoke
from .config import config

cd = {}
daily_calls = {}
MAX_DAILY_CALLS = config.comfyui_day_limit


async def get_message_at(data: str) -> int | None:
    '''
    获取at列表
    :param data: event.json()
    '''
    data = json.loads(data)
    try:
        msg = data['original_message'][1]
        if msg['type'] == 'at':
            return int(msg['data']['qq'])
    except Exception:
        return None


async def get_image(event) -> list[bytes]:
    img_url = []
    reply = event.reply
    at_id = await get_message_at(event.json())
    # 获取图片url
    if at_id and not reply:
        img_url = [f"https://q1.qlogo.cn/g?b=qq&nk={at_id}&s=640"]
    for seg in event.message['image']:
        img_url.append(seg.data["url"])
    if reply:
        for seg in reply.message['image']:
            img_url.append(seg.data["url"])

    image_byte = []
    if img_url:
        for url in img_url:
            url = url.replace("gchat.qpic.cn", "multimedia.nt.qq.com.cn")

            logger.info(f"检测到图片，自动切换到以图生图，正在获取图片")
            image_byte.append(await ComfyUI.http_request("GET", url, format=False))

    return image_byte


async def comfyui_generate(event, bot, args):
    comfyui_instance = ComfyUI(**vars(args), nb_event=event, args=args, bot=bot)

    image_byte = await get_image(event)
    comfyui_instance.init_images = image_byte

    await comfyui_instance.select_backend()

    for i in range(comfyui_instance.batch_count):
        comfyui_instance.seed += 1
        try:
            await comfyui_instance.exec_generate()
        except Exception as e:
            traceback.print_exc()
            await send_msg_and_revoke(f'任务{comfyui_instance.task_id}生成失败, {e}')

    unimsg: UniMessage = comfyui_instance.unimessage
    unimsg = UniMessage.text('队列完成\n') + unimsg
    comfyui_instance.unimessage = unimsg

    await comfyui_instance.send_all_msg()


async def comfyui_handler(bot: Bot, event: Event, args: Namespace = ShellCommandArgs()):

    nowtime = datetime.datetime.now().timestamp()
    today_date = datetime.datetime.now().strftime('%Y-%m-%d')  # 获取当前日期
    user_id = event.get_user_id()

    deltatime = nowtime - cd.get(user_id, 0)

    if deltatime < config.comfyui_cd:
        await send_msg_and_revoke(f"你冲的太快啦，请休息一下吧，剩余CD为{config.comfyui_cd - int(deltatime)}s")
        return

    daily_key = f"{user_id}:{today_date}"

    if daily_key in daily_calls:
        daily_calls[daily_key] += int(args.batch_count*args.batch_size)
    else:
        daily_calls[daily_key] = 1

    if daily_key in daily_calls and daily_calls[daily_key] >= MAX_DAILY_CALLS:
        await send_msg_and_revoke(f"今天你的调用次数已达上限，最多可以调用 {MAX_DAILY_CALLS} 次。")
        return
    else:
        await send_msg_and_revoke(f"你今天已经调用了{daily_calls[daily_key]}次, 还能调用{MAX_DAILY_CALLS-daily_calls[daily_key]}次")

    cd[user_id] = nowtime

    await comfyui_generate(event, bot, args)





