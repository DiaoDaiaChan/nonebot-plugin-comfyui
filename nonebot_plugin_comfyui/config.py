from nonebot import get_plugin_config, logger

from pathlib import Path

from pydantic import BaseModel


class Config(BaseModel):
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_url_list: list = ["http://127.0.0.1:8188", "http://127.0.0.1:8288"]
    comfyui_multi_backend: bool = False
    comfyui_model: str = ""
    comfyui_workflows_dir: str = "./data/comfyui"
    comfyui_default_workflows: str = "txt2img"
    comfyui_max_res: int = 2048
    comfyui_base_res: int = 1024
    comfyui_audit: bool = False
    comfyui_audit_site: str = "http://server.20020026.xyz:7865"
    comfyui_save_image: bool = True
    comfyui_cd: int = 20
    comfyui_day_limit: int = 50


config = get_plugin_config(Config)
Path(config.comfyui_workflows_dir).resolve().mkdir(parents=True, exist_ok=True)

logger.info(f"Comfyui插件加载完成, 配置: {config}")
