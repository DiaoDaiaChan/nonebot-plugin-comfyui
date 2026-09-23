import os
from pathlib import Path
from typing import Any
import aiofiles
from jinja2 import Environment, FileSystemLoader
from nonebot import logger

from ..config import config, PLUGIN_DIR
from ..constants import PLUGIN_VERSION
from ..parser import comfyui_parser
from ..services.comfy_client import comfy_client
from ..services.workflow_engine import workflow_engine

TEMPLATE_DIR: Path = PLUGIN_DIR / "template"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)


async def get_backend_status_data() -> list[dict[str, Any]]:
    """获取所有后端的系统状态与队列详情"""
    results: list[dict[str, Any]] = []

    def obfuscate_url(url: str) -> str:
        if len(url) <= 16:
            return url
        return url[:8] + '*' * (len(url) - 16) + url[-8:]

    for idx, url in enumerate(config.comfyui_url_list):
        node_status: dict[str, Any] = {
            "url": obfuscate_url(url),
            "system": {},
            "queue": {},
            "error": None,
            "index": idx
        }

        try:
            status_resp = await comfy_client.request("GET", f"{url}/system_stats", timeout=config.comfyui_timeout)
            system_data = status_resp.get("system", {})
            node_status["system"].update({
                "comfyui_version": system_data.get("comfyui_version"),
                "python_version": system_data.get("python_version"),
                "pytorch_version": system_data.get("pytorch_version"),
                "startup_args": system_data.get("argv", [])
            })
            devices = status_resp.get("devices", [])
            if devices:
                dev = devices[0]
                node_status["system"].update({
                    "device_name": dev.get("name"),
                    "vram_free": dev.get("vram_free"),
                    "vram_total": dev.get("vram_total")
                })
        except Exception as e:
            node_status["error"] = f"获取系统信息失败: {e}"

        try:
            queue_resp = await comfy_client.request("GET", f"{url}/queue", timeout=config.comfyui_timeout)
            running = queue_resp.get("queue_running", [])
            pending = queue_resp.get("queue_pending", [])
            node_status["queue"].update({
                "running_count": len(running),
                "pending_count": len(pending),
                "running_ids": [t[1] for t in running if len(t) > 1],
                "pending_ids": [t[1] for t in pending if len(t) > 1]
            })
        except Exception as e:
            if not node_status["error"]:
                node_status["error"] = f"获取队列信息失败: {e}"

        results.append(node_status)
    return results


async def render_backend_status_html() -> str:
    data = await get_backend_status_data()
    template = jinja_env.get_template("backend_status.html")
    return template.render(data=data)


async def render_help_html(reg_commands: list[tuple[str, str]] | None = None) -> str:
    reg_commands = reg_commands or []
    argument_list = []

    for action in comfyui_parser._actions:
        if action.dest != 'help':
            options = action.option_strings
            flag = options[0] if options else action.dest
            help_text = action.help or ""
            desc = help_text.split("example:")[0].strip() if "example:" in help_text else help_text
            example = help_text.split("example:")[1].strip() if "example:" in help_text else ""
            argument_list.append({
                "flag": flag,
                "description": desc,
                "example": example
            })

    template_data = {
        "reg_commands": reg_commands,
        "parameters": argument_list,
        "shape_presets": [
            {"name": k, "width": v[0], "height": v[1]}
            for k, v in config.comfyui_shape_preset.items()
        ],
        "queue_params": [
            {"flag": "-be", "description": "查看队列的后端索引或者URL(默认0)", "example": "queue -get <id> -be 0"},
            {"flag": "-t", "description": "追踪后端当前所有的任务id", "example": "queue -t -be 0"},
            {"flag": "-d", "description": "需要删除的任务id", "example": "queue -d <id> -be 0"},
            {"flag": "-c", "description": "清除后端上的所有任务", "example": "queue -c -be 0"},
            {"flag": "-i", "description": "查询指定任务状态", "example": "queue -i <id> -be 0"},
            {"flag": "-v", "description": "查看历史任务，配合 -index 使用", "example": "queue -v -index 0-20 -be 0"},
            {"flag": "-get", "description": "获取指定任务的输出图片/文件", "example": "queue -get <id> -be 0"},
            {"flag": "-stop", "description": "终止当前正在执行的任务", "example": "queue -stop"}
        ],
        "capi_params": [
            {"flag": "-be", "description": "后端索引或URL(默认0)", "example": "capi -be 0 -get all"},
            {"flag": "-get", "description": "节点名称或all(获取所有节点)", "example": "capi -get KSampler -be 0"}
        ],
        "other_commands": [
            {"command": "查看工作流", "description": "查看所有可用工作流", "example": "查看工作流 / 查看工作流 flux"},
            {"command": "comfyui后端", "description": "查看所有 ComfyUI 后端状态", "example": "comfyui后端"},
            {"command": "二次元的我", "description": "随机生成二次元形象", "example": "二次元的我"},
            {"command": "dan", "description": "从 Danbooru 查询 tag", "example": "dan 原神 5"},
            {"command": "llm-tag", "description": "使用 LLM 扩写并优化提示词", "example": "llm-tag 海边的少女"},
            {"command": "get-ckpt", "description": "获取后端的 Checkpoint 模型列表", "example": "get-ckpt 0"},
            {"command": "get-loras", "description": "获取后端的 LoRA 模型列表", "example": "get-loras 0"},
            {"command": "get-task", "description": "获取自己提交过的任务历史", "example": "get-task 0-10"}
        ],
        "version": PLUGIN_VERSION
    }

    template = jinja_env.get_template("help.html")
    return template.render(**template_data)


