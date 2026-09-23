import json
from pathlib import Path
from typing import Any
from nonebot import logger
from nonebot.plugin.on import on_shell_command

from ..config import config, init_workflows_dir
from ..parser import rebuild_parser
from ..handlers.generate import comfyui_generate_handler

REGISTERED_COMMANDS: list[tuple[str, str]] = []


def register_workflow_commands() -> list[tuple[str, str]]:
    """
    扫描所有工作流反射文件，将配置了 command 的工作流动态注册为 NoneBot Matcher。
    纯同步执行，彻底避免 import 期调用 asyncio.run() 崩溃的问题。
    """
    global REGISTERED_COMMANDS
    REGISTERED_COMMANDS.clear()

    init_workflows_dir(config.comfyui_workflows_dir)
    wf_dir = Path(config.comfyui_workflows_dir).resolve()
    if not wf_dir.exists():
        return REGISTERED_COMMANDS

    for file_path in wf_dir.glob("*_reflex.json"):
        wf_name = file_path.name.replace("_reflex.json", "")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reflex_json = json.load(f)
        except Exception as e:
            logger.warning(f"读取工作流反射文件失败 [{file_path}]: {e}")
            continue

        cmd = reflex_json.get("command")
        if not cmd:
            continue

        reg_args = reflex_json.get("reg_args")
        dynamic_parser = rebuild_parser(wf_name, reg_args)

        cmd_list = cmd if isinstance(cmd, list) else [cmd]
        main_cmd = cmd_list[0]
        aliases = set(cmd_list[1:]) if len(cmd_list) > 1 else set()

        # 检查是否已注册过相同命令，避免重名冲突
        if any(c[0] == str(cmd) for c in REGISTERED_COMMANDS):
            logger.debug(f"跳过重复的工作流命令注册: {cmd} ({wf_name})")
            continue

        kwargs: dict[str, Any] = {
            "cmd": main_cmd,
            "parser": dynamic_parser,
            "priority": 5,
            "block": True,
            "handlers": [comfyui_generate_handler]
        }
        if aliases:
            kwargs["aliases"] = aliases

        on_shell_command(**kwargs)
        logger.info(f"动态注册工作流命令成功: {cmd} (对应工作流: {wf_name})")
        REGISTERED_COMMANDS.append((str(cmd), reflex_json.get("note", "")))

    return REGISTERED_COMMANDS
