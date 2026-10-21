"""
Unit tests for comfyui_reflex standalone library:
Pure Python, zero-dependency ComfyUI API workflow manipulation and rewriting engine.
"""

import copy
import json
import struct
import zlib
from pathlib import Path
import pytest

# 1. 验证独立库导入（零框架依赖，无任何 NoneBot/第三方库依赖）
import comfyui_reflex
from comfyui_reflex import (
    ComfyWorkflow,
    ComfyNode,
    ReflexConfig,
    ReflexEngine,
    WorkflowLoader,
    calculate_dimensions,
    extract_loras_from_prompt,
    apply_loras_to_api_json,
    extract_prompt_from_png,
    extract_comfyui_metadata_from_png,
    read_png_text_chunks,
    MAX_SEED,
    SAMPLER_MAPPING,
    SCHEDULER_MAPPING,
    REFLEX_DICT
)
from comfyui_reflex.exceptions import (
    ReflexError,
    ReflexNotFoundError,
    ReflexConfigError,
    ReflexArgumentError,
    NodeNotFoundError,
    WorkflowFormatError
)


def create_minimal_test_png(text_chunks: dict[str, str]) -> bytes:
    """构造一个包含指定文本元数据块的最小合法 PNG 二进制数据"""
    signature = b"\x89PNG\r\n\x1a\n"
    
    # IHDR chunk
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    ihdr_chunk = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

    # tEXt chunks
    text_parts = []
    for k, v in text_chunks.items():
        chunk_data = k.encode("latin-1") + b"\x00" + v.encode("utf-8")
        crc = zlib.crc32(b"tEXt" + chunk_data)
        text_parts.append(struct.pack(">I", len(chunk_data)) + b"tEXt" + chunk_data + struct.pack(">I", crc))

    # IEND chunk
    iend_crc = zlib.crc32(b"IEND")
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

    return signature + ihdr_chunk + b"".join(text_parts) + iend_chunk


@pytest.fixture
def temp_dir():
    d = Path("./tests/.tmp_test_dir").resolve()
    d.mkdir(parents=True, exist_ok=True)
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


def test_standalone_exports():
    """验证顶层导出完整且版本号存在，且无任何机器人相关属性污染"""
    assert comfyui_reflex.__version__ == "0.1.0"
    assert MAX_SEED == 2 ** 31
    assert "Euler a" in SAMPLER_MAPPING
    assert "Karras" in SCHEDULER_MAPPING
    assert "sampler" in REFLEX_DICT
    assert issubclass(NodeNotFoundError, ReflexError)
    assert issubclass(WorkflowFormatError, ReflexError)


def test_calculate_dimensions():
    """测试分辨率与宽高比计算"""
    # 预设形制
    assert calculate_dimensions(shape="p") == (832, 1216)
    assert calculate_dimensions(shape="l") == (1216, 832)
    assert calculate_dimensions(shape="s") == (1024, 1024)

    # 自定义形制预设
    custom_presets = {"custom_portrait": (768, 1024)}
    assert calculate_dimensions(shape="custom_portrait", shape_presets=custom_presets) == (768, 1024)

    # 形制 WxH 字符串
    assert calculate_dimensions(shape="512x768") == (512, 768)

    # 宽高比比例计算
    w_16_9, h_16_9 = calculate_dimensions(accept_ratio="16:9", base_res=1024)
    assert w_16_9 > h_16_9
    assert abs(w_16_9 * h_16_9 - 1024 ** 2) < 5000

    w_9_16, h_9_16 = calculate_dimensions(accept_ratio="9:16", base_res=1024)
    assert w_9_16 < h_9_16

    # 默认值
    assert calculate_dimensions(default_width=640, default_height=960) == (640, 960)

    # 异常测试
    with pytest.raises(ReflexArgumentError):
        calculate_dimensions(accept_ratio="invalid_ratio")


