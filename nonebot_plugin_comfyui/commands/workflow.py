import asyncio
from nonebot.plugin.on import on_command
from nonebot_plugin_alconna import on_alconna, Args, Alconna, UniMessage
try:
    from nonebot_plugin_htmlrender import html_to_pic, md_to_pic
except ImportError:
    from nonebot_plugin_htmlrender import render_html, render_markdown

    async def html_to_pic(html: str, **kwargs) -> bytes:
        res = await render_html(html, **kwargs)
        return getattr(res, "data", bytes(res))

    async def md_to_pic(md: str, **kwargs) -> bytes:
        res = await render_markdown(md, **kwargs)
        return getattr(res, "data", bytes(res))

from ..config import PLUGIN_DIR
from ..utils.render import render_help_html, render_workflows_html, render_backend_status_html
from .dynamic import REGISTERED_COMMANDS

help_cmd = on_command(
    "comfyui帮助",
    aliases={"帮助", "菜单", "help", "指令"},
    priority=1,
    block=False
)

view_workflow_cmd = on_alconna(
    Alconna("查看工作流", Args["search?", str]),
    priority=5,
    block=True,
    use_cmd_start=True
)

backend_status_cmd = on_command(
    "后端",
    aliases={"comfyui后端"},
    priority=1,
    block=False
)


@help_cmd.handle()
async def handle_help() -> None:
    html_content = await render_help_html(REGISTERED_COMMANDS)
    img_bytes = await html_to_pic(html=html_content)

    source_template_path = PLUGIN_DIR / "template" / "example.md"
    md_content = ""
    if source_template_path.exists():
        with open(source_template_path, "r", encoding="utf-8") as f:
            md_content = f.read()

    msg = UniMessage.text("项目地址: github.com/DiaoDaiaChan/nonebot-plugin-comfyui\n")
    msg += UniMessage.image(raw=img_bytes)
    await msg.send()

    if md_content:
        await asyncio.sleep(1)
        user_guidance = await md_to_pic(md=md_content)
        ug_msg = UniMessage.text("⚠️⚠️⚠️ 基础使用教程 ⚠️⚠️⚠️\n")
        ug_msg += UniMessage.image(raw=user_guidance)
        ug_msg += "\n⚠️⚠️⚠️ 重要 ⚠️⚠️⚠️"
        await ug_msg.finish()


@view_workflow_cmd.handle()
async def handle_view_workflow(search: str | None = None) -> None:
    html_content, screenshot_bytes = await render_workflows_html(search)
    img_bytes = await html_to_pic(html=html_content)

    msg = UniMessage.image(raw=img_bytes)
    if screenshot_bytes:
        msg += "\n工作流前端预览:\n"
        msg += UniMessage.image(raw=screenshot_bytes)

    await msg.finish()


@backend_status_cmd.handle()
async def handle_backend_status() -> None:
    html_content = await render_backend_status_html()
    img_bytes = await html_to_pic(html=html_content)
    await UniMessage.image(raw=img_bytes).finish()
