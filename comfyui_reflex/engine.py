"""
Core Reflex Execution Engine.
Applies reflex configurations and user generation parameters to ComfyUI API JSON graphs.
Pure Python, zero framework dependencies.
"""

from __future__ import annotations

import copy
import random
from typing import Any, Mapping

from .constants import (
    MAX_SEED,
    OTHER_ACTION,
    MODIFY_ACTION,
    SAMPLER_MAPPING,
    SCHEDULER_MAPPING,
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT
)
from .lora import apply_loras_to_api_json
from .models import ReflexConfig


class ReflexEngine:
    """Reflex 图重构引擎类"""

    @classmethod
    def apply_reflex(
        cls,
        raw_api_json: dict[str, Any],
        reflex_json: dict[str, Any] | ReflexConfig,
        params: dict[str, Any] | None = None,
        init_images: list[dict[str, Any]] | None = None,
        backend_index: int = 0
    ) -> dict[str, Any]:
        """
        核心方法：将生成参数与 Reflex 规则应用到 ComfyUI API JSON 图中。
        
        参数:
            raw_api_json: 原始 ComfyUI 工作流 API JSON 图 (node_id -> node_data)
            reflex_json: 对应工作流的 reflex 配置 (dict 或 ReflexConfig)
            params: 用户传入的生成参数字典
            init_images: 上传的输入图像信息列表 (含 'name' 键)
            backend_index: 当前选中的后端索引编号 (默认 0)
        
        返回:
            更新后的可直接提交给 ComfyUI /prompt 接口执行的 final_api_json
        """
        api_json = copy.deepcopy(raw_api_json)
        init_images = init_images or []
        params = params or {}

        # 提取参数
        prompt = params.get("prompt", "")
        negative_prompt = params.get("negative_prompt", "")
        width = params.get("width", DEFAULT_WIDTH)
        height = params.get("height", DEFAULT_HEIGHT)
        seed = params.get("seed", random.randint(0, MAX_SEED))
        steps = params.get("steps", 28)
        cfg_scale = params.get("cfg_scale", 7.0)
        raw_sampler = params.get("sampler", "dpmpp_2m")
        sampler = SAMPLER_MAPPING.get(raw_sampler, raw_sampler)
        raw_scheduler = params.get("scheduler", "karras")
        scheduler = SCHEDULER_MAPPING.get(raw_scheduler, raw_scheduler)
        denoise_strength = params.get("denoise_strength", 1.0)
        batch_size = params.get("batch_size", 1)
        model = params.get("model", "")
        override = params.get("override", False)
        override_ng = params.get("override_ng", False)
        cli_args = params.get("args")

        # 标准映射表
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
            if not node_id:
                continue

            # 特殊判断：如果键名为 override，但其内容包含节点覆写结构（例如 {node_id: {"override": {...}}}）
            is_node_override_block = (
                item == "override"
                and isinstance(node_id, dict)
                and any(isinstance(v, dict) and "override" in v for v in node_id.values())
            )

            if item not in OTHER_ACTION or is_node_override_block:
                org_node_id = node_id
                target_ids: list[str] = []
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
                        if not isinstance(override_dict, dict):
                            continue
                        single_override = override_dict.get("override", {})
                        node_str = str(node_key)
                        if single_override and node_str in api_json:
                            node_inputs = api_json[node_str].setdefault('inputs', {})
                            raw_node_inputs = raw_api_json.get(node_str, {}).get('inputs', {})
                            for inp_key, action in single_override.items():
                                if not isinstance(action, str):
                                    continue
                                if action == "randint":
                                    node_inputs[inp_key] = random.randint(0, MAX_SEED)
                                elif action == "append_prompt" and not override:
                                    orig = raw_node_inputs.get(inp_key, "")
                                    node_inputs[inp_key] = prompt + str(orig)
                                elif action == "append_negative_prompt" and not override_ng:
                                    orig = raw_node_inputs.get(inp_key, "")
                                    node_inputs[inp_key] = negative_prompt + str(orig)
                                elif action == "replace_prompt" and not override:
                                    orig = raw_node_inputs.get(inp_key, "")
                                    node_inputs[inp_key] = str(orig).replace("{prompt}", prompt)
                                elif action == "replace_negative_prompt" and not override_ng:
                                    orig = raw_node_inputs.get(inp_key, "")
                                    node_inputs[inp_key] = str(orig).replace("{prompt}", negative_prompt)
                                elif "upscale" in action:
                                    scale = 1.5
                                    if "_" in action:
                                        try:
                                            scale = float(action.split("_")[1])
                                        except (ValueError, IndexError):
                                            scale = 1.5
                                    is_width = 'width' in inp_key.lower() or inp_key == 'w' or inp_key.endswith('_w') or inp_key.startswith('w_')
                                    res = width if is_width else height
                                    node_inputs[inp_key] = int(res * scale)
                                elif "value" in action:
                                    parts = action.split("_")
                                    if len(parts) >= 3:
                                        val_str = parts[1]
                                        t_str = parts[2]
                                        if t_str == "int":
                                            val = int(val_str)
                                        elif t_str == "float":
                                            val = float(val_str)
                                        else:
                                            val = str(val_str)
                                        node_inputs[inp_key] = val
                                    elif len(parts) == 2:
                                        node_inputs[inp_key] = parts[1]
                                elif "image" in action and init_images:
                                    parts = action.split("_")
                                    if len(parts) >= 2:
                                        try:
                                            img_idx = int(parts[1])
                                            if img_idx < len(init_images):
                                                node_inputs[inp_key] = init_images[img_idx]['name']
                                        except ValueError:
                                            pass

            # 自定义注册参数映射 (reg_args)
            elif item == "reg_args" and cli_args and isinstance(node_id, dict):
                args_dict = vars(cli_args) if hasattr(cli_args, '__dict__') and not isinstance(cli_args, dict) else (dict(cli_args) if isinstance(cli_args, dict) else {})
                for node_k, item_data in node_id.items():
                    node_str = str(node_k)
                    if node_str not in api_json or not isinstance(item_data, dict):
                        continue
                    node_inputs = api_json[node_str].setdefault('inputs', {})
                    for arg in item_data.get("args", []):
                        if not isinstance(arg, dict):
                            continue
                        dest_key = arg.get("dest")
                        type_str = arg.get("type")
                        json_key = list(arg["dest_to_value"].keys())[0] if "dest_to_value" in arg else dest_key
                        preset_dict = arg.get("preset", {})

                        if "default" in arg:
                            node_inputs[json_key] = arg["default"]

                        if dest_key and (dest_key in args_dict or hasattr(cli_args, dest_key)):
                            val = args_dict.get(dest_key, getattr(cli_args, dest_key, None))
                            if val is not None:
                                if preset_dict and val in preset_dict:
                                    val = preset_dict[val]
                                try:
                                    if type_str == "int":
                                        val = int(val)
                                    elif type_str == "float":
                                        val = float(val)
                                    elif type_str == "bool":
                                        val = bool(val)
                                except (ValueError, TypeError):
                                    pass
                                node_inputs[json_key] = val

            # 后端差异映射 (reflex)
            elif item == "reflex" and isinstance(node_id, dict):
                for be_idx_str, node_reflex in node_id.items():
                    try:
                        if backend_index == int(be_idx_str) and isinstance(node_reflex, dict):
                            for n_id, inps in node_reflex.items():
                                if str(n_id) in api_json and isinstance(inps, dict):
                                    api_json[str(n_id)].setdefault('inputs', {}).update(inps)
                    except (ValueError, TypeError):
                        pass

        # 应用 LoRA
        loras = params.get("loras", [])
        if loras and "lora" in reflex_json:
            api_json = apply_loras_to_api_json(api_json, reflex_json["lora"], loras)

        return api_json


# 顶层便利函数
apply_reflex = ReflexEngine.apply_reflex
