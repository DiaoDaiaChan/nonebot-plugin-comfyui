import copy
import re
from typing import Any
from nonebot import logger
from .comfy_client import comfy_client


class LoraEngine:
    """LoRA 提示词解析与 API JSON 节点注入引擎"""

    LORA_NODE_TEMPLATE: dict[str, Any] = {
        "inputs": {
            "lora_name": "",
            "strength_model": 1.0,
            "strength_clip": 1.0,
            "model": ["", 0],
            "clip": ["", 1]
        },
        "class_type": "LoraLoader",
        "_meta": {
            "title": "nonebot_plugin_comfyui auto load"
        }
    }

    @staticmethod
    def extract_loras_from_prompt(prompt: str) -> tuple[str, list[tuple[str, float]]]:
        """
        从 prompt 中提取 `<lora:name:weight>` 结构。
        返回 (清洗后的 prompt, [(lora_name, weight)])
        """
        loras: list[tuple[str, float]] = []
        clean_parts: list[str] = []

        for part in prompt.split(','):
            part_str = part.strip()
            if part_str.startswith('<lora:') and part_str.endswith('>'):
                content = part_str[6:-1]
                if ':' in content:
                    name, val_str = content.split(':', 1)
                    try:
                        weight = float(val_str.strip())
                    except ValueError:
                        weight = 1.0
                    loras.append((name.strip(), weight))
                else:
                    loras.append((content.strip(), 1.0))
            else:
                if part_str:
                    clean_parts.append(part_str)

        return ', '.join(clean_parts), loras

    @classmethod
    async def match_available_loras(
        cls,
        backend_url: str,
        parsed_loras: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        """与 ComfyUI 后端现存的 LoRA 文件进行模糊匹配"""
        if not parsed_loras:
            return []

        all_backend_loras = await comfy_client.get_loras(backend_url)
        matched: list[tuple[str, float]] = []

        for lora_name, weight in parsed_loras:
            found = False
            for real_lora in all_backend_loras:
                if lora_name in real_lora:
                    logger.info(f"LoRA 匹配成功: '{lora_name}' -> '{real_lora}' (权重: {weight})")
                    matched.append((real_lora, weight))
                    found = True
                    break
            if not found:
                logger.warning(f"未能找到匹配的 LoRA: '{lora_name}'")

        return matched

    @classmethod
    def apply_loras_to_api_json(
        cls,
        api_json: dict[str, Any],
        lora_config: Any,
        loras: list[tuple[str, float]]
    ) -> dict[str, Any]:
        """
        根据 reflex 中的 lora 配置，将 LoRA 节点串联插入到 api_json 图结构中
        """
        if not loras or not lora_config:
            return api_json

        new_api_json = copy.deepcopy(api_json)
        build_lora_node: dict[str, Any] = {}

        if isinstance(lora_config, list):
            for node_cfg in lora_config:
                for k, v in node_cfg.items():
                    if len(loras) == 1:
                        tmp = copy.deepcopy(cls.LORA_NODE_TEMPLATE)
                        self_node_id = str(k)
                        from_model = str(v['from']['model'])
                        from_clip = str(v['from']['clip'])

                        lora_name, weight = loras[0]
                        tmp['inputs']['model'][0] = from_model
                        tmp['inputs']['clip'][0] = from_clip
                        tmp['inputs']['strength_model'] = weight
                        tmp['inputs']['strength_clip'] = weight
                        tmp['inputs']['lora_name'] = lora_name

                        for to_type, to_nodes in v.get('to', {}).items():
                            for target_node in to_nodes:
                                if str(target_node) in new_api_json:
                                    new_api_json[str(target_node)]['inputs'][to_type][0] = self_node_id

                        build_lora_node[self_node_id] = tmp
                    else:
                        self_node_id_int = int(k) - 1
                        from_model = str(v['from']['model'])
                        from_clip = str(v['from']['clip'])

                        for index, (lora_name, weight) in enumerate(loras):
                            tmp = copy.deepcopy(cls.LORA_NODE_TEMPLATE)
                            self_node_id_int += 1
                            curr_id_str = str(self_node_id_int)

                            if index == 0:
                                f_model, f_clip = from_model, from_clip
                            else:
                                prev_id = str(self_node_id_int - 1)
                                f_model, f_clip = prev_id, prev_id

                            tmp['inputs']['model'][0] = f_model
                            tmp['inputs']['clip'][0] = f_clip
                            tmp['inputs']['strength_model'] = weight
                            tmp['inputs']['strength_clip'] = weight
                            tmp['inputs']['lora_name'] = lora_name

                            if index == len(loras) - 1:
                                for to_type, to_nodes in v.get('to', {}).items():
                                    for target_node in to_nodes:
                                        if str(target_node) in new_api_json:
                                            new_api_json[str(target_node)]['inputs'][to_type][0] = curr_id_str

                            build_lora_node[curr_id_str] = tmp

        elif isinstance(lora_config, (int, str)):
            base_node_id = int(lora_config)
            link_model_list: list[str] = []
            link_clip_list: list[str] = []

            for node_id, node_data in new_api_json.items():
                m_in = node_data.get('inputs', {}).get('model')
                c_in = node_data.get('inputs', {}).get('clip')
                if m_in and str(m_in[0]) == str(base_node_id):
                    link_model_list.append(node_id)
                if c_in and str(c_in[0]) == str(base_node_id):
                    link_clip_list.append(node_id)

            curr_node = base_node_id - 1
            for index, (lora_name, weight) in enumerate(loras):
                tmp = copy.deepcopy(cls.LORA_NODE_TEMPLATE)
                curr_node += 1
                curr_str = str(curr_node)

                if index == 0:
                    raw_lora = new_api_json.get(str(base_node_id), copy.deepcopy(cls.LORA_NODE_TEMPLATE))
                    raw_lora['inputs']['strength_model'] = weight
                    raw_lora['inputs']['strength_clip'] = weight
                    raw_lora['inputs']['lora_name'] = lora_name
                    build_lora_node[str(base_node_id)] = raw_lora
                else:
                    prev_str = str(curr_node - 1)
                    tmp['inputs']['model'][0] = prev_str
                    tmp['inputs']['clip'][0] = prev_str
                    tmp['inputs']['strength_model'] = weight
                    tmp['inputs']['strength_clip'] = weight
                    tmp['inputs']['lora_name'] = lora_name
                    build_lora_node[curr_str] = tmp

                    if index == len(loras) - 1:
                        for m_id in link_model_list:
                            new_api_json[m_id]['inputs']['model'][0] = curr_str
                        for c_id in link_clip_list:
                            new_api_json[c_id]['inputs']['clip'][0] = curr_str

        new_api_json.update(build_lora_node)
        return new_api_json


lora_engine = LoraEngine()
