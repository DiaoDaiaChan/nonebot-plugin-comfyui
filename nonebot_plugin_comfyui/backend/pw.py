from playwright.async_api import async_playwright

from ..config import config
from pathlib import Path

import aiofiles


async def get_workflow_sc(wf):

    async with async_playwright() as playwright:

        browser = await playwright.chromium.launch()
        context = await browser.new_context(
            viewport={'width': 3000, 'height': 2000}
        )
        page = await context.new_page()

        await page.goto(config.comfyui_url)
        await page.wait_for_load_state('networkidle')

        file_path = Path(config.comfyui_workflows_dir).resolve() / f'{wf}.json'

        drop_area = await page.query_selector('#comfy-file-input')
        await drop_area.set_input_files(file_path)

        await page.wait_for_load_state('networkidle')

        screenshot_path = Path('screenshot.jpg').resolve()
        await page.screenshot(path=screenshot_path, type="jpeg", full_page=True, quality=70)

        async with aiofiles.open(screenshot_path, 'rb') as f:
            image_bytes = await f.read()
            await browser.close()
            return image_bytes


