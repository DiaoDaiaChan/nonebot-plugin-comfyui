import json
import os
import random
import tempfile
from pathlib import Path
from nonebot import logger
from ..config import config, BACKEND_URL_LIST
from ..services.comfy_client import comfy_client


async def get_workflow_sc(wf: str) -> bytes | None:
    """使用 Playwright 截取 ComfyUI 前端工作流图预览（可选功能，依赖 playwright）"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.debug("未安装 playwright 依赖，跳过工作流网页截图预览")
        return None

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            context = await browser.new_context(viewport={'width': 3000, 'height': 2000})
            page = await context.new_page()

            ava_backends, _ = await comfy_client.get_available_backends()
            if not ava_backends:
                await browser.close()
                return None

            wf_dir = Path(config.comfyui_workflows_dir).resolve()
            file_path = wf_dir / f'{wf}.json'
            reflex_file_path = wf_dir / f'{wf}_reflex.json'

            if not reflex_file_path.exists():
                await browser.close()
                return None

            with open(reflex_file_path, 'r', encoding='utf-8') as f:
                reflex_json = json.load(f)

            available_in = reflex_json.get('available')
            if available_in:
                ava_backend_inter = set(available_in).intersection(ava_backends)
                if ava_backend_inter:
                    url = BACKEND_URL_LIST[random.choice(list(ava_backend_inter))]
                else:
                    url = BACKEND_URL_LIST[random.choice(list(ava_backends))]
            else:
                url = BACKEND_URL_LIST[random.choice(list(ava_backends))]

            await page.goto(url)
            await page.wait_for_load_state('networkidle')

            drop_area = await page.query_selector('#comfy-file-input')
            if drop_area:
                await drop_area.set_input_files(str(file_path))
                await page.wait_for_load_state('networkidle')

            tmp_path = ""
            try:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_f:
                    tmp_path = tmp_f.name

                await page.screenshot(path=tmp_path, type="jpeg", full_page=True, quality=70)
                with open(tmp_path, 'rb') as f:
                    image_bytes = f.read()
                return image_bytes
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
                await browser.close()
    except Exception as e:
        logger.warning(f"Playwright 截图生成失败: {e}")
        return None
