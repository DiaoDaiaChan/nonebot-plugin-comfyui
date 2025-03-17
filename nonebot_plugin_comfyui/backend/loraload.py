import re
import json


def process_workflow(input_text, pseudo_api_workflow):
    def extract_lora_info(text):
        pattern = r'<lora:([^:]+(?:[^>]*[^:]+)?):([\d.]+)>'
        matches = re.findall(pattern, text)
        lora_dict = {}
        for lora_name, lora_weight in matches:
            key = f"{lora_name}.safetensors"
            lora_dict[key] = float(lora_weight)
        return lora_dict

    def remove_lora_placeholders(text):
        pattern = r'<lora:[^>]+>'
        return re.sub(pattern, '', text).strip()

    def insert_lora_nodes(workflow, lora_dict):
        if not lora_dict:
            # 如果没有 lora 信息，移除所有 <loras> 占位符
            for key in list(workflow.keys()):
                if key == "<loras>":
                    del workflow[key]
            return workflow

        lora_nodes = []
        for lora_name, lora_weight in lora_dict.items():
            lora_nodes.append({
                "class_type": "LoraLoader",
                "inputs": {
                    "model": ["1", 0],
                    "clip": ["1", 1],
                    "lora_name": lora_name,
                    "strength_model": lora_weight,
                    "strength_clip": lora_weight
                }
            })

        all_nodes = []
        lora_placeholder_indices = []
        index = 0
        for node_id, node in workflow.items():
            if node_id == "<loras>":
                lora_placeholder_indices.append(index)
            else:
                all_nodes.append((node_id, node))
            index += 1

        # 在每个 <loras> 占位符位置插入 lora 节点
        for idx in reversed(lora_placeholder_indices):
            all_nodes = all_nodes[:idx] + [(f"lora_{i}", node) for i, node in enumerate(lora_nodes, start=1)] + all_nodes[
                                                                                                                   idx:]

        new_workflow = {}
        id_mapping = {}
        for i, (node_id, node) in enumerate(all_nodes, start=1):
            new_id = str(i)
            id_mapping[node_id] = new_id
            new_workflow[new_id] = node

        # 更新依赖关系
        for node in new_workflow.values():
            for input_key, input_value in node.get("inputs", {}).items():
                if isinstance(input_value, list) and len(input_value) > 0 and input_value[0].isdigit():
                    old_id = input_value[0]
                    if old_id in id_mapping:
                        input_value[0] = id_mapping[old_id]

        return new_workflow

    def replace_prompt(workflow, prompt_text):
        for node in workflow.values():
            if node.get("class_type") == "CLIPTextEncode":
                node["inputs"]["text"] = prompt_text
        return workflow

    # 由于原始 JSON 格式可能有误，这里进行修正
    pseudo_api_workflow = pseudo_api_workflow.replace('"<loras>",', '"<loras>": null,')
    workflow = json.loads(pseudo_api_workflow)

    # 提取 lora 信息
    lora_info = extract_lora_info(input_text)

    # 移除 lora 占位符并获取提示词
    prompt_text = remove_lora_placeholders(input_text)

    # 插入 lora 节点
    workflow = insert_lora_nodes(workflow, lora_info)

    # 替换正向提示词
    workflow = replace_prompt(workflow, prompt_text)

    return workflow


# 示例输入文本
input_text = '<lora:a:0.8>,<lora:b:1.2>,<lora:c-123:1.1>,1girl'

# 包含多个 <loras> 标签的伪 API 工作流
pseudo_api_workflow = '''
{
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "your_base_model.ckpt"
        }
    },
    "<loras>",
    "2": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "<prompt>",
            "clip": [
                "1",
                1
            ]
        }
    },
    "<loras>",
    "3": {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": 512,
            "height": 512,
            "batch_size": 1
        }
    },
    "4": {
        "class_type": "KSampler",
        "inputs": {
            "model": [
                "1",
                0
            ],
            "positive": [
                "2",
                0
            ],
            "negative": [
                "2",
                0
            ],
            "latent_image": [
                "3",
                0
            ],
            "steps": 20,
            "cfg": 7,
            "sampler_name": "euler",
            "scheduler": "normal"
        }
    },
    "5": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": [
                "4",
                0
            ],
            "vae": [
                "1",
                2
            ]
        }
    },
    "6": {
        "class_type": "SaveImage",
        "inputs": {
            "images": [
                "5",
                0
            ]
        }
    },
    "9": {
        "class_type": "KSampler",
        "inputs": {
            "model": [
                "8",
                0
            ],
            "positive": [
                "2",
                0
            ],
            "negative": [
                "2",
                0
            ],
            "latent_image": [
                "3",
                0
            ],
            "steps": 20,
            "cfg": 7,
            "sampler_name": "euler",
            "scheduler": "normal"
        }
    },
    "10": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": [
                "9",
                0
            ],
            "vae": [
                "1",
                2
            ]
        }
    },
    "11": {
        "class_type": "SaveImage",
        "inputs": {
            "images": [
                "10",
                0
            ]
        }
    }
}
'''

# 调用封装函数进行处理
processed_workflow = process_workflow(input_text, pseudo_api_workflow)

# 打印处理后的工作流
print("处理后的 API 工作流:")
print(json.dumps(processed_workflow, indent=4))
