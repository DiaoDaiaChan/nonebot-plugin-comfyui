import asyncio
import json
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(root_dir))

def test_imports():
    print("Testing imports...")
    import nonebot
    nonebot.init()

    import nonebot_plugin_comfyui
    from nonebot_plugin_comfyui.exceptions import (
        ComfyUIPluginError,
        ComfyuiExceptions,
        NoAvailableBackendError,
        ArgsError
    )
    from nonebot_plugin_comfyui.parser import comfyui_parser
    from nonebot_plugin_comfyui.services import (
        comfy_client,
        workflow_engine,
        lora_engine,
        rate_limiter,
        audit_image
    )
    from nonebot_plugin_comfyui.constants import MAX_SEED, REFLEX_DICT
    print("[PASS] All modules imported successfully without side-effects or errors.")


def test_exception_hierarchy():
    print("Testing exception hierarchy...")
    from nonebot_plugin_comfyui.exceptions import (
        ComfyUIPluginError,
        ComfyuiExceptions,
        NoAvailableBackendError,
        APIJsonError
    )

    err = NoAvailableBackendError("后端离线")
    assert isinstance(err, Exception), "Should inherit from Exception"
    assert isinstance(err, ComfyUIPluginError), "Should inherit from ComfyUIPluginError"
    assert issubclass(NoAvailableBackendError, ComfyuiExceptions), "Should be compatible with ComfyuiExceptions"
    assert ComfyuiExceptions.NoAvailableBackendError is NoAvailableBackendError
    print("[PASS] Exception hierarchy is properly structured and backward compatible.")


def test_parser_negative_prompt_fix():
    print("Testing parser negative prompt (-u) bug fix...")
    from nonebot_plugin_comfyui.parser import comfyui_parser

    # In the original code, dest was "negative_prompt example:prompt -u '低质量'"
    # which caused args.negative_prompt to not exist!
    test_args = ["1girl", "masterpiece", "-u", "bad quality, blurry", "-s", "12345", "-ar", "16:9"]
    parsed = comfyui_parser.parse_args(test_args)

    assert hasattr(parsed, "negative_prompt"), "negative_prompt attribute MUST exist"
    assert parsed.negative_prompt == ["bad quality, blurry"] or parsed.negative_prompt == "bad quality, blurry"
    assert parsed.seed == 12345
    assert parsed.accept_ratio == "16:9"
    assert "1girl" in parsed.prompt
    print("[PASS] Parser correctly extracts -u negative_prompt and other flags.")


def test_builtin_workflows():
    print("Testing built-in workflows...")
    wf_dir = root_dir / "nonebot_plugin_comfyui" / "build_in_wf"
    assert wf_dir.exists(), "build_in_wf directory must exist"

    files = list(wf_dir.glob("*.json"))
    assert len(files) > 0, "Should have built-in workflows"

    # Verify each non-reflex json has a corresponding _reflex.json
    for json_file in files:
        if not json_file.name.endswith("_reflex.json"):
            wf_name = json_file.stem
            reflex_file = wf_dir / f"{wf_name}_reflex.json"
            assert reflex_file.exists(), f"Reflex file missing for {wf_name}: {reflex_file}"
            # Verify JSON syntax
            with open(json_file, "r", encoding="utf-8") as f:
                json.load(f)
            with open(reflex_file, "r", encoding="utf-8") as f:
                json.load(f)

    # Verify img2img specifically
    assert (wf_dir / "img2img.json").exists()
    assert (wf_dir / "img2img_reflex.json").exists()
    print("[PASS] All built-in workflows are valid JSON and have matching reflex files.")


def test_lora_engine():
    print("Testing LoRA engine...")
    from nonebot_plugin_comfyui.services.lora_engine import lora_engine

    prompt = "1girl, <lora:detail:0.8>, solo, <lora:face_v2:1.2>, smile"
    clean_prompt, loras = lora_engine.extract_loras_from_prompt(prompt)

    assert loras == [("detail", 0.8), ("face_v2", 1.2)]
    assert "<lora:" not in clean_prompt
    assert "1girl" in clean_prompt
    assert "solo" in clean_prompt

    # Test applying LoRA to mock api_json
    mock_api = {
        "3": {
            "inputs": {"model": ["4", 0], "clip": ["4", 1]},
            "class_type": "KSampler"
        },
        "4": {
            "inputs": {"ckpt_name": "model.safetensors"},
            "class_type": "CheckpointLoaderSimple"
        }
    }
    lora_config = [{
        "10": {
            "from": {"model": 4, "clip": 4},
            "to": {"model": [3], "clip": [3]}
        }
    }]
    modified = lora_engine.apply_loras_to_api_json(mock_api, lora_config, [("detail.safetensors", 0.8)])
    assert "10" in modified
    assert modified["10"]["class_type"] == "LoraLoader"
    assert modified["10"]["inputs"]["lora_name"] == "detail.safetensors"
    assert modified["3"]["inputs"]["model"][0] == "10"
    print("[PASS] LoRA extraction and graph mutation pass.")


def test_dimensions():
    print("Testing dimensions calculation...")
    from nonebot_plugin_comfyui.services.workflow_engine import workflow_engine

    w, h = workflow_engine.calculate_dimensions(shape="p")
    assert (w, h) == (832, 1216)

    w, h = workflow_engine.calculate_dimensions(shape="l")
    assert (w, h) == (1216, 832)

    w, h = workflow_engine.calculate_dimensions(shape="1024x768")
    assert (w, h) == (1024, 768)

    w, h = workflow_engine.calculate_dimensions(accept_ratio="1:1")
    assert abs(w - h) <= 2
    print("[PASS] Dimension calculation pass.")


def test_rate_limiter():
    print("Testing rate limiter...")
    from nonebot_plugin_comfyui.services.rate_limiter import rate_limiter

    user_id = "test_user_123"
    in_cd, remain = rate_limiter.check_cd(user_id)
    assert not in_cd

    rate_limiter.update_cd(user_id)
    in_cd, remain = rate_limiter.check_cd(user_id)
    assert in_cd
    assert remain > 0

    # Superuser ignores CD
    in_cd, remain = rate_limiter.check_cd(user_id, is_superuser=True)
    assert not in_cd

    # Daily quota
    daily_key = rate_limiter.get_today_key(user_id)
    msg, reached = rate_limiter.check_daily_limit(daily_key, amount=2)
    assert not reached

    rate_limiter.revert_daily(daily_key, amount=2)
    assert rate_limiter.daily_records[daily_key] == 0
    print("[PASS] Rate limiter logic pass.")


if __name__ == "__main__":
    import shutil
    try:
        test_imports()
        test_exception_hierarchy()
        test_parser_negative_prompt_fix()
        test_builtin_workflows()
        test_lora_engine()
        test_dimensions()
        test_rate_limiter()
        print("\n[SUCCESS] ALL 7 TEST SUITES PASSED PERFECTLY!")
    finally:
        for folder in ["config", "data"]:
            p = root_dir / folder
            if p.exists() and p.is_dir():
                shutil.rmtree(p, ignore_errors=True)

