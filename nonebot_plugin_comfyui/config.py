from nonebot import get_plugin_config, logger

from pydantic import BaseModel


class Config(BaseModel):
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_model: str = ""
    comfyui_workflows_dir: str = ""
    comfyui_default_workflows: str = "txt2img"
    comfyui_max_res: int = 2048
    comfyui_base_res: int = 1024


config = get_plugin_config(Config)
config.comfyui_max_res = config.comfyui_max_res ^ 2
config.comfyui_base_res = config.comfyui_base_res ^ 2

logger.info(f"Comfyui插件加载完成, 配置: {config}")
