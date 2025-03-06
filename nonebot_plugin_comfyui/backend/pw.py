import aiofiles
import json
import random

from playwright.async_api import async_playwright

from ..config import config, BACKEND_URL_LIST
from .utils import get_ava_backends
from pathlib import Path

import aiofiles


async def get_workflow_sc(wf):

    async with async_playwright() as playwright:

        browser = await playwright.chromium.launch()
        context = await browser.new_context(
            viewport={'width': 3000, 'height': 2000}
        )
        page = await context.new_page()
        
        ava_backends, _ = await get_ava_backends()

        file_path = Path(config.comfyui_workflows_dir).resolve() / f'{wf}.json'
        reflex_file_path = Path(config.comfyui_workflows_dir).resolve() / f'{wf}_reflex.json'
        
        async with aiofiles.open(reflex_file_path, 'rb') as f:
            reflex_json = json.loads(await f.read())
            
        available_in = reflex_json.get('available', None)

        if available_in:
            ava_backend_inter = set(available_in).intersection(ava_backends)
            if ava_backend_inter:
                url = BACKEND_URL_LIST[random.choice(list(ava_backend_inter))]
        else:
            url = BACKEND_URL_LIST[random.choice(list(ava_backends))]
        
        await page.goto(url)
        await page.wait_for_load_state('networkidle')

        drop_area = await page.query_selector('#comfy-file-input')
        await drop_area.set_input_files(file_path)

        await page.wait_for_load_state('networkidle')

        screenshot_path = Path('screenshot.jpg').resolve()
        await page.screenshot(path=screenshot_path, type="jpeg", full_page=True, quality=70)

        async with aiofiles.open(screenshot_path, 'rb') as f:
            image_bytes = await f.read()
            await browser.close()
            return image_bytes


