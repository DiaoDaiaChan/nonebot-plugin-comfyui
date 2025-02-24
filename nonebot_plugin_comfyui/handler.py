import json
import random
import datetime

from argparse import Namespace
from itertools import islice

from nonebot import logger, get_bot
from nonebot import Bot
from nonebot.adapters import Event
from nonebot.params import ShellCommandArgs, Matcher

from nonebot_plugin_alconna import UniMessage
from .backend.utils import send_msg_and_revoke, comfyui_generate, get_file_url
from .config import config
from .backend import ComfyuiTaskQueue, ComfyUI
from .backend.update_check import check_package_update

cd = {}
daily_calls = {}
TEMP_MSG = False

TIPS = [
    "发送 comfyui帮助  来获取详细的操作",
    "queue -stop 可以停止当前生成",
    "插件默认不支持中文提示词",
    "插件帮助菜单中的注册的命令为可以调用的额外命令",
    "查看工作流  ,可以查看所有的工作流;查看工作流 flux ,可以筛选带有flux的工作流",
    "使用-con / -并发 参数进行多后端并发生图"
    "使用 -r 1216x832 参数, 可用快速设定分辨率"
]
MAX_DAILY_CALLS = config.comfyui_day_limit


async def limit(daily_key, counter):
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
    global TEMP_MSG

    try:
        if TEMP_MSG == False:
            update_msg, is_new_ver = await check_package_update()

            if is_new_ver:
                bot = get_bot()
                for superuser in config.comfyui_superusers:
                    await bot.send_private_msg(user_id=superuser, message=update_msg)

            await bot.send(event, update_msg)

    except:
        logger.warning("版本更新信息获取失败")
    finally:
        TEMP_MSG = True
    # CD部分
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
    await send_msg_and_revoke(f"{msg}, TIPS: {random.choice(TIPS)}", True)

    if config.comfyui_limit_as_seconds:
        daily_calls[daily_key] -= int(total_image)

    if reach_limit:
        return

    cd[user_id] = nowtime
    # 执行生成
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

        comfyui_instance.unimessage += f"共有{len(task_id)}个任务\n后端共有以下任务正在执行\n" + '\n'.join(task_id)

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

        comfyui_instance = await get_file_url(comfyui_instance, outputs, backend_url, args.get_task)

        await comfyui_instance.download_img()

        comfyui_instance.unimessage += f"这是你要找的任务:\n"

    if args.view:

        def get_keys_from_ranges(all_task_dict, ranges_str):
            selected_keys = []
            start, end = map(int, ranges_str.split('-'))
            selected_keys.extend(list(islice(all_task_dict.keys(), start, end)))

            return selected_keys

        keys = get_keys_from_ranges(queue_instance.all_task_dict, args.index)
        keys.sort(reverse=True)

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

