from nonebot.plugin.on import on_shell_command
from ..config import config
from ..parser import comfyui_parser, queue_parser, api_parser
from ..handlers.generate import comfyui_generate_handler
from ..handlers.queue import queue_handler, api_handler

comfyui_cmd = on_shell_command(
    "prompt",
    parser=comfyui_parser,
    priority=5,
    block=True,
    handlers=[comfyui_generate_handler],
    aliases=set(config.comfyui_trigger_word)
)

queue_cmd = on_shell_command(
    "queue",
    parser=queue_parser,
    priority=5,
    block=True,
    handlers=[queue_handler]
)

api_cmd = on_shell_command(
    "capi",
    parser=api_parser,
    priority=5,
    block=True,
    handlers=[api_handler]
)