async def render_workflows_html(search: str | None = None) -> tuple[str, bytes | None]:
    """渲染工作流列表及可选 Playwright 预览截图"""
    wf_names = workflow_engine.list_workflows()
    filtered_names = []
    if search:
        if search.isdigit():
            idx = int(search)
            if 1 <= idx <= len(wf_names):
                filtered_names = [wf_names[idx - 1]]
        else:
            filtered_names = [n for n in wf_names if search in n]
    else:
        filtered_names = wf_names

    tbody_rows = []
    row_tmpl = jinja_env.get_template("row_template.html")

    for idx, name in enumerate(filtered_names, 1):
        try:
            _, reflex_json = await workflow_engine.load_workflow_files(name)
        except Exception:
            continue

        load_image = reflex_json.get('load_image')
        image_count = len(load_image) if isinstance(load_image, dict) else 1
        note = reflex_json.get('note', '').strip()
        override = reflex_json.get('override', {})
        override_msg = '<br>'.join([f'{k}: {v}' for k, v in override.items()])
        day_limit = reflex_json.get('daylimit', "无限")
        reg_command = reflex_json.get('command', '')

        # 参数表格
        reg_args = reflex_json.get('reg_args')
        reg_args_table = "无"
        if reg_args:
            reg_args_table = "<table class='sub-table'><thead><tr><th>参数名</th><th>类型</th><th>默认值</th><th>描述</th></tr></thead><tbody>"
            for k, val in reg_args.items():
                for arg in val.get('args', []):
                    reg_args_table += f"<tr><td>{arg.get('name_or_flags', [''])[0]}</td><td>{arg.get('type')}</td><td>{arg.get('default')}</td><td>{arg.get('help')}</td></tr>"
            reg_args_table += "</tbody></table>"

        # 可用后端
        available_str = reflex_json.get('available', [])
        available = ', '.join(str(b) for b in available_str) + '号后端可用' if available_str else "全部可用"

        row = row_tmpl.render(
            index=idx,
            day_limit=day_limit,
            name=name,
            is_loaded_image=bool(load_image),
            image_count=image_count,
            override_msg=override_msg,
            reg_command=reg_command,
            reg_args_table=reg_args_table,
            reg_preset_table="无",
            note=note,
            available=available
        )
        tbody_rows.append(row)

    show_tmpl = jinja_env.get_template("show_wf_template.html")
    full_html = show_tmpl.render(tbody_content='\n'.join(tbody_rows))

    screenshot_bytes = None
    if len(filtered_names) == 1:
        # 可选的 Playwright 预览
        try:
            from ..backend.pw import get_workflow_sc
            screenshot_bytes = await get_workflow_sc(filtered_names[0])
        except Exception as e:
            logger.debug(f"跳过 Playwright 截图预览: {e}")

    return full_html, screenshot_bytes
