from argparse import Namespace
import random
from typing import Any
from nonebot import Bot, logger
from nonebot.adapters import Event
from nonebot_plugin_alconna import UniMessage

from nonebot.params import ShellCommandArgs

from ..config import config, BACKEND_URL_LIST
from ..services.comfy_client import comfy_client
from ..services.audit import text_audit
from ..amusement.today_girl import prompt_dict
from ..amusement.search_danbooru import danbooru
from ..amusement.llm_tagger import get_user_session
from ..utils.media import send_msg_and_revoke
from .generate import comfyui_generate_handler, TaskRecordManager


async def today_girl_handler(bot: Bot, event: Event, args: Namespace = ShellCommandArgs()) -> None:
    """二次元的我：随机组合标签并生图"""
    build_msg_en = []
    build_msg_zh = []

    choice_list = ["类型", "发色", "头发", "衣服", "鞋子", "装饰", "胸", "表情", "动作", "天气", "环境", "优秀实践"]
    for i in choice_list:
        sub_dict = prompt_dict.get(i, {})
        if sub_dict:
            zh = random.choice(list(sub_dict.keys()))
            en = sub_dict[zh]
            build_msg_zh.append(zh)
            build_msg_en.append(en)
        else:
            build_msg_zh.append("")
            build_msg_en.append("")

    tags = ", ".join([e for e in build_msg_en if e])
    args.prompt = [f"(solo:1.1), {tags}"]
    args.silent = True

    to_user = f"""二次元的我:
{build_msg_zh[11]},
是{build_msg_zh[0]}, {build_msg_zh[7]},
{build_msg_zh[1]}色{build_msg_zh[2]},
穿着{build_msg_zh[3]}和{build_msg_zh[4]},
有着{build_msg_zh[5]}和{build_msg_zh[6]},
正在{build_msg_zh[8]},
画面{build_msg_zh[9]}, {build_msg_zh[10]}"""

    await send_msg_and_revoke(f"锵锵~~~{to_user}\n正在为你生成二次元图像捏", reply_to=True, delay=10)
    await comfyui_generate_handler(bot, event, args)


async def danbooru_handler(bot: Bot, event: Event, tag: str, limit: int | None = None) -> None:
    """从 Danbooru 搜索标签与图样"""
    lim = limit if isinstance(limit, int) else 3
    try:
        resp_list = await danbooru(tag, lim)
        msg_out = UniMessage()
        for r in resp_list:
            msg_out += r.resp_img
        await msg_out.send(reply_to=True)
    except Exception as e:
        await UniMessage.text(f"查询 Danbooru 失败: {e}").send(reply_to=True)


async def llm_handler(bot: Bot, event: Event, args: Namespace = ShellCommandArgs()) -> None:
    """使用 LLM 扩写与润色提示词并生图"""
    user_prompt = " ".join(args.prompt) if isinstance(args.prompt, list) else str(args.prompt)
    session = get_user_session(event.get_session_id())
    llm_prompt = await session.main(user_prompt)

    # 审核 LLM 扩写结果
    audit_res = await text_audit(llm_prompt)
    if "yes" in audit_res:
        llm_prompt = "1girl, solo, masterpiece"

    args.silent = True
    args.prompt = [llm_prompt]

    await send_msg_and_revoke(f"LLM 扩写结果:\n{llm_prompt}", reply_to=True, delay=15)
    await comfyui_generate_handler(bot, event, args)


async def get_checkpoints_handler(bot: Bot, event: Event, index: int) -> None:
    """查询指定后端的 Checkpoint 列表"""
    if 0 <= index < len(BACKEND_URL_LIST):
        url = BACKEND_URL_LIST[index]
    else:
        url = config.comfyui_url

    try:
        ckpts = await comfy_client.get_checkpoints(url)
        await UniMessage.text(f"后端 [{index}] 模型列表:\n" + "\n".join(ckpts[:40])).send(reply_to=True)
    except Exception as e:
        await UniMessage.text(f"获取模型列表失败: {e}").send(reply_to=True)


async def get_loras_handler(bot: Bot, event: Event, index: int) -> None:
    """查询指定后端的 LoRA 列表"""
    if 0 <= index < len(BACKEND_URL_LIST):
        url = BACKEND_URL_LIST[index]
    else:
        url = config.comfyui_url

    try:
        loras = await comfy_client.get_loras(url)
        await UniMessage.text(f"后端 [{index}] LoRA 列表:\n" + "\n".join(loras[:40])).send(reply_to=True)
    except Exception as e:
        await UniMessage.text(f"获取 LoRA 列表失败: {e}").send(reply_to=True)


async def get_user_tasks_handler(bot: Bot, event: Event, index: str | None = None) -> None:
    """获取用户提交过的任务 ID"""
    idx_range = index or "0-10"
    try:
        start, end = map(int, idx_range.split("-"))
    except ValueError:
        start, end = 0, 10

    user_id = str(event.get_user_id())
    tasks_dict = TaskRecordManager.get_user_tasks(user_id)
    task_items = list(tasks_dict.items())
    task_items.reverse()  # 最近优先

    sliced = task_items[start:end]
    if not sliced:
        await UniMessage.text("暂无历史任务记录").send(reply_to=True)
        return

    msg = f"您的历史任务记录 [{start}-{end}]:\n"
    for tid, info in sliced:
        msg += f"- ID: {tid}\n  工作流: {info['work_flow']}, 后端: [{info['backend_index']}], 状态: {info['status']}\n"

    await UniMessage.text(msg.strip()).send(reply_to=True)
