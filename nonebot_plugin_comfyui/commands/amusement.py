from nonebot.plugin.on import on_shell_command
from nonebot_plugin_alconna import on_alconna, Args, Alconna

from ..parser import comfyui_parser
from ..handlers.amusement import (
    today_girl_handler,
    danbooru_handler,
    llm_handler,
    get_checkpoints_handler,
    get_loras_handler,
    get_user_tasks_handler
)

today_girl_cmd = on_shell_command(
    "二次元的",
    parser=comfyui_parser,
    priority=5,
    block=True,
    handlers=[today_girl_handler]
)

dan_cmd = on_alconna(
    Alconna("dan", Args["tag", str]["limit?", int]),
    handlers=[danbooru_handler],
    priority=5,
    block=True,
    use_cmd_start=True,
    aliases={"查tag"}
)

llm_cmd = on_shell_command(
    "llm-tag",
    priority=1,
    block=True,
    handlers=[llm_handler],
    parser=comfyui_parser,
)

get_ckpt_cmd = on_alconna(
    Alconna("get-ckpt", Args["index", int]),
    priority=5,
    block=True,
    handlers=[get_checkpoints_handler],
    use_cmd_start=True
)

get_loras_cmd = on_alconna(
    Alconna("get-loras", Args["index", int]),
    priority=5,
    block=True,
    handlers=[get_loras_handler],
    use_cmd_start=True,
    aliases={"get-lora"}
)

get_task_cmd = on_alconna(
    Alconna("get-task", Args["index?", str]),
    priority=5,
    block=True,
    handlers=[get_user_tasks_handler],
    use_cmd_start=True
)
