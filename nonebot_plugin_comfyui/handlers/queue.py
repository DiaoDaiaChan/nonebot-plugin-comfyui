from argparse import Namespace
from typing import Any
from nonebot import Bot, logger
from nonebot.adapters import Event
from nonebot_plugin_alconna import UniMessage

from nonebot.params import ShellCommandArgs

from ..config import config, BACKEND_URL_LIST
from ..services.comfy_client import comfy_client
from ..services.workflow_engine import workflow_engine
from ..services.audit import audit_image
from ..utils.media import get_qr


async def queue_handler(bot: Bot, event: Event, args: Namespace = ShellCommandArgs()) -> None:
    """处理 queue 队列管理指令"""
    backend_val = getattr(args, "backend", "0")
    if backend_val.isdigit():
        idx = int(backend_val)
        backend_url = BACKEND_URL_LIST[idx] if 0 <= idx < len(BACKEND_URL_LIST) else config.comfyui_url
    elif backend_val in BACKEND_URL_LIST:
        backend_url = backend_val
    else:
        backend_url = config.comfyui_url

    msg_out = UniMessage()

    # 1. 停止当前生成
    if getattr(args, "stop", False):
        try:
            await comfy_client.interrupt(backend_url)
            msg_out += "任务已成功请求停止！\n"
        except Exception as e:
            msg_out += f"终止任务失败: {e}\n"

    # 2. 追踪队列
    if getattr(args, "track", False):
        try:
            queue_data = await comfy_client.request("GET", f"{backend_url}/queue")
            running = [t[1] for t in queue_data.get('queue_running', []) if len(t) > 1]
            pending = [t[1] for t in queue_data.get('queue_pending', []) if len(t) > 1]
            total_tasks = running + pending
            msg_out += f"后端当前共 {len(total_tasks)} 个任务:\n"
            if running:
                msg_out += "正在执行:\n" + "\n".join(running) + "\n"
            if pending:
                msg_out += "排队中:\n" + "\n".join(pending) + "\n"
        except Exception as e:
            msg_out += f"获取队列失败: {e}\n"

    # 3. 删除任务
    delete_id = getattr(args, "delete", None)
    if delete_id:
        ids = [i.strip() for i in delete_id.split(",") if i.strip()]
        try:
            await comfy_client.delete_queue(backend_url, ids)
            msg_out += f"已将任务 {ids} 从队列中删除\n"
        except Exception as e:
            msg_out += f"删除任务失败: {e}\n"

    # 4. 清空队列
    if getattr(args, "clear", False):
        try:
            await comfy_client.clear_queue(backend_url)
            msg_out += "队列中的所有任务已全部清空！\n"
        except Exception as e:
            msg_out += f"清空队列失败: {e}\n"

    # 5. 查询指定任务状态
    task_id = getattr(args, "task_id", None)
    if task_id:
        try:
            hist = await comfy_client.get_history(backend_url, task_id)
            if task_id in hist:
                status_str = hist[task_id].get("status", {}).get("status_str", "未知")
                completed = "是" if hist[task_id].get("status", {}).get("completed") else "否"
                msg_out += f"任务 {task_id}:\n状态: {status_str}\n是否完成: {completed}\n"
            else:
                msg_out += f"任务 {task_id}: 生成中或未找到\n"
        except Exception as e:
            msg_out += f"查询任务失败: {e}\n"

    # 6. 获取指定任务结果 (get_task)
    get_t = getattr(args, "get_task", None)
    if get_t:
        try:
            hist = await comfy_client.get_history(backend_url, get_t)
            if get_t in hist:
                outputs = hist[get_t].get("outputs", {})
                msg_out += f"任务 {get_t} 的生成结果:\n"
                for node_id, node_data in outputs.items():
                    for img in node_data.get("images", []):
                        fn = img["filename"]
                        sub = img.get("subfolder", "")
                        t = img.get("type", "")
                        u = f"{backend_url}/view?filename={fn}&subfolder={sub}&type={t}"
                        img_b = await comfy_client.request("GET", u, as_json=False)
                        msg_out += UniMessage.image(raw=img_b)
            else:
                msg_out += f"未找到任务 {get_t} 的历史记录\n"
        except Exception as e:
            msg_out += f"获取任务输出失败: {e}\n"

    # 7. 查看历史任务 ID
    if getattr(args, "view", False):
        try:
            hist_all = await comfy_client.request("GET", f"{backend_url}/history")
            keys = list(hist_all.keys())
            idx_range = getattr(args, "index", "0-10")
            start, end = map(int, idx_range.split("-"))
            selected = keys[start:end]
            msg_out += f"后端共有 {len(keys)} 个历史任务，切片 [{start}-{end}]:\n" + "\n".join(selected) + "\n"
        except Exception as e:
            msg_out += f"查看历史失败: {e}\n"

    await msg_out.send(reply_to=True)


async def api_handler(bot: Bot, event: Event, args: Namespace = ShellCommandArgs()) -> None:
    """处理 capi 节点查询指令"""
    backend_val = getattr(args, "backend", "0")
    if backend_val.isdigit():
        idx = int(backend_val)
        backend_url = BACKEND_URL_LIST[idx] if 0 <= idx < len(BACKEND_URL_LIST) else config.comfyui_url
    else:
        backend_url = backend_val

    node = getattr(args, "get", "all")
    if node == "all":
        try:
            resp = await comfy_client.request("GET", f"{backend_url}/object_info")
            names = list(resp.keys())
            msg = UniMessage.text(f"ComfyUI 后端共加载 {len(names)} 个节点:\n" + "\n".join(names[:100]))
            if len(names) > 100:
                msg += f"\n... (剩余 {len(names) - 100} 个节点省略)"
            await msg.send(reply_to=True)
        except Exception as e:
            await UniMessage.text(f"获取节点列表失败: {e}").send(reply_to=True)
    else:
        try:
            resp = await comfy_client.request("GET", f"{backend_url}/object_info/{node}")
            lines = [f"{k}: {v}" for k, v in resp.get(node, {}).items()]
            await UniMessage.text(f"节点 {node} 详情:\n" + "\n".join(lines[:30])).send(reply_to=True)
        except Exception as e:
            await UniMessage.text(f"获取节点 {node} 失败: {e}").send(reply_to=True)
