import re
import json

def replace_lora_nodes(input_string, base_json):
    # 正则表达式用于匹配 <lora:name:weight> 或 <nodename:name:weight> 格式
    lora_pattern = r'<([^:]+):([^:]+):([^>]+)>'
    lora_matches = re.findall(lora_pattern, input_string)
    lora_info = [(node_type, name, float(weight)) for node_type, name, weight in lora_matches]

    for node_type, _, _ in lora_info:
        # 找出原有的指定类型节点及其前后连接的节点
        node_id = None
        prev_node_output = None
        next_node_id = None
        next_node_input_key = None

        for id, node in base_json["prompt"].items():
            if node["class_type"] == node_type:
                node_id = id
                # 找到前一个节点的输出
                if "model" in node["inputs"]:
                    prev_node_output = node["inputs"]["model"]
                # 查找连接到这个节点输出的下一个节点
                for next_id, next_node in base_json["prompt"].items():
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
            del base_json["prompt"][node_id]

        # 如果没有找到前一个节点的输出，尝试默认从 CheckpointLoaderSimple 节点开始
        if not prev_node_output:
            for id, node in base_json["prompt"].items():
                if node["class_type"] == "CheckpointLoaderSimple":
                    prev_node_output = [id, 0]
                    break

        if not prev_node_output:
            raise ValueError(f"Could not find a valid starting node for {node_type}.")

        # 开始添加新的指定类型节点
        next_node_id_to_use = max(int(id) for id in base_json["prompt"].keys()) + 1
        for _, name, weight in lora_info:
            if node_type == "LoraLoader" or node_type == "lora":
                new_node = {
                    "class_type": "LoraLoader",
                    "inputs": {
                        "model": prev_node_output,
                        "lora_name": f"{name}.safetensors",
                        "strength_model": weight,
                        "strength_clip": weight
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
                    }
                }
            base_json["prompt"][str(next_node_id_to_use)] = new_node
            # 更新下一个节点的输入模型
            prev_node_output = [str(next_node_id_to_use), 0]
            next_node_id_to_use += 1

        # 如果找到后续连接的节点，更新其输入
        if next_node_id and next_node_input_key:
            base_json["prompt"][next_node_id]["inputs"][next_node_input_key] = prev_node_output
        else:
            # 如果没有找到后续连接节点，假设是连接到 KSampler 节点
            for id, node in base_json["prompt"].items():
                if node["class_type"] == "KSampler":
                    node["inputs"]["model"] = prev_node_output
                    break

    return base_json

# 示例输入字符串，包含多个不同类型的标签
input_string = "<lora:lora1:0.7> <customnode:custom1:0.8> <lora:lora3:0.9>"

# 示例的 ComfyUI 基础工作流 JSON 数据，包含一个 LoRA 节点
base_json = {
    "prompt": {
        "1": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["3", 0],
                "seed": 12345,
                "steps": 20,
                "cfg": 7,
                "sampler_name": "euler",
                "scheduler": "normal",
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0]
            }
        },
        "2": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "v1-5-pruned-emaonly.ckpt"
            }
        },
        "3": {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["2", 0],
                "lora_name": "old_lora.safetensors",
                "strength_model": 0.5,
                "strength_clip": 0.5
            }
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "A beautiful scene",
                "clip": ["2", 1]
            }
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "ugly, blurry",
                "clip": ["2", 1]
            }
        },
        "6": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": 512,
                "height": 512,
                "batch_size": 1
            }
        },
        "7": {
            "class_type": "VAEDecode",
            "inputs": {
                "vae": ["2", 2],
                "samples": ["1", 0]
            }
        },
        "8": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["7", 0]
            }
        }
    },
    "client_id": "example_client_id"
}

# 调用函数替换节点
updated_json = replace_lora_nodes(input_string, base_json)

# 打印更新后的工作流 JSON 数据
print(json.dumps(updated_json, indent=4))

