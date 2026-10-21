# comfyui-reflex

> 零三方依赖 (Zero Dependencies) 的纯 Python 标准库，专用于高效改写、解析、检查与重构 **ComfyUI API 工作流**。

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)]()

---

## 🌟 核心特性

- **纯标准库实现**：零外部依赖，极速安装，可无缝嵌入任何 Web 框架（FastAPI、Flask、Django）、云函数或脚本工具。
- **面向对象流式操作 (`ComfyWorkflow`)**：通过直观的链式调用轻松修改提示词、负向词、采样参数、随机种子、图像分辨率与模型。
- **PNG 图像工作流提取**：内置纯标准库解析器，支持直接从 ComfyUI 输出的 PNG 图像中无损提取 Prompt API JSON 和 WebUI 工作流。
- **自动 LoRA 图拓扑重构**：内置 LoRA 语法解析器与节点链重构器，自动识别下游节点并串联 `LoraLoader`。
- **声明式 Reflex 规则引擎**：支持基于映射配置改写工作流，提供 `randint`、`upscale`、`append_prompt`、`replace_prompt`、`value`、`image` 等高级动作及多后端动态适配。
- **高阶分辨率计算**：支持预设形制 (`p`/`l`/`s`)、WxH 字符串与宽高比算力基准换算。
- **完整类型提示**：配备 PEP 561 `py.typed`，支持 mypy 与 pyright 静态检查。

---

## 📦 安装

```bash
pip install comfyui-reflex
```

---

## 🚀 快速上手

### 1. 链式改写 ComfyUI 工作流

```python
from comfyui_reflex import ComfyWorkflow

# 从 JSON 文件或 ComfyUI 生成的 PNG 图片加载
wf = ComfyWorkflow.load("workflow.json")
# 或者直接从图片反解:
# wf = ComfyWorkflow.from_image("ComfyUI_00001_.png")

# 链式改写常用参数
wf.set_prompt("1girl, cyber city, neon lighting, 8k masterpiece") \
  .set_negative_prompt("blurry, low quality, bad anatomy") \
  .set_seed(123456) \
  .set_dimensions(width=832, height=1216) \
  .set_sampler(steps=28, cfg=7.0, sampler_name="Euler a", scheduler="karras") \
  .inject_lora("detail_slider.safetensors", strength_model=0.8)

# 构造直接发送至 ComfyUI HTTP /prompt 接口的 payload
payload = wf.to_prompt_payload(client_id="my_client_123")

# 保存修改后的工作流
wf.save("workflow_modified.json")
```

### 2. 纯标准库 PNG 元数据提取

```python
from comfyui_reflex import extract_prompt_from_png, extract_comfyui_metadata_from_png

# 提取 ComfyUI API Prompt (可直接转为 ComfyWorkflow)
prompt_dict = extract_prompt_from_png("output.png")

# 提取全部元数据 (包含 prompt 与 webui workflow)
metadata = extract_comfyui_metadata_from_png("output.png")
print("Prompt 节点数:", len(metadata.get("prompt", {})))
```

### 3. LoRA 提取与节点链自动注入

```python
from comfyui_reflex import extract_loras_from_prompt, ComfyWorkflow

raw_prompt = "1girl, <lora:add_detail:0.8>, solo, <lora:flat_color:0.5>"
clean_prompt, loras = extract_loras_from_prompt(raw_prompt)
# clean_prompt: "1girl, solo"
# loras: [("add_detail", 0.8), ("flat_color", 0.5)]

wf = ComfyWorkflow.load("workflow.json")
wf.set_prompt(clean_prompt).inject_loras(loras)
```

### 4. 声明式 Reflex 规则改写

```python
from comfyui_reflex import ComfyWorkflow, ReflexConfig

wf = ComfyWorkflow.load("workflow.json")
reflex = ReflexConfig.from_file("workflow_reflex.json")

wf.apply_reflex(
    reflex=reflex,
    params={
        "prompt": "masterpiece, 1girl",
        "negative_prompt": "low quality",
        "width": 1024,
        "height": 1024,
        "seed": 42,
        "sampler": "Euler a",
        "scheduler": "karras",
        "steps": 30,
        "cfg_scale": 6.5
    }
)
```

---

## 🛠️ 模块体系

| 模块 | 核心导出 | 功能简述 |
| :--- | :--- | :--- |
| `comfyui_reflex.workflow` | `ComfyWorkflow` | 面向对象的工作流容器，支持流式改写、节点查找、连线与序列化 |
| `comfyui_reflex.models` | `ComfyNode`, `ReflexConfig` | 节点对象封装与 Reflex 映射规则协议模型 |
| `comfyui_reflex.png` | `extract_prompt_from_png` 等 | 纯标准库读取 PNG 图像中的 `tEXt` / `iTXt` 块提取工作流 |
| `comfyui_reflex.lora` | `extract_loras_from_prompt` 等 | 提示词 LoRA 标记提取与图内动态拓扑链式插入 |
| `comfyui_reflex.dimensions`| `calculate_dimensions` | 形制与比例分辨率自适应运算 |
| `comfyui_reflex.engine` | `ReflexEngine` | 声明式规则应用与高级动作执行（`randint`、`upscale`、`reg_args` 等）|
| `comfyui_reflex.loader` | `WorkflowLoader` | 同步与异步工作流文件成对扫描与加载 |

---

## 📄 License

MIT
