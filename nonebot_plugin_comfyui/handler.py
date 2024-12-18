import json
import traceback
import os

import datetime
from argparse import Namespace
from itertools import islice

from nonebot import logger
from nonebot.plugin import require
from nonebot import Bot
from nonebot.adapters import Event
from nonebot.params import ShellCommandArgs, Matcher

require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import UniMessage

from .backend.utils import send_msg_and_revoke
from .config import config
from .backend import ComfyUI, ComfyuiTaskQueue

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

    try:
        await comfyui_instance.exec_generate()
    except Exception as e:
        traceback.print_exc()
        await send_msg_and_revoke(f'任务{comfyui_instance.task_id}生成失败, {e}')
        raise e

    unimsg: UniMessage = comfyui_instance.unimessage
    unimsg = UniMessage.text(f'队列完成, 耗时:{comfyui_instance.spend_time}秒\n') + unimsg
    comfyui_instance.unimessage = unimsg

    await comfyui_instance.send_all_msg()

    return comfyui_instance


async def limit(daily_key, counter) -> (str, bool):
    if config.comfyui_limit_as_seconds:
        if daily_key in daily_calls:
            daily_calls[daily_key] += int(counter)
        else:
            daily_calls[daily_key] = 1

        if daily_key in daily_calls and daily_calls[daily_key] >= MAX_DAILY_CALLS:
            return f"今天你的使用时间已达上限，最多可以调用 {MAX_DAILY_CALLS} 秒。", True
        else:
            return f"你今天已经使用了{daily_calls[daily_key]}秒, 还能使用{MAX_DAILY_CALLS - daily_calls[daily_key]}秒", False
    else:

        if daily_key in daily_calls:
            daily_calls[daily_key] += int(counter)
        else:
            daily_calls[daily_key] = 1

        if daily_key in daily_calls and daily_calls[daily_key] >= MAX_DAILY_CALLS:
            return f"今天你的调用次数已达上限，最多可以调用 {MAX_DAILY_CALLS} 次。", True
        else:
            return f"你今天已经调用了{daily_calls[daily_key]}次, 还能调用{MAX_DAILY_CALLS - daily_calls[daily_key]}次", False


async def comfyui_handler(bot: Bot, event: Event, args: Namespace = ShellCommandArgs()):
    nowtime = datetime.datetime.now().timestamp()
    today_date = datetime.datetime.now().strftime('%Y-%m-%d')  # 获取当前日期
    user_id = event.get_user_id()

    deltatime = nowtime - cd.get(user_id, 0)

    if deltatime < config.comfyui_cd:
        await send_msg_and_revoke(f"你冲的太快啦，请休息一下吧，剩余CD为{config.comfyui_cd - int(deltatime)}s")
        return

    daily_key = f"{user_id}:{today_date}"

    total_image = args.batch_count * args.batch_size
    msg, reach_limit = await limit(daily_key, total_image)
    await send_msg_and_revoke(msg, True)

    if config.comfyui_limit_as_seconds:
        daily_calls[daily_key] -= int(total_image)

    if reach_limit:
        return

    cd[user_id] = nowtime
    try:
        comfyui_instance = await comfyui_generate(event, bot, args)

        if config.comfyui_limit_as_seconds:
            spend_time = comfyui_instance.spend_time
            await limit(daily_key, spend_time)

    except:
        daily_calls[daily_key] -= int(total_image)


