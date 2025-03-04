import asyncio

from nonebot import logger
from nonebot.plugin.on import on_shell_command, on_command

from nonebot_plugin_htmlrender import html_to_pic, md_to_pic
from nonebot_plugin_alconna import on_alconna, Args, UniMessage, Alconna

from jinja2 import Environment, FileSystemLoader
from .handler import comfyui_handler
from .backend.help import ComfyuiHelp
from .handler import queue_handler, api_handler
from .parser import comfyui_parser, api_parser, queue_parser, rebuild_parser
from .backend.utils import build_help_text, get_backend_status
from .config import PLUGIN_DIR

comfyui = on_shell_command(
    "prompt",
    parser=comfyui_parser,
    priority=5,
    block=True,
    handlers=[comfyui_handler]
)

queue = on_shell_command(
    "queue",
    parser=queue_parser,
    priority=5,
    block=True,
    handlers=[queue_handler]
)

api = on_shell_command(
    "capi",
    parser=api_parser,
    priority=5,
    block=True,
    handlers=[api_handler]
)


help_ = on_command(
    "comfyui帮助", 
    aliases={"帮助", "菜单", "help", "指令"},
    priority=1, 
    block=False
)

view_workflow = on_alconna(
    Alconna("查看工作流", Args["search?", str]),
    priority=5,
    block=True
)

backend = on_command(
    "后端",
    aliases={"comfyui后端"},
    priority=1,
    block=False
)


async def start_up_func():

    async def set_command():
        reg_command = []

        _, content, wf_name = await ComfyuiHelp().get_reflex_json()

        for wf, wf_name in zip(content, wf_name):
            if "command" in wf:
                reg_args = None

                if "reg_args" in wf:
                    reg_args = wf["reg_args"]

                comfyui_parser = await rebuild_parser(wf_name, reg_args)
                on_shell_command(
                    wf["command"],
                    parser=comfyui_parser,
                    priority=5,
                    block=True,
                    handlers=[comfyui_handler]
                )

                logger.info(f"成功注册命令: {wf['command']}")
                reg_command.append((wf["command"], wf.get("note", "")))

        return reg_command

    return await set_command()


@help_.handle()
async def _():
    img = await html_to_pic(html=await build_help_text(reg_command))
    
    ug_str = '⚠️⚠️⚠️基础使用教程⚠️⚠️⚠️'

    source_template = PLUGIN_DIR / "template/example.md"

    with open(source_template, 'r', encoding='utf-8') as f:
        source_template = f.read()
    
    user_guidance = await md_to_pic(md=source_template)
    ug_str += UniMessage.image(raw=user_guidance)
    ug_str += '⚠️⚠️⚠️重要⚠️⚠️⚠️'

    msg = UniMessage.text('项目地址: github.com/DiaoDaiaChan/nonebot-plugin-comfyui')
    img = UniMessage.image(raw=img)
    msg = msg + img

    await msg.send()
    await asyncio.sleep(1)
    await ug_str.finish()


@view_workflow.handle()
async def _(search):

    html_, msg = await ComfyuiHelp().get_html(search)
    img = await html_to_pic(html=html_)

    msg = UniMessage.image(raw=img) + msg
    await msg.finish()


@backend.handle()
async def _():
    data = await get_backend_status()

    env = Environment(loader=FileSystemLoader(str(PLUGIN_DIR / 'template')))
    template = env.get_template('backend_status.html')

    html_output = template.render(data=data)
    img = await html_to_pic(html=html_output)

    msg = UniMessage.image(raw=img)
    await msg.finish()

reg_command = asyncio.run(start_up_func())
