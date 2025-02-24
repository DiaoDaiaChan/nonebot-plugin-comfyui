import os
import shutil

from nonebot import get_plugin_config, logger, get_driver
from pathlib import Path
from pydantic import BaseModel

PLUGIN_DIR = Path(os.path.dirname(os.path.abspath(__file__))).resolve()


class Config(BaseModel):
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_url_list: list = ["http://127.0.0.1:8188", "http://127.0.0.1:8288"]
    comfyui_multi_backend: bool = False
    comfyui_model: str = ""
    comfyui_workflows_dir: str = "./data/comfyui"
    comfyui_default_workflows: str = "txt2img"
    comfyui_max_res: int = 2048
    comfyui_base_res: int = 1024
    comfyui_audit: bool = True
    comfyui_audit_local: bool = False
    comfyui_audit_level: int = 2
    comfyui_audit_comp: bool = False
    comfyui_audit_site: str = "http://server.20020026.xyz:7865"
    comfyui_save_image: bool = True
    comfyui_cd: int = 20
    comfyui_day_limit: int = 50
    comfyui_limit_as_seconds: bool = False
    comfyui_timeout: int = 5
    comfyui_shape_preset: dict = {
        "p": (832, 1216),
        "l": (1216, 832),
        "s": (1024, 1024),
        "lp": (1152, 1536),
        "ll": (1536, 1152),
        "ls": (1240, 1240),
        "up": (960, 1920),
        "ul": (1920, 960)
    }
    comfyui_superusers: list = []


config = get_plugin_config(Config)
wf_dir = Path(config.comfyui_workflows_dir)
superusers = list(get_driver().config.superusers)
config.comfyui_superusers = superusers

if config.comfyui_multi_backend is False:
    config.comfyui_url_list = [config.comfyui_url]

if wf_dir.exists():
    logger.info(f"Comfyui工作流文件夹存在")
else:
    wf_dir.resolve().mkdir(parents=True, exist_ok=True)

    current_dir = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
    build_in_wf = current_dir / "build_in_wf"
    for file in build_in_wf.iterdir():
        if file.is_file():
            shutil.copy(file, wf_dir)

logger.info(f"Comfyui插件加载完成, 配置: {config}")
