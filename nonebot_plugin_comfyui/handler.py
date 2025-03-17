import json
import random
import datetime
import traceback

from argparse import Namespace
from itertools import islice

from nonebot import logger, get_bot
from nonebot import Bot
from nonebot.adapters import Event
from nonebot.params import ShellCommandArgs, Matcher

from nonebot_plugin_alconna import UniMessage
from .backend.utils import send_msg_and_revoke, get_file_url, http_request, txt_audit, get_image
from .amusement import *
from .backend import ComfyUI
from .config import config
from .backend import ComfyuiTaskQueue, ComfyUI, ComfyuiHistory
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


async def comfyui_generate(event, bot, args, extra_msg=None, day_limit=None):
    comfyui_instance = ComfyUI(nb_event=event, bot=bot, args=args, **vars(args))

    if extra_msg:
        await comfyui_instance.send_extra_info(extra_msg, reply=True)
    # 加载图片
    image_byte = await get_image(event, args.gif)
    comfyui_instance.init_images = image_byte

    try:
        await comfyui_instance.exec_generate(day_limit)
    except Exception as e:
        traceback.print_exc()
        await send_msg_and_revoke(f'任务{comfyui_instance.task_id}生成失败, {e}')
        raise e

    unimsg: UniMessage = comfyui_instance.unimessage
    unimsg = UniMessage.text(f'队列完成, 耗时:{comfyui_instance.spend_time}秒\n') + unimsg
    comfyui_instance.unimessage = unimsg

    await comfyui_instance.send_all_msg()

    return comfyui_instance


async def limit(daily_key, counter, wf=None):

    if config.comfyui_limit_as_seconds:
        if daily_key in daily_calls:
            daily_calls[daily_key] += int(counter)
        else:
            daily_calls[daily_key] = int(counter)

        if daily_key in daily_calls and daily_calls[daily_key] >= MAX_DAILY_CALLS:
            msg = f"今天你的使用时间已达上限，最多可以调用 {MAX_DAILY_CALLS} 秒。"
            is_reach_limit = True
        else:
            msg = f"你今天已经使用了{daily_calls[daily_key]}秒, 还能使用{MAX_DAILY_CALLS - daily_calls[daily_key]}秒"
            is_reach_limit = False
    else:

        if daily_key in daily_calls:
            daily_calls[daily_key] += int(counter)
        else:
            daily_calls[daily_key] = int(counter)

        if daily_key in daily_calls and daily_calls[daily_key] >= MAX_DAILY_CALLS:
            msg = f"今天你的调用次数已达上限，最多可以调用 {MAX_DAILY_CALLS} 次。"
            is_reach_limit = True
        else:
            msg = f"你今天已经调用了{daily_calls[daily_key]}次, 还能调用{MAX_DAILY_CALLS - daily_calls[daily_key]}次"
            is_reach_limit = False

    if wf:
        if "wf" not in daily_calls:
            daily_calls["wf"] = {}

        if daily_key not in daily_calls["wf"]:
            daily_calls["wf"][daily_key] = {}

        if wf in daily_calls["wf"][daily_key]:
            daily_calls["wf"][daily_key][wf] += int(counter)
        else:
            daily_calls["wf"][daily_key][wf] = int(counter)

    return msg, is_reach_limit


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
    
    if user_id in config.comfyui_superusers:
        msg = f"TIPS: {random.choice(TIPS)}"
        await comfyui_generate(event, bot, args, msg)
        return

    deltatime = nowtime - cd.get(user_id, 0)

    if deltatime < config.comfyui_cd:
        await send_msg_and_revoke(f"你冲的太快啦，请休息一下吧，剩余CD为{config.comfyui_cd - int(deltatime)}s")
        return

    daily_key = f"{user_id}:{today_date}"

    total_image = args.batch_count * args.batch_size
    limit_msg, reach_limit = await limit(daily_key, total_image, args.work_flows)
    msg = f"{limit_msg}, TIPS: {random.choice(TIPS)}"

    if config.comfyui_limit_as_seconds:
        daily_calls[daily_key] -= int(total_image)

    if reach_limit:
        await send_msg_and_revoke(limit_msg)
        return

    cd[user_id] = nowtime
    # 执行生成
    try:
        comfyui_instance = await comfyui_generate(
            event, bot, args, msg,
            daily_calls["wf"][daily_key][args.work_flows]
        )

        if config.comfyui_limit_as_seconds:
            spend_time = comfyui_instance.spend_time
            await limit(daily_key, spend_time)

    except:
        traceback.print_exc()
        daily_calls[daily_key] -= int(total_image)