def test_lora_parsing_and_injection():
    """测试 LoRA 提示词解析与节点图注入"""
    prompt = "masterpiece, 1girl, <lora:detail_tweaker:0.8>, solo, <lora:anime_style:0.5>, <lora:flat_color>"
    clean_prompt, loras = extract_loras_from_prompt(prompt)
    
    assert clean_prompt == "masterpiece, 1girl, solo"
    assert loras == [
        ("detail_tweaker", 0.8),
        ("anime_style", 0.5),
        ("flat_color", 1.0)
    ]

    raw_api = {
        "3": {
            "inputs": {
                "seed": 100,
                "model": ["4", 0],
                "clip": ["4", 1]
            },
            "class_type": "KSampler"
        },
        "4": {
            "inputs": {"ckpt_name": "v1-5.safetensors"},
            "class_type": "CheckpointLoaderSimple"
        }
    }

    # 注入单个 LoRA
    injected = apply_loras_to_api_json(raw_api, "4", [("my_lora", 0.75)])
    assert "4" in injected
    assert injected["4"]["inputs"]["lora_name"] == "my_lora"
    assert injected["4"]["inputs"]["strength_model"] == 0.75


def test_comfy_workflow_fluent_api():
    """测试 ComfyWorkflow 面向对象链式改写 API"""
    raw_api = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 10,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            },
            "_meta": {"title": "Main Sampler"}
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "v1-5.safetensors"}
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1}
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "default pos", "clip": ["4", 1]},
            "_meta": {"title": "positive prompt"}
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "default neg", "clip": ["4", 1]},
            "_meta": {"title": "negative prompt"}
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": "ComfyUI"}
        }
    }

    wf = ComfyWorkflow(raw_api)

    # 1. 基础查找与状态
    assert len(wf) == 6
    assert wf.has_node("3")
    assert wf["3"].class_type == "KSampler"
    assert wf["3"].title == "Main Sampler"
    assert len(wf.find_nodes_by_class("CLIPTextEncode")) == 2
    assert wf.find_first_by_title("Main Sampler") is not None
    assert len(wf.get_output_nodes()) == 1
    assert wf.get_output_nodes()[0].id == "9"

    # 2. 链式改写参数
    (
        wf.set_prompt("a beautiful cyber city, night, glowing neon")
          .set_negative_prompt("blurry, low quality")
          .set_seed(987654)
          .set_dimensions(width=832, height=1216, batch_size=2)
          .set_sampler(steps=25, cfg=6.5, sampler_name="Euler a", scheduler="karras", denoise=0.9)
          .set_checkpoint("dreamshaper_8.safetensors")
    )

    # 验证改写结果
    assert wf["6"].inputs["text"] == "a beautiful cyber city, night, glowing neon"
    assert wf["7"].inputs["text"] == "blurry, low quality"
    assert wf["3"].inputs["seed"] == 987654
    assert wf["3"].inputs["steps"] == 25
    assert wf["3"].inputs["cfg"] == 6.5
    assert wf["3"].inputs["sampler_name"] == "euler_ancestral"
    assert wf["3"].inputs["scheduler"] == "karras"
    assert wf["3"].inputs["denoise"] == 0.9
    assert wf["5"].inputs["width"] == 832
    assert wf["5"].inputs["height"] == 1216
    assert wf["5"].inputs["batch_size"] == 2
    assert wf["4"].inputs["ckpt_name"] == "dreamshaper_8.safetensors"

    # 3. 提示词追加与替换
    wf.append_prompt("8k wallpaper")
    assert wf["6"].inputs["text"] == "a beautiful cyber city, night, glowing neon, 8k wallpaper"

    # 4. Payload 生成
    payload = wf.to_prompt_payload(client_id="test_client_001")
    assert "prompt" in payload
    assert payload["client_id"] == "test_client_001"
    assert "3" in payload["prompt"]