'''
下面的未测试，输入提示词类似beautiful,1girl<lora:name0:weight> --nodename1 <lora:name1:weight>,<lora:name2:weight> --nodename2 <lora:name3:weight>,<lora:name4:weight>这种
import re

def replace_lora_nodes(input_string, base_json):
    # 正则表达式用于匹配 <lora:name:weight> 和 --nodename 格式
    lora_pattern = r'<lora:([^:]+):([^>]+)>'
    node_pattern = r'--([^\s<]+)'

    # 提取所有的 lora 信息和节点名称
    lora_matches = re.findall(lora_pattern, input_string)
    node_matches = re.findall(node_pattern, input_string)

    # 初始化节点名称列表，如果没有匹配到节点名称，默认使用 'LoraLoader'
    node_names = node_matches if node_matches else ['LoraLoader']

    # 依次处理每个节点名称对应的 lora 信息
    lora_index = 0
    for node_name in node_names:
        # 找出原有的指定类型节点及其前后连接的节点
        target_node_id = None
        prev_node_output = None
        next_node_id = None
        next_node_input_key = None

        for node_id, node in base_json["prompt"].items():
            if node["class_type"] == node_name:
                target_node_id = node_id
                # 找到前一个节点的输出
                for input_key, input_value in node["inputs"].items():
                    if isinstance(input_value, list):
                        prev_node_output = input_value
                        break
                # 查找连接到这个节点输出的下一个节点
                for next_id, next_node in base_json["prompt"].items():
                    for input_key, input_value in next_node["inputs"].items():
                        if isinstance(input_value, list) and input_value[0] == target_node_id:
                            next_node_id = next_id
                            next_node_input_key = input_key
                            break
                    if next_node_id:
                        break
                break

        # 如果找到原有的指定类型节点，移除它
        if target_node_id:
            del base_json["prompt"][target_node_id]

        # 计算当前节点名称对应的 lora 信息范围
        next_node_index = len(node_names) - 1 if node_names.index(node_name) == len(node_names) - 1 else node_names.index(node_name) + 1
        next_node_match_index = input_string.find(f"--{node_names[next_node_index]}") if next_node_index < len(node_names) else len(input_string)
        current_lora_matches = []
        while lora_index < len(lora_matches) and input_string.find(f"<lora:{lora_matches[lora_index][0]}:{lora_matches[lora_index][1]}>") < next_node_match_index:
            current_lora_matches.append(lora_matches[lora_index])
            lora_index += 1

        # 如果没有找到前一个节点的输出，尝试默认从 CheckpointLoaderSimple 节点开始
        if not prev_node_output:
            for node_id, node in base_json["prompt"].items():
                if node["class_type"] == "CheckpointLoaderSimple":
                    prev_node_output = [node_id, 0]
                    break

        if not prev_node_output:
            raise ValueError("Could not find a valid starting node for LoRA.")

        # 开始添加新的 LoRA 节点
        next_node_id_to_use = max(int(id) for id in base_json["prompt"].keys()) + 1
        for name, weight in current_lora_matches:
            lora_node = {
                "class_type": "LoraLoader",
                "inputs": {
                    "model": prev_node_output,
                    "lora_name": f"{name}.safetensors",
                    "strength_model": weight,
                    "strength_clip": weight
                }
            }
            base_json["prompt"][str(next_node_id_to_use)] = lora_node
            # 更新下一个 LoRA 节点的输入模型
            prev_node_output = [str(next_node_id_to_use), 0]
            next_node_id_to_use += 1

        # 如果找到后续连接的节点，更新其输入
        if next_node_id and next_node_input_key:
            base_json["prompt"][next_node_id]["inputs"][next_node_input_key] = prev_node_output
        else:
            # 如果没有找到后续连接节点，假设是连接到 KSampler 节点
            for node_id, node in base_json["prompt"].items():
                if node["class_type"] == "KSampler":
                    node["inputs"]["model"] = prev_node_output
                    break

    return base_json
'''
