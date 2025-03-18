import re
import json

def replace_lora_nodes(input_string, base_json):
    # 正则表达式用于匹配 <lora:name:weight> 或 <nodename:name:weight> 格式
    lora_pattern = r'<([^:]+):([^:]+):([^>]+)>'
    lora_matches = re.findall(lora_pattern, input_string)
    lora_info = [(node_type, name, float(weight)) for node_type, name, weight in lora_matches]
    input_node_types = set([node_type for node_type, _, _ in lora_info])

    # 找出原 JSON 中所有节点类型
    existing_node_types = set()
    for id, node in base_json.items():
        existing_node_types.add(node["class_type"])

    # 处理输入字符串中没有但原 JSON 中有的节点
    for node_type in existing_node_types - input_node_types:
        node_id = None
        prev_node_output = None
        next_node_id = None
        next_node_input_key = None

        for id, node in base_json.items():
            if node["class_type"] == node_type:
                node_id = id
                # 找到前一个节点的输出
                if "model" in node["inputs"]:
                    prev_node_output = node["inputs"]["model"]
                # 查找连接到这个节点输出的下一个节点
                for next_id, next_node in base_json.items():
                    for input_key, input_value in next_node["inputs"].items():
                        if isinstance(input_value, list) and input_value[0] == node_id:
                            next_node_id = next_id
                            next_node_input_key = input_key
                            break
                    if next_node_id:
                        break
                break

        # 如果找到原有的节点，移除它并连接前后节点
        if node_id and prev_node_output and next_node_id and next_node_input_key:
            base_json[next_node_id]["inputs"][next_node_input_key] = prev_node_output
            del base_json[node_id]

    for node_type, _, _ in lora_info:
        # 找出原有的指定类型节点及其前后连接的节点
        node_id = None
        prev_node_output = None
        next_node_id = None
        next_node_input_key = None

        for id, node in base_json.items():
            if node["class_type"] == node_type:
                node_id = id
                # 找到前一个节点的输出
                if "model" in node["inputs"]:
                    prev_node_output = node["inputs"]["model"]
                # 查找连接到这个节点输出的下一个节点
                for next_id, next_node in base_json.items():
                    for input_key, input_value in next_node["inputs"].items():
                        if isinstance(input_value, list) and input_value[0] == node_id:
                            next_node_id = next_id
                            next_node_input_key = input_key
                            break
                    if next_node_id:
                        break
                break

        # 如果找到原有的节点，移除它
        if node_id:
            del base_json[node_id]

        # 如果没有找到前一个节点的输出，尝试默认从 CheckpointLoaderSimple 节点开始
        if not prev_node_output:
            for id, node in base_json.items():
                if node["class_type"] == "CheckpointLoaderSimple":
                    prev_node_output = [id, 0]
                    break

        if not prev_node_output:
            raise ValueError(f"Could not find a valid starting node for {node_type}.")

        # 开始添加新的指定类型节点
        next_node_id_to_use = max(int(id) for id in base_json.keys()) + 1
        for _, name, weight in lora_info:
            if node_type == "LoraLoader" or node_type == "lora":
                new_node = {
                    "class_type": "LoraLoader",
                    "inputs": {
                        "model": prev_node_output,
                        "lora_name": f"{name}.safetensors",
                        "strength_model": weight,
                        "strength_clip": weight
                    },
                    "_meta": {
                        "title": "Lora Loader"
                    }
                }
            else:
                # 这里可以根据不同的节点类型进行更详细的输入配置
                new_node = {
                    "class_type": node_type,
                    "inputs": {
                        "model": prev_node_output,
                        # 可以根据实际情况添加其他输入
                        "name": f"{name}.safetensors",
                        "strength": weight
                    },
                    "_meta": {
                        "title": f"{node_type} Node"
                    }
                }
            base_json[str(next_node_id_to_use)] = new_node
            # 更新下一个节点的输入模型
            prev_node_output = [str(next_node_id_to_use), 0]
            next_node_id_to_use += 1

        # 如果找到后续连接的节点，更新其输入
        if next_node_id and next_node_input_key:
            base_json[next_node_id]["inputs"][next_node_input_key] = prev_node_output
        else:
            # 如果没有找到后续连接节点，假设是连接到 KSampler 节点
            for id, node in base_json.items():
                if node["class_type"] == "KSampler":
                    node["inputs"]["model"] = prev_node_output
                    break

    return base_json

# 示例输入字符串，包含多个不同类型的标签
input_string = "<lora:lora1:0.7> <customnode:custom1:0.8> <lora:lora3:0.9>"

# 示例的 ComfyUI 基础工作流 JSON 数据
base_json = {
    "3": {
        "inputs": {
            "seed": 363272565452302,
            "steps": 20,
            "cfg": 8,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1,
            "model": [
                "4",
                0
            ],
            "positive": [
                "6",
                0
            ],
            "negative": [
                "7",
                0
            ],
            "latent_image": [
                "5",
                0
            ]
        },
        "class_type": "KSampler",
        "_meta": {
            "title": "KSampler"
        }
    },
    "4": {
        "inputs": {
            "ckpt_name": "NoobXL-EPS-v1.1.safetensors"
        },
        "class_type": "CheckpointLoaderSimple",
        "_meta": {
            "title": "Load Checkpoint"
        }
    },
    "5": {
        "inputs": {
            "width": 1024,
            "height": 1024,
            "batch_size": 1
        },
        "class_type": "EmptyLatentImage",
        "_meta": {
            "title": "Empty Latent Image"
        }
    },
    "6": {
        "inputs": {
            "text": "beautiful scenery nature glass bottle landscape, , purple galaxy bottle,",
            "clip": [
                "4",
                1
            ]
        },
        "class_type": "CLIPTextEncode",
        "_meta": {
            "title": "CLIP Text Encode (Prompt)"
        }
    },
    "7": {
        "inputs": {
            "text": "text, watermark",
            "clip": [
                "4",
                1
            ]
        },
        "class_type": "CLIPTextEncode",
        "_meta": {
            "title": "CLIP Text Encode (Prompt)"
        }
    },
    "8": {
        "inputs": {
            "samples": [
                "3",
                0
            ],
            "vae": [
                "4",
                2
            ]
        },
        "class_type": "VAEDecode",
        "_meta": {
            "title": "VAE Decode"
        }
    },
    "9": {
        "inputs": {
            "filename_prefix": "nb_comfyui/txt2img/txt2img",
            "images": [
                "8",
                0
            ]
        },
        "class_type": "SaveImage",
        "_meta": {
            "title": "Save Image"
        }
    }
}

# 调用函数替换节点
updated_json = replace_lora_nodes(input_string, base_json)

# 打印更新后的工作流 JSON 数据
print(json.dumps(updated_json, indent=4))