def test_comfy_workflow_graph_manipulation():
    """测试工作流图节点的动态添加、删除与重连"""
    wf = ComfyWorkflow()
    assert len(wf) == 0

    # 动态添加节点
    node_clip = wf.add_node("1", "CLIPTextEncode", {"text": "hello"}, title="My Prompt")
    assert len(wf) == 1
    assert node_clip.title == "My Prompt"

    node_sampler = wf.add_node("2", "KSampler", {"seed": 0})
    assert len(wf) == 2

    # 连线 [1, 0] -> 2.inputs["positive"]
    wf.link(from_node="1", from_slot=0, to_node="2", to_input="positive")
    assert wf["2"].inputs["positive"] == ["1", 0]
    assert wf["2"].incoming_links()["positive"] == ("1", 0)

    # 断线
    wf.unlink(to_node="2", to_input="positive")
    assert "positive" not in wf["2"].inputs

    # 删除节点
    removed = wf.remove_node("1")
    assert removed is not None
    assert len(wf) == 1
    assert not wf.has_node("1")


def test_png_metadata_extraction(temp_dir: Path):
    """测试纯标准库 PNG 图片元数据提取与直接恢复为 ComfyWorkflow"""
    prompt_payload = {
        "3": {
            "class_type": "KSampler",
            "inputs": {"seed": 42, "steps": 20}
        }
    }
    webui_workflow = {"nodes": [{"id": 3, "type": "KSampler"}]}

    # 构造含 prompt 和 workflow 块的 PNG
    png_bytes = create_minimal_test_png({
        "prompt": json.dumps(prompt_payload),
        "workflow": json.dumps(webui_workflow),
        "extra_info": "comfyui generated image"
    })

    test_png_path = temp_dir / "sample_comfy.png"
    test_png_path.write_bytes(png_bytes)

    # 1. 验证底层文本块读取
    chunks = read_png_text_chunks(test_png_path)
    assert "prompt" in chunks
    assert "workflow" in chunks
    assert chunks["extra_info"] == "comfyui generated image"

    # 2. 验证元数据解析
    meta = extract_comfyui_metadata_from_png(test_png_path)
    assert meta["prompt"]["3"]["inputs"]["seed"] == 42
    assert meta["workflow"]["nodes"][0]["type"] == "KSampler"

    # 3. 验证从 PNG 直接创建 ComfyWorkflow
    wf = ComfyWorkflow.from_image(test_png_path)
    assert wf.has_node("3")
    assert wf["3"].inputs["seed"] == 42

    # 链式改写后另存为 json
    wf.set_seed(12345)
    out_json = temp_dir / "extracted_modified.json"
    wf.save(out_json)
    
    reloaded = ComfyWorkflow.load(out_json)
    assert reloaded["3"].inputs["seed"] == 12345


def test_reflex_config_pure_model(temp_dir: Path):
    """测试纯工作流 ReflexConfig 模型封装（无任何机器人概念）"""
    raw_dict = {
        "output": ["9", "12"],
        "media": "image",
        "output_prefix": "MyBotOutput",
        "note": "高质量通用文生图工作流",
        "presets": {"portrait": [832, 1216]},
        "load_image": "15"
    }
    cfg = ReflexConfig(raw_dict)

    assert cfg.output_nodes == {"image": ["9", "12"]}
    assert cfg.all_output_node_ids == ["9", "12"]
    assert cfg.media_type == "image"
    assert cfg.output_prefix == "MyBotOutput"
    assert cfg.requires_image is True
    assert cfg.note == "高质量通用文生图工作流"
    assert cfg.presets == {"portrait": [832, 1216]}

    # Mapping 特性
    assert cfg["media"] == "image"
    assert "output" in cfg

    # 文件持久化测试
    cfg_path = temp_dir / "pure_reflex.json"
    cfg.save_to_file(cfg_path)
    loaded = ReflexConfig.from_file(cfg_path)
    assert loaded.all_output_node_ids == ["9", "12"]


