import re
import json
import requests


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


def insert_lora_nodes(workflow, lora_dict, placeholder_index):
    if not lora_dict:
        return workflow

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

    all_nodes = list(workflow.items())
    new_workflow = {}
    id_mapping = {}
    lora_start_index = int(placeholder_index)

    # 插入 LoRA 节点
    for i, lora_node in enumerate(lora_nodes):
        new_id = str(lora_start_index + i)
        new_workflow[new_id] = lora_node
        id_mapping[str(lora_start_index + i)] = new_id

    # 处理原有的节点
    for node_id, node in all_nodes:
        if node_id == placeholder_index:
            continue
        new_id = str(int(node_id) + len(lora_nodes) if int(node_id) > lora_start_index else node_id)
        id_mapping[node_id] = new_id
        new_workflow[new_id] = node

    def update_dependencies(node, prev_model_id=None, prev_clip_id=None):
        for input_key, input_value in node.get("inputs", {}).items():
            if isinstance(input_value, list) and len(input_value) > 0 and isinstance(input_value[0], str):
                if input_value[0] == "placeholder":
                    if input_key == "model":
                        input_value[0] = prev_model_id if prev_model_id else id_mapping[str(int(placeholder_index) - 1)]
                    elif input_key == "clip":
                        input_value[0] = prev_clip_id if prev_clip_id else id_mapping[str(int(placeholder_index) - 1)]
                elif input_value[0] in id_mapping:
                    input_value[0] = id_mapping[input_value[0]]
            elif isinstance(input_value, dict):
                update_dependencies(input_value, prev_model_id, prev_clip_id)
            elif isinstance(input_value, list):
                for sub_value in input_value:
                    if isinstance(sub_value, dict):
                        update_dependencies(sub_value, prev_model_id, prev_clip_id)

    lora_groups = sorted([k for k in new_workflow.keys() if int(k) >= lora_start_index])
    prev_model_id = id_mapping[str(int(placeholder_index) - 1)]
    prev_clip_id = id_mapping[str(int(placeholder_index) - 1)]
    for node_id in lora_groups:
        node = new_workflow[node_id]
        update_dependencies(node, prev_model_id, prev_clip_id)
        prev_model_id = node_id
        prev_clip_id = node_id

    for node_id, node in new_workflow.items():
        if int(node_id) < lora_start_index:
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
        # 从 API JSON 中提取 <loras> 信息
        workflow = pseudo_api_workflow["prompt"]
        placeholder_index = workflow.pop("<loras>", None)

        lora_info = extract_lora_info(input_text)
        prompt_text = remove_lora_placeholders(input_text)

        if placeholder_index:
            workflow = insert_lora_nodes(workflow, lora_info, placeholder_index)
        workflow = replace_prompt(workflow, prompt_text)

        # 验证工作流格式
        for node_id, node in workflow.items():
            if "inputs" not in node or "class_type" not in node:
                raise ValueError(f"节点 {node_id} 格式错误，缺少 'inputs' 或 'class_type'")
            for input_key, input_value in node["inputs"].items():
                if isinstance(input_value, list) and len(input_value) > 1:
                    dep_id = input_value[0]
                    if dep_id not in workflow:
                        print(f"节点 {node_id} 的输入 {input_key} 依赖不存在的节点 {dep_id}")
                        raise ValueError(f"节点 {node_id} 的输入 {input_key} 依赖不存在的节点 {dep_id}")

        return {"prompt": workflow}
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

api_workflow = "api_workflow.json"
with open(api_workflow, "r", encoding="utf-8") as f:
    pseudo_api_workflow = json.load(f)

# 处理工作流
processed_workflow = process_workflow(input_text, pseudo_api_workflow)

if processed_workflow:
    print("处理后的 API 工作流:")
    print(json.dumps(processed_workflow, indent=4))