async def queue_handler(bot: Bot, event: Event, matcher: Matcher, args: Namespace = ShellCommandArgs()):
    queue_instance = ComfyuiTaskQueue(bot, event, **vars(args))
    comfyui_instance = ComfyUI(**vars(args), nb_event=event, args=args, bot=bot)

    backend_url = queue_instance.backend_url

    await queue_instance.get_history_task(queue_instance.backend_url)
    task_status_dict = await queue_instance.get_task(args.task_id)

    if args.stop:
        resp = await comfyui_instance.http_request("POST", f"{backend_url}/interrupt", text=True)
        comfyui_instance.unimessage += "任务已经停止"

    if args.track:
        resp = await comfyui_instance.http_request("GET", f"{backend_url}/queue")
        task_id = []

        for task in resp['queue_running']:
            task_id.append(task[1])

        for task in resp['queue_pending']:
            task_id.append(task[1])

        comfyui_instance.unimessage += "后端共有以下任务正在执行\n" + '\n'.join(task_id)

    delete = args.delete
    if delete:
        if "," in delete:
            delete = delete.split(",")

        else:
            delete = [delete]

        payload = {"delete": delete}

        resp = await comfyui_instance.http_request(
            "POST",
            f"{backend_url}/queue",
            content=json.dumps(payload),
            text=True
        )

        comfyui_instance.unimessage += "任务已经从队列中删除"

    if args.clear:

        payload = {"clear": True}

        resp = await comfyui_instance.http_request(
            "POST",
            f"{backend_url}/queue",
            content=json.dumps(payload),
            text=True
        )

        comfyui_instance.unimessage += "任务已经全部清空"

    if args.task_id:

        if task_status_dict:

            task_status = task_status_dict['status']['status_str']
            is_task_completed = '是' if task_status_dict['status']['completed'] else '否'

        else:
            task_status = '生成中'
            is_task_completed = '否'

        comfyui_instance.unimessage += f"任务{args.task_id}: \n状态：{task_status}\n是否完成: {is_task_completed}"

    if args.get_task:
        task_status_dict = await queue_instance.get_task(args.get_task)

        try:
            outputs = task_status_dict['outputs']
        except KeyError:
            await matcher.finish(f"任务{args.get_task}不存在")

        comfyui_instance = await get_file_url(comfyui_instance, outputs, backend_url)

        await comfyui_instance.download_img()

        comfyui_instance.unimessage = f"这是你要找的任务:\n" + comfyui_instance.unimessage

    if args.view:
        def get_keys_from_ranges(all_task_dict, ranges_str):
            selected_keys = []
            start, end = map(int, ranges_str.split('-'))
            selected_keys.extend(list(islice(all_task_dict.keys(), start, end)))

            return selected_keys

        keys = get_keys_from_ranges(queue_instance.all_task_dict, args.index)

        id_list_str = '\n'.join(list(keys))
        comfyui_instance.unimessage = f"此ComfyUI后端上共有: {len(queue_instance.all_task_dict.keys())}个任务,\n这是指定的任务的id:\n {id_list_str}" + comfyui_instance.unimessage

    await comfyui_instance.send_all_msg()


async def api_handler(bot: Bot, event: Event, args: Namespace = ShellCommandArgs()):
    comfyui_instance = ComfyUI(**vars(args), nb_event=event, args=args, bot=bot, forward=True)

    backend_url = comfyui_instance.backend_url
    node = args.get
    if node:
        if node == "all":
            resp = await comfyui_instance.http_request("GET", f"{backend_url}/object_info")

            node_name = list(resp.keys())
            chunked_list = []

            for i in range(0, len(node_name), 100):
                chunked_list.append(UniMessage.text("\n".join(node_name[i:i + 100])))

            comfyui_instance.unimessage += f"此ComfyUI后端上共有: {len(node_name)}个节点:\n"
            comfyui_instance.uni_long_text = chunked_list

        else:
            resp = await comfyui_instance.http_request("GET", f"{backend_url}/object_info/{node}")
            msg = ""
            for key, value in resp[node].items():
                msg += f"{key}: {value}\n"

            comfyui_instance.unimessage += msg

    await comfyui_instance.send_all_msg()


async def get_file_url(comfyui_instance, outputs, backend_url):
    images_url = comfyui_instance.media_url.get('image', [])
    video_url = comfyui_instance.media_url.get('video', [])

    for imgs in list(outputs.values()):
        if 'images' in imgs:
            for img in imgs['images']:

                filename = img['filename']
                _, file_format = os.path.splitext(filename)

                if img['subfolder'] == "":
                    url = f"{backend_url}/view?filename={filename}"
                else:
                    url = f"{backend_url}/view?filename={filename}&subfolder={img['subfolder']}"

                if img['type'] == "temp":
                    url = f"{backend_url}/view?filename={filename}&subfolder=&type=temp"

                images_url.append({"url": url, "file_format": file_format})

        if 'gifs' in imgs:
            for img in imgs['gifs']:
                filename = img['filename']
                _, file_format = os.path.splitext(filename)

                if img['subfolder'] == "":
                    url = f"{backend_url}/view?filename={filename}"
                else:
                    url = f"{backend_url}/view?filename={filename}&subfolder={img['subfolder']}"

                video_url.append({"url": url, "file_format": file_format})

        if 'text' in imgs:

            for img in imgs['text']:
                comfyui_instance.unimessage += img

    comfyui_instance.media_url['image'] = images_url
    comfyui_instance.media_url['video'] = video_url

    return comfyui_instance
