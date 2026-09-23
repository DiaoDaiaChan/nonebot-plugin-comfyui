from nonebot import get_driver, logger
from nonebot.plugin import require, PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_htmlrender")

from .config import Config, config, init_workflows_dir
from .commands import (
    register_workflow_commands,
    comfyui_cmd,
    queue_cmd,
    api_cmd,
    help_cmd,
    view_workflow_cmd,
    backend_status_cmd,
    today_girl_cmd,
    dan_cmd,
    llm_cmd,
    get_ckpt_cmd,
    get_loras_cmd,
    get_task_cmd
)
from .utils.update_check import check_package_update

# 启动生命周期钩子
driver = get_driver()


@driver.on_startup
async def _on_startup() -> None:
    logger.info("ComfyUI 插件正在初始化...")
    init_workflows_dir(config.comfyui_workflows_dir)

    # 异步检查版本更新
    update_msg, is_new = await check_package_update()
    if is_new and update_msg:
        logger.info(update_msg)
        try:
            bot = nonebot.get_bot()
            for su in config.comfyui_superusers:
                await bot.send_private_msg(user_id=int(su), message=update_msg)
        except Exception:
            pass


# 在插件加载时同步扫描并注册工作流命令（纯同步，杜绝 asyncio.run）
register_workflow_commands()

__plugin_meta__ = PluginMetadata(
    name="Comfyui绘图插件",
    description="专门适配Comfyui的绘图插件",
    usage="基础生图命令: prompt，发送 comfyui帮助 来获取支持的参数",
    config=Config,
    type="application",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra={"author": "DiaoDaiaChan", "email": "437012661@qq.com"},
    homepage="https://github.com/DiaoDaiaChan/nonebot-plugin-comfyui"
)
