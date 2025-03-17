import re
import json


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
        return {k: v for k, v in workflow.items() if k != "<loras>"}

    lora_nodes = []
    for lora_name, lora_weight in lora_dict.items():
        lora_nodes.append({
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["placeholder", 0],
                "clip": ["placeholder", 1],
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

    total_nodes = all_nodes
    for idx in reversed(lora_placeholder_indices):
        total_nodes = (
            total_nodes[:idx] +
            [(f"lora_{idx+1}_{i+1}", node.copy()) for i, node in enumerate(lora_nodes)] +
            total_nodes[idx:]
        )

    new_workflow = {}
    id_mapping = {}
    new_id = 1
    for old_id, node in total_nodes:
        str_new_id = str(new_id)
        id_mapping[old_id] = str_new_id
        new_workflow[str_new_id] = node
        new_id += 1

    def update_dependencies(node, prev_model_id="1", prev_clip_id="1"):
        for input_key, input_value in node.get("inputs", {}).items():
            if isinstance(input_value, list) and len(input_value) > 0 and isinstance(input_value[0], str):
                if input_value[0] == "placeholder":
                    if input_key == "model":
                        input_value[0] = prev_model_id
                    elif input_key == "clip":
                        input_value[0] = prev_clip_id
                elif input_value[0] in id_mapping:
                    input_value[0] = id_mapping[input_value[0]]
            elif isinstance(input_value, dict):
                update_dependencies(input_value, prev_model_id, prev_clip_id)
            elif isinstance(input_value, list):
                for sub_value in input_value:
                    if isinstance(sub_value, dict):
                        update_dependencies(sub_value, prev_model_id, prev_clip_id)

    lora_groups = sorted([k for k in new_workflow.keys() if k.startswith("lora_")])
    prev_model_id = "1"
    prev_clip_id = "1"
    for node_id in lora_groups:
        node = new_workflow[node_id]
        update_dependencies(node, prev_model_id, prev_clip_id)
        prev_model_id = node_id
        prev_clip_id = node_id

    for node_id, node in new_workflow.items():
        if not node_id.startswith("lora_"):
            update_dependencies(node, prev_model_id, prev_clip_id)

    return new_workflow


def replace_prompt(workflow, prompt_text):
    def replace_in_dict(obj):
        if isinstance(obj, dict):
            return {k: replace_in_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_in_dict(item) for item in obj]
        elif isinstance(obj, str) and obj == "<prompt>":
            return prompt_text
        return obj

    return replace_in_dict(workflow)


def process_workflow(input_text, pseudo_api_workflow):
    try:
        # 兼容 JSON 格式，确保 <loras> 被正确解析
        pseudo_api_workflow = pseudo_api_workflow.replace('"<loras>",', '"<loras>": null,')
        workflow = json.loads(pseudo_api_workflow)

        lora_info = extract_lora_info(input_text)
        prompt_text = remove_lora_placeholders(input_text)

        workflow = insert_lora_nodes(workflow, lora_info)
        workflow = replace_prompt(workflow, prompt_text)

        # 验证工作流格式
        for node_id, node in workflow.items():
            if "inputs" not in node or "class_type" not in node:
                raise ValueError(f"节点 {node_id} 格式错误，缺少 'inputs' 或 'class_type'")
            for input_key, input_value in node["inputs"].items():
                if isinstance(input_value, list) and len(input_value) > 1:
                    dep_id = input_value[0]
                    if dep_id not in workflow:
                        raise ValueError(f"节点 {node_id} 的输入 {input_key} 依赖不存在的节点 {dep_id}")

        return workflow
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        return None
    except ValueError as e:
        print(f"工作流验证错误: {e}")
        return None
    except Exception as e:
        print(f"处理工作流时出现错误: {e}")
        return None


# 示例输入文本
input_text = '<lora:a:0.8>,<lora:b:1.2>,<lora:c-123:1.1>,1girl'

# 修改后的伪 API 工作流模板
pseudo_api_workflow = '''
{
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "dreamshaper_8.safetensors"
        }
    },
    "<loras>": null,
    "3": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "<prompt>",
            "clip": ["1", 1]
        }
    },
    "<loras>": null,
    "4": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["1", 0],
            "positive": ["3", 0],
            "negative": ["3", 0],
            "latent_image": ["5", 0],
            "steps": 20,
            "cfg": 7,
            "sampler_name": "euler",
            "scheduler": "normal"
        }
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": 512,
            "height": 512,
            "batch_size": 1
        }
    }
}
'''

# 处理工作流
processed_workflow = process_workflow(input_text, pseudo_api_workflow)

if processed_workflow:
    print("处理后的 API 工作流:")
    print(json.dumps(processed_workflow, indent=4))

# 示例 API 请求代码
import requests

def submit_workflow(workflow, server_address="127.0.0.1:8188"):
    api_endpoint = f"http://{server_address}/prompt"
    response = requests.post(api_endpoint, json={"prompt": workflow})
    if response.status_code == 200:
        print("API 请求成功:", response.json())
    else:
        print("API 请求失败:", response.text)

if processed_workflow:
    submit_workflow(processed_workflow)
