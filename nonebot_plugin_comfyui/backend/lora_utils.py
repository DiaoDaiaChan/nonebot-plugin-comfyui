import re
import json
import asyncio
import aiohttp


async def replace_lora_nodes(input_string, base_json, url):
    # 正则表达式用于匹配 <lora:name:weight> 或 <nodename:name:weight> 格式
    lora_pattern = r'<([^:]+):([^:]+):([^>]+)>'
    lora_matches = re.findall(lora_pattern, input_string)
    lora_info = [(node_type, name, float(weight)) for node_type, name, weight in lora_matches]
    input_node_types = set([node_type for node_type, _, _ in lora_info])
    print("lora_matches:", lora_matches)
    print("lora_info:", lora_info)
    print("input_node_types:", input_node_types)

    # 找出原 JSON 中所有节点类型
    existing_node_types = set()
    for id, node in base_json.items():
        existing_node_types.add(node["class_type"])
    print("existing_node_types:", existing_node_types)

    # 只有当 base_json 中存在 LoraLoader 节点时，才处理输入字符串中没有但原 JSON 中有的节点
    if "LoraLoader" in existing_node_types:
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
                print(f"移除节点 {node_id} 并更新连接")

    # 过滤掉在 base_json 中不存在的节点类型，这里修改为只要是 lora 类型就保留
    valid_lora_info = []
    for node_type, name, weight in lora_info:
        if node_type == "lora" or node_type == "LoraLoader":
            valid_lora_info.append((node_type, name, weight))
    print("valid_lora_info:", valid_lora_info)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{url}/object_info/LoraLoader") as response:
                response.raise_for_status()
                lora_loader_info = await response.json()
                available_loras = []
                for sublist in lora_loader_info.get("LoraLoader", {}).get("input", {}).get("required", {}).get("lora_name", []):
                    for item in sublist:
                        if ".safetensors" in item:
                            available_loras.append(item.split('.')[0])
            print("available_loras:", available_loras)
        except aiohttp.ClientError as e:
            print(f"请求错误: {e}")
            available_loras = []

    if "LoraLoader" in existing_node_types:
        # 移除原有的 LoraLoader 节点
        lora_node_ids = []
        for id, node in base_json.items():
            if node["class_type"] == "LoraLoader":
                lora_node_ids.append(id)
        for id in lora_node_ids:
            del base_json[id]
            print(f"移除节点 {id}")

        # 找到 CheckpointLoaderSimple 节点作为起始节点
        start_node_output = None
        for id, node in base_json.items():
            if node["class_type"] == "CheckpointLoaderSimple":
                start_node_output = [id, 0]
                break

        if not start_node_output:
            raise ValueError("Could not find a CheckpointLoaderSimple node.")

        prev_node_output = start_node_output
        # 开始添加新的指定类型节点
        next_node_id_to_use = max(int(id) for id in base_json.keys()) + 1
        for _, name, weight in valid_lora_info:
            if name in available_loras:
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
                print(f"准备添加新节点 {next_node_id_to_use}: {new_node}")
                base_json[str(next_node_id_to_use)] = new_node
                prev_node_output = [str(next_node_id_to_use), 0]
                next_node_id_to_use += 1

        # 更新 VAEDecode 节点的输入
        for id, node in base_json.items():
            if node["class_type"] == "VAEDecode":
                node["inputs"]["samples"] = prev_node_output
                print(f"将 VAEDecode 节点 {id} 的 samples 输入更新为 {prev_node_output}")
                break

    return base_json


# 示例输入字符串，包含多个不同类型的标签
input_string = "<lora:lora1:0.7> <customnode:custom1:0.8><lora:mordred-pdxl-nvwls-v1:0.4> <lora:lora3:0.9> <nonexistent:test:0.5> <lora:chenbin-000010:0.6><lora:chenbin-000015:0.6>"

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
                "10",
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
                0
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
                "10",
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
    },
    "10": {
        "inputs": {
            "lora_name": "chenbin-000005.safetensors",
            "strength_model": 1,
            "strength_clip": 1,
            "model": [
                "4",
                0
            ],
            "clip": [
                "4",
                1
            ]
        },
        "class_type": "LoraLoader",
        "_meta": {
            "title": "Load LoRA"
        }
    }
}

# 假设的 url
url = "http://example.com"

# 调用函数替换节点
updated_json = asyncio.run(replace_lora_nodes(input_string, base_json, url))

# 打印更新后的工作流 JSON 数据
print(json.dumps(updated_json, indent=4))
