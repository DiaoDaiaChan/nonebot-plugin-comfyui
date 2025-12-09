import aiohttp
import re
import json
import asyncio
from typing import Dict, Tuple, Optional, List


async def process_workflow(input_string: str, base_json: dict, url: str) -> dict:
    # 深拷贝 base_json
    workflow = json.loads(json.dumps(base_json))
    
    # 正则表达式匹配 <class_type:name:value>
    pattern = r"<([^:]+):([^:]+):([^>]+)>"
    matches = re.findall(pattern, input_string)
    
    # 获取 base_json 中存在的 class_type
    existing_class_types = {node["class_type"] for node in base_json.values()}
    if "LoraLoader" in existing_class_types:
        existing_class_types.add("lora")
    
    # 获取所有可用的 LoRA
    available_loras = await get_available_loras(url)
    
    # 记录原有 LoraLoader 节点的位置
    original_lora_positions = {node_id: node for node_id, node in base_json.items() if node["class_type"] == "LoraLoader"}
    
    # 默认删除所有 LoraLoader 节点并调整连接
    workflow = remove_lora_nodes(workflow, base_json)
    
    # 处理 LoRA 的新节点
    lora_matches = [m for m in matches if m[0].lower() in ["lora", "loraloader"]]
    new_lora_nodes = []
    
    if lora_matches:
        for i, (class_type, name, value) in enumerate(lora_matches):
            lora_name = name if name in available_loras else None
            if lora_name:
                try:
                    value = float(value)
                except ValueError:
                    value = 1.0
                # 使用原有位置或创建新节点
                if i < len(original_lora_positions):
                    node_id = list(original_lora_positions.keys())[i]
                    workflow[node_id] = {
                        "class_type": "LoraLoader",
                        "inputs": {
                            "lora_name": f"{lora_name}.safetensors",
                            "strength_model": value,
                            "strength_clip": value,
                            "model": [None, 0],
                            "clip": [None, 1]
                        },
                        "_meta": {"title": "Load LoRA"}
                    }
                else:
                    node_id = str(max([int(k) for k in workflow.keys()] + [0]) + 1)
                    workflow[node_id] = {
                        "class_type": "LoraLoader",
                        "inputs": {
                            "lora_name": f"{lora_name}.safetensors",
                            "strength_model": value,
                            "strength_clip": value,
                            "model": [None, 0],
                            "clip": [None, 1]
                        },
                        "_meta": {"title": "Load LoRA"}
                    }
                new_lora_nodes.append((workflow[node_id], node_id))
    
    # 插入并串联 LoRA 节点
    if new_lora_nodes:
        insert_lora_nodes(workflow, new_lora_nodes, base_json, original_lora_positions)
    
    # 处理其他类型节点
    for class_type, name, value in matches:
        normalized_class_type = "LoraLoader" if class_type.lower() == "lora" else class_type
        if normalized_class_type not in existing_class_types or class_type.lower() in ["lora", "loraloader"]:
            continue
        try:
            value = float(value)
        except ValueError:
            pass
        node, node_id = find_or_create_node(workflow, class_type, base_json)
        update_node_inputs(node, name, value)
        if node_id not in base_json:
            insert_node(workflow, node_id, class_type, base_json)
    
    return workflow

async def get_available_loras(url: str) -> list:
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
                return available_loras
        except aiohttp.ClientError as e:
            print(f"请求错误: {e}")
            return []

def find_or_create_node(workflow: dict, class_type: str, base_json: dict) -> Tuple[dict, str]:
    for node_id, node in base_json.items():
        if node.get("class_type") == class_type:
            return workflow[node_id], node_id
    new_node_id = str(max([int(k) for k in workflow.keys()] + [0]) + 1)
    workflow[new_node_id] = {
        "class_type": class_type,
        "inputs": {},
        "_meta": {"title": class_type}
    }
    return workflow[new_node_id], new_node_id

def update_node_inputs(node: dict, name: str, value: any):
    class_type = node["class_type"]
    
    if class_type == "CLIPTextEncode":
        node["inputs"]["text"] = name
    
    elif class_type == "KSampler":
        if name in ["seed", "steps", "cfg", "denoise"]:
            node["inputs"][name] = value if isinstance(value, (int, float)) else int(value)
    
    elif class_type == "CheckpointLoaderSimple":
        node["inputs"]["ckpt_name"] = f"{name}.safetensors"
    
    elif class_type == "EmptyLatentImage":
        if name in ["width", "height", "batch_size"]:
            node["inputs"][name] = int(value)
    
    elif class_type == "VAEDecode":
        pass
    
    elif class_type == "SaveImage":
        node["inputs"]["filename_prefix"] = name