def test_reflex_engine_advanced_apply():
    """测试 ReflexEngine 的高级覆盖规则 (randint, upscale, replace_prompt, value 等)"""
    raw_api = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 0,
                "steps": 20,
                "cfg": 8.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0]
            }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1}
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "default positive"}
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "default negative"}
        },
        "8": {
            "class_type": "CustomNode",
            "inputs": {
                "custom_int": 0,
                "prompt_slot": "{prompt}, cinematic lighting",
                "upscale_w": 512
            }
        }
    }

    reflex_cfg = {
        "sampler": "3",
        "image_size": "5",
        "prompt": "6",
        "negative_prompt": "7",
        "override": {
            "8": {
                "override": {
                    "custom_int": "value_99_int",
                    "prompt_slot": "replace_prompt",
                    "upscale_w": "upscale_1.5"
                }
            }
        }
    }

    wf = ComfyWorkflow(raw_api)
    wf.apply_reflex(
        reflex=reflex_cfg,
        params={
            "prompt": "1girl, sunset",
            "negative_prompt": "bad anatomy",
            "width": 800,
            "height": 1200,
            "seed": 777,
            "sampler": "Euler a",
            "scheduler": "karras",
            "steps": 28,
            "cfg_scale": 7.0
        }
    )

    assert wf["3"].inputs["seed"] == 777
    assert wf["3"].inputs["steps"] == 28
    assert wf["3"].inputs["sampler_name"] == "euler_ancestral"
    assert wf["6"].inputs["text"] == "1girl, sunset"
    assert wf["8"].inputs["custom_int"] == 99
    assert wf["8"].inputs["prompt_slot"] == "1girl, sunset, cinematic lighting"
    assert wf["8"].inputs["upscale_w"] == int(800 * 1.5)


def test_workflow_loader(temp_dir: Path):
    """测试工作流成对文件的查找与同步/异步加载"""
    wf_dir = temp_dir / "test_workflows"
    wf_dir.mkdir()

    (wf_dir / "txt2img.json").write_text(json.dumps({"1": {"class_type": "Node"}}), encoding="utf-8")
    (wf_dir / "txt2img_reflex.json").write_text(json.dumps({"output": ["1"]}), encoding="utf-8")

    # 扫描
    flows = WorkflowLoader.list_workflows(wf_dir)
    assert flows == ["txt2img"]

    # 加载
    api_json, reflex_json = WorkflowLoader.load_workflow_pair(wf_dir, "txt2img")
    assert "1" in api_json
    assert reflex_json["output"] == ["1"]

    # 异常测试
    with pytest.raises(ReflexNotFoundError):
        WorkflowLoader.load_workflow_pair(wf_dir, "not_exist")


def test_plugin_backward_compatibility():
    """验证 nonebot_plugin_comfyui 仍能正常导入并无损使用独立库功能"""
    import nonebot
    try:
        nonebot.get_driver()
    except Exception:
        nonebot.init()

    from nonebot_plugin_comfyui.exceptions import (
        ComfyUIPluginError,
        ComfyuiExceptions,
        ReflexJsonNotFoundError,
        ReflexJsonError,
        WorkflowAdminLimitation,
        WorkflowGroupLimitation,
        ArgsError
    )
    from nonebot_plugin_comfyui.services import workflow_engine, lora_engine
    from nonebot_plugin_comfyui.constants import MAX_SEED, REFLEX_DICT

    assert MAX_SEED == 2 ** 31
    assert "sampler" in REFLEX_DICT

    # 异常继承关系验证
    err = ReflexJsonNotFoundError("找不到 reflex")
    assert isinstance(err, ComfyUIPluginError)
    assert isinstance(err, ReflexError)
    assert isinstance(err, ReflexNotFoundError)

    admin_err = WorkflowAdminLimitation("仅限管理员")
    assert isinstance(admin_err, ComfyuiExceptions)

    # workflow_engine 桥接调用验证
    w, h = workflow_engine.calculate_dimensions(shape="s")
    assert w == 1024 and h == 1024
