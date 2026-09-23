import copy
import json
import os
import random
from pathlib import Path
from typing import Any
import aiofiles
from nonebot import logger

from ..config import config
from ..constants import MAX_SEED, OTHER_ACTION, MODIFY_ACTION, REFLEX_DICT
from ..exceptions import (
    ReflexJsonNotFoundError,
    ReflexJsonError,
    WorkflowAdminLimitation,
    WorkflowGroupLimitation,
    WorkflowNotAvailableInSelectedBackend,
    NoAvailableBackendForSelectedWorkflow,
    ArgsError
)
from .lora_engine import lora_engine


class WorkflowEngine:
    """工作流检索、Reflex 规则应用与 API JSON 图重构引擎"""

    @staticmethod
    def get_workflows_dir() -> Path:
        return Path(config.comfyui_workflows_dir).resolve()

    @classmethod
    def list_workflows(cls, search: str | None = None, index: int | None = None) -> list[str]:
        """列出或筛选所有合法的工作流名称"""
        wf_dir = cls.get_workflows_dir()
        if not wf_dir.exists():
            return []

        wf_files: list[str] = []
        for file in os.listdir(wf_dir):
            if file.endswith('.json') and not file.endswith('_reflex.json'):
                name = file[:-5]
                # 检查是否存在匹配的 reflex 文件
                reflex_file = wf_dir / f"{name}_reflex.json"
                if reflex_file.exists():
                    if search and search in name:
                        wf_files.append(name)
                    elif not search:
                        wf_files.append(name)

        if index is not None:
            if 1 <= index <= len(wf_files):
                return [wf_files[index - 1]]
            return []

        return wf_files

    @classmethod
    async def load_workflow_files(cls, wf_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """异步加载工作流 API JSON 和对应的 Reflex JSON"""
        wf_dir = cls.get_workflows_dir()
        api_path = wf_dir / f"{wf_name}.json"
        reflex_path = wf_dir / f"{wf_name}_reflex.json"

        if not api_path.exists() or not reflex_path.exists():
            raise ReflexJsonNotFoundError(f"未找到工作流 {wf_name} 的完整定义文件")

        async with aiofiles.open(api_path, 'r', encoding='utf-8') as f:
            api_json = json.loads(await f.read())

        async with aiofiles.open(reflex_path, 'r', encoding='utf-8') as f:
            reflex_json = json.loads(await f.read())

        return api_json, reflex_json

    @staticmethod
    def calculate_dimensions(
        shape: str | None = None,
        accept_ratio: str | None = None,
        width: int | None = None,
        height: int | None = None
    ) -> tuple[int, int]:
        """统一计算分辨率"""
        # 1. 优先根据预设形制 shape 计算
        if shape:
            preset = config.comfyui_shape_preset.get(shape)
            if preset:
                return preset[0], preset[1]
            if 'x' in shape:
                try:
                    w_s, h_s = shape.split('x')
                    return int(w_s), int(h_s)
                except ValueError:
                    pass

        # 2. 根据比例 accept_ratio 计算 (例如 16:9)
        if accept_ratio and ':' in accept_ratio:
            try:
                w_ratio, h_ratio = map(int, accept_ratio.split(':'))
                total_pixels = config.comfyui_base_res ** 2
                aspect = w_ratio / h_ratio
                if aspect >= 1:
                    w = int((total_pixels * aspect) ** 0.5)
                    h = int(w / aspect)
                else:
                    h = int((total_pixels / aspect) ** 0.5)
                    w = int(h * aspect)
                return w, h
            except Exception:
                raise ArgsError(f"画幅比例参数无效: {accept_ratio}")

        # 3. 默认宽与高
        w = width or config.comfyui_default_value.get("width", 832)
        h = height or config.comfyui_default_value.get("height", 1216)
        return w, h

    @classmethod
    def validate_permissions(
        cls,
        reflex_json: dict[str, Any],
        user_id: str,
        group_id: str
    ) -> None:
        """校验工作流的管理员与群组权限"""
        is_admin = reflex_json.get('admin', False)
        if is_admin and user_id not in config.comfyui_superusers:
            raise WorkflowAdminLimitation("此工作流仅限管理员使用")

        allowed_groups = reflex_json.get('group')
        if allowed_groups and group_id:
            try:
                gid_int = int(group_id)
                if gid_int not in allowed_groups:
                    raise WorkflowGroupLimitation("此工作流不允许在当前群使用")
            except ValueError:
                pass

    @classmethod
    def apply_reflex(
        cls,
        raw_api_json: dict[str, Any],
        reflex_json: dict[str, Any],
        params: dict[str, Any],
        init_images: list[dict[str, Any]] | None = None,
        backend_index: int = 0
    ) -> dict[str, Any]:
        """将生成参数应用到 API JSON 图中"""
        api_json = copy.deepcopy(raw_api_json)
        init_images = init_images or []

        prompt = params.get("prompt", "")
        negative_prompt = params.get("negative_prompt", "")
        width = params.get("width", 832)
        height = params.get("height", 1216)
        seed = params.get("seed", random.randint(0, MAX_SEED))
        steps = params.get("steps", 28)
        cfg_scale = params.get("cfg_scale", 7.0)
        sampler = params.get("sampler", "dpmpp_2m")
        scheduler = params.get("scheduler", "karras")
        denoise_strength = params.get("denoise_strength", 1.0)
        batch_size = params.get("batch_size", 1)
        model = params.get("model", "")
        override = params.get("override", False)
        override_ng = params.get("override_ng", False)
        cli_args = params.get("args")

        # 映射表
        update_mapping: dict[str, dict[str, Any]] = {
            "sampler": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg_scale,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": denoise_strength
            },
            "seed": {
                "seed": seed,
                "noise_seed": seed
            },
            "image_size": {
                "width": width,
                "height": height,
                "batch_size": batch_size
            },
            "prompt": {
                "text": prompt,
                "Text": prompt,
                "prompt": prompt
            },
            "negative_prompt": {
                "text": negative_prompt,
                "Text": negative_prompt,
                "prompt": negative_prompt
            },
            "checkpoint": {
                "ckpt_name": model if model else None,
                "unet_name": model if model else None,
                "model": model if model else None
            },
            "load_image": {
                "image": init_images[0]['name'] if init_images else None
            },
            "tipo": {
                "width": width,
                "height": height,
                "seed": seed,
                "tags": prompt
            }
        }

        # 遍历 reflex 配置节点并改写 inputs
        for item, node_id in reflex_json.items():
            if node_id and item not in OTHER_ACTION:
                org_node_id = node_id
                target_ids = []
                if isinstance(node_id, list):
                    target_ids = [str(x) for x in node_id]
                elif isinstance(node_id, (int, str)):
                    target_ids = [str(node_id)]
                elif isinstance(node_id, dict):
                    target_ids = [str(x) for x in node_id.keys()]

                for nid in target_ids:
                    node_data = api_json.get(nid)
                    if node_data and item in update_mapping:
                        inputs = node_data.get('inputs', {})
                        for k, v in update_mapping[item].items():
                            if k in inputs and v is not None:
                                inputs[k] = v

                # 高级 node 覆写控制 (override)
                if isinstance(org_node_id, dict) and item not in MODIFY_ACTION:
                    for node_key, override_dict in org_node_id.items():
                        single_override = override_dict.get("override", {})
                        node_str = str(node_key)
                        if single_override and node_str in api_json:
                            for inp_key, action in single_override.items():
                                if action == "randint":
                                    api_json[node_str]['inputs'][inp_key] = random.randint(0, MAX_SEED)
                                elif action == "append_prompt" and not override:
                                    orig = raw_api_json[node_str]['inputs'].get(inp_key, "")
                                    api_json[node_str]['inputs'][inp_key] = prompt + orig
                                elif action == "append_negative_prompt" and not override_ng:
                                    orig = raw_api_json[node_str]['inputs'].get(inp_key, "")
                                    api_json[node_str]['inputs'][inp_key] = negative_prompt + orig
                                elif action == "replace_prompt" and not override:
                                    orig = raw_api_json[node_str]['inputs'].get(inp_key, "")
                                    api_json[node_str]['inputs'][inp_key] = orig.replace("{prompt}", prompt)
                                elif action == "replace_negative_prompt" and not override_ng:
                                    orig = raw_api_json[node_str]['inputs'].get(inp_key, "")
                                    api_json[node_str]['inputs'][inp_key] = orig.replace("{prompt}", negative_prompt)
                                elif "upscale" in action:
                                    scale = 1.5
                                    if "_" in action:
                                        scale = float(action.split("_")[1])
                                    res = width if inp_key == 'width' else height
                                    api_json[node_str]['inputs'][inp_key] = int(res * scale)
                                elif "value" in action:
                                    if "_" in action:
                                        val_str = action.split("_")[1]
                                        t_str = action.split("_")[2]
                                        if t_str == "int":
                                            val = int(val_str)
                                        elif t_str == "float":
                                            val = float(val_str)
                                        else:
                                            val = str(val_str)
                                        api_json[node_str]['inputs'][inp_key] = val
                                elif "image" in action and init_images:
                                    img_idx = int(action.split("_")[1])
                                    if img_idx < len(init_images):
                                        api_json[node_str]['inputs'][inp_key] = init_images[img_idx]['name']

            # 自定义注册参数映射 (reg_args)
            elif item == "reg_args" and cli_args:
                args_dict = vars(cli_args)
                for node_k, item_data in node_id.items():
                    node_str = str(node_k)
                    if node_str not in api_json:
                        continue
                    for arg in item_data.get("args", []):
                        dest_key = arg.get("dest")
                        type_str = arg.get("type")
                        json_key = list(arg["dest_to_value"].keys())[0] if "dest_to_value" in arg else dest_key
                        preset_dict = arg.get("preset", {})

                        if "default" in arg:
                            api_json[node_str]['inputs'][json_key] = arg["default"]

                        if hasattr(cli_args, dest_key):
                            val = args_dict[dest_key]
                            if preset_dict and val in preset_dict:
                                val = preset_dict[val]
                            if type_str == "int":
                                val = int(val)
                            elif type_str == "float":
                                val = float(val)
                            elif type_str == "bool":
                                val = bool(val)
                            api_json[node_str]['inputs'][json_key] = val

            # 后端差异映射 (reflex)
            elif item == "reflex":
                for be_idx_str, node_reflex in node_id.items():
                    if backend_index == int(be_idx_str):
                        for n_id, inps in node_reflex.items():
                            if str(n_id) in api_json:
                                api_json[str(n_id)]['inputs'].update(inps)

        # 应用 LoRA
        loras = params.get("loras", [])
        if loras and "lora" in reflex_json:
            api_json = lora_engine.apply_loras_to_api_json(api_json, reflex_json["lora"], loras)

        return api_json


workflow_engine = WorkflowEngine()