def remove_lora_nodes(workflow: dict, base_json: dict) -> dict:
    lora_nodes = {node_id: node for node_id, node in base_json.items() if node["class_type"] == "LoraLoader"}
    
    for lora_id in lora_nodes:
        upstream_model = lora_nodes[lora_id]["inputs"].get("model", [None, 0])
        upstream_clip = lora_nodes[lora_id]["inputs"].get("clip", [None, 1])
        
        for node_id, node in workflow.items():
            for input_key, connection in node["inputs"].items():
                if isinstance(connection, list) and connection[0] == lora_id:
                    if input_key == "model":
                        node["inputs"][input_key] = upstream_model
                    elif input_key == "clip":
                        node["inputs"][input_key] = upstream_clip
        
        workflow.pop(lora_id)
    
    return workflow

def insert_lora_nodes(workflow: dict, new_lora_nodes: List[Tuple[dict, str]], base_json: dict, original_lora_positions: dict):
    # 串联 LoRA 节点
    if len(new_lora_nodes) > 1:
        for i in range(len(new_lora_nodes) - 1):
            _, current_id = new_lora_nodes[i]
            next_node, next_id = new_lora_nodes[i + 1]
            next_node["inputs"]["model"] = [current_id, 0]
            next_node["inputs"]["clip"] = [current_id, 1]
    
    # 第一个 LoRA 连接到原有上游
    first_node, first_id = new_lora_nodes[0]
    for orig_id in original_lora_positions:
        first_node["inputs"]["model"] = original_lora_positions[orig_id]["inputs"].get("model", [None, 0])
        first_node["inputs"]["clip"] = original_lora_positions[orig_id]["inputs"].get("clip", [None, 1])
        break
    
    # 最后一个 LoRA 连接到原有下游
    last_node, last_id = new_lora_nodes[-1]
    for orig_id in original_lora_positions:
        for node_id, node in base_json.items():
            for input_key, connection in node["inputs"].items():
                if isinstance(connection, list) and connection[0] == orig_id:
                    if node_id in workflow and input_key in workflow[node_id]["inputs"]:
                        workflow[node_id]["inputs"][input_key] = [last_id, connection[1]]

def insert_node(workflow: dict, node_id: str, class_type: str, base_json: dict):
    source_connections = {}
    target_connections = []
    
    for orig_id, orig_node in base_json.items():
        if orig_node["class_type"] == class_type:
            for input_key, connection in orig_node["inputs"].items():
                if isinstance(connection, list) and connection[0] in base_json:
                    source_connections[input_key] = (connection[0], connection[1])
        for input_key, connection in orig_node["inputs"].items():
            if isinstance(connection, list) and connection[0] in base_json and base_json[connection[0]]["class_type"] == class_type:
                target_connections.append((orig_id, input_key, connection[1]))
    
    for input_key, (source_id, output_idx) in source_connections.items():
        if input_key not in workflow[node_id]["inputs"]:
            workflow[node_id]["inputs"][input_key] = [source_id, output_idx]
    
    for target_id, input_key, output_idx in target_connections:
        if target_id in workflow and input_key in workflow[target_id]["inputs"]:
            workflow[target_id]["inputs"][input_key] = [node_id, output_idx]
#
# # 测试代码
# async def main():
#     base_json = {
#         "3": {"inputs": {"seed": 363272565452302, "steps": 20, "cfg": 8, "sampler_name": "euler", "scheduler": "normal", "denoise": 1, "model": ["10", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}, "class_type": "KSampler", "_meta": {"title": "KSampler"}},
#         "4": {"inputs": {"ckpt_name": "NoobXL-EPS-v1.1.safetensors"}, "class_type": "CheckpointLoaderSimple", "_meta": {"title": "Load Checkpoint"}},
#         "5": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}, "class_type": "EmptyLatentImage", "_meta": {"title": "Empty Latent Image"}},
#         "6": {"inputs": {"text": "beautiful scenery", "clip": ["10", 1]}, "class_type": "CLIPTextEncode", "_meta": {"title": "CLIP Text Encode (Prompt)"}},
#         "7": {"inputs": {"text": "text, watermark", "clip": ["10", 1]}, "class_type": "CLIPTextEncode", "_meta": {"title": "CLIP Text Encode (Prompt)"}},
#         "8": {"inputs": {"samples": ["3", 0], "vae": ["4", 2]}, "class_type": "VAEDecode", "_meta": {"title": "VAE Decode"}},
#         "9": {"inputs": {"filename_prefix": "nb_comfyui/txt2img/txt2img", "images": ["8", 0]}, "class_type": "SaveImage", "_meta": {"title": "Save Image"}},
#         "10": {"inputs": {"lora_name": "chenbin-000005.safetensors", "strength_model": 1, "strength_clip": 1, "model": ["4", 0], "clip": ["4", 1]}, "class_type": "LoraLoader", "_meta": {"title": "Load LoRA"}}
#     }
#
#     input_string = "New prompt <lora:nikki:0.8> <lora:invalid_lora:0.6> <lora:chenbin-000005:0.7> <CLIPTextEncode:amazing landscape:1.0> <KSampler:seed:12345>"
#     url = "http://server2.20020026.xyz:58288"
#
#     result = await process_workflow(input_string, base_json, url)
#     print(json.dumps(result, indent=2))
#
# if __name__ == "__main__":
#     asyncio.run(main())