async def queue_handler(bot: Bot, event: Event, matcher: Matcher, args: Namespace = ShellCommandArgs()):
    queue_instance = ComfyuiHistory(bot, event, **vars(args))
    comfyui_instance = ComfyUI(nb_event=event, bot=bot, args=args, **vars(args))

    backend_url = queue_instance.backend_url

    await queue_instance.get_history_task(queue_instance.backend_url)
    task_status_dict = await queue_instance.get_task(args.task_id)

    if args.stop:
        resp = await http_request("POST", f"{backend_url}/interrupt", text=True)
        comfyui_instance.unimessage += "任务已经停止"

    if args.track:
        resp = await http_request("GET", f"{backend_url}/queue")
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

        resp = await http_request(
            "POST",
            f"{backend_url}/queue",
            content=json.dumps(payload),
            text=True
        )

        comfyui_instance.unimessage += "任务已经从队列中删除"

    if args.clear:

        payload = {"clear": True}

        resp = await http_request(
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
    comfyui_instance = ComfyUI(nb_event=event, bot=bot, args=args, forward=True, **vars(args))

    backend_url = comfyui_instance.backend_url
    node = args.get
    if node:
        if node == "all":
            resp = await http_request("GET", f"{backend_url}/object_info")

            node_name = list(resp.keys())
            chunked_list = []

            for i in range(0, len(node_name), 100):
                chunked_list.append(UniMessage.text("\n".join(node_name[i:i + 100])))

            comfyui_instance.unimessage += f"此ComfyUI后端上共有: {len(node_name)}个节点:\n"
            comfyui_instance.uni_long_text = chunked_list

        else:
            resp = await http_request("GET", f"{backend_url}/object_info/{node}")
            msg = ""
            for key, value in resp[node].items():
                msg += f"{key}: {value}\n"

            comfyui_instance.unimessage += msg

    await comfyui_instance.send_all_msg()


async def today_girl_handler(
    bot: Bot,
    event: Event,
    args: Namespace = ShellCommandArgs()
):
    build_msg_en = []
    build_msg_zh = []

    choice_list = ["类型", "发色", "头发", "衣服", "鞋子", "装饰", "胸",  "表情", "动作", "天气", "环境", "优秀实践"]
    for i in choice_list:
        zh = random.choice(list(prompt_dict[i].keys()))
        en = prompt_dict[i][zh]
        build_msg_zh.append(zh)
        build_msg_en.append(en)
        tags = build_msg_en[0] +","+ f','.join(build_msg_en)
        args.prompt = [tags]

    to_user = f'''
二次元的我,
{build_msg_zh[11]},
是{build_msg_zh[0]},{build_msg_zh[7]},
{build_msg_zh[1]}色{build_msg_zh[2]},
穿着{build_msg_zh[3]}和{build_msg_zh[4]},
有着{build_msg_zh[5]}和{build_msg_zh[6]},
正在{build_msg_zh[8]},
画面{build_msg_zh[9]},{build_msg_zh[10]},
'''.strip()

    await send_msg_and_revoke(f"锵锵~~~{to_user}\n正在为你生成二次元图像捏")
    args.prompt = ["(solo:1.1),"] + args.prompt
    args.silent = True
    
    await comfyui_handler(bot, event, args)


async def danbooru_handler(bot: Bot, event: Event, tag: str, limit):

    comfyui_instance = ComfyUI(nb_event=event, bot=bot, forward=True)
    comfyui_instance.resp_msg_list = await danbooru(tag, limit)

    await comfyui_instance.send_all_msg()


async def get_checkpoints(
    bot: Bot,
    event: Event,
    index: int
):
    comfyui_instance = ComfyUI(nb_event=event, bot=bot)
    resp = await http_request(
        "GET", f"{config.comfyui_url_list[index]}/object_info/CheckpointLoaderSimple"
    )

    ckpt_list = resp['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
    ckpt_msg = "\n".join(ckpt_list)
    comfyui_instance.unimessage += ckpt_msg

    await comfyui_instance.send_all_msg()


async def llm_handler(bot: Bot, event: Event, args: Namespace = ShellCommandArgs()):
    prompt = await get_user_session(event.get_session_id()).main(','.join(args.prompt))
    resp = await txt_audit(prompt)
    if "yes" in resp:
        prompt = "1girl"

    args.silent = True
    args.prompt = [prompt]

    await send_msg_and_revoke(f'这是llm为你生成的prompt: \n {prompt}')

    await comfyui_handler(bot, event, args)


async def get_task(event: Event, index):
    if isinstance(index, str):
        pass
    else:
        index = "0-10"

    start, end = map(int, index.split('-'))

    my_task = await ComfyuiTaskQueue.get_user_task(event.get_user_id())
    my_task = list(my_task.items())

    tasks_in_range = my_task[start:end + 1]
    msg = '这是你的任务: \n'

    for task_id, task_info in tasks_in_range:
        msg += (
            f"任务ID: {task_id}\n"
            f"后端索引: {task_info['backend_index']}\n"
            f"工作流: {task_info['work_flow']}\n"
            f"状态: {task_info['status']}\n\n"
        )

    await UniMessage.text(msg).send()

