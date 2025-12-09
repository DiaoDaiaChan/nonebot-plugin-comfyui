import asyncio

from bs4 import BeautifulSoup
from ..backend import RespMsg
from ..backend.utils import http_request, pic_audit_standalone, download_img, txt_audit
from nonebot_plugin_alconna import UniMessage
from ..exceptions import ComfyuiExceptions
from ..config import config


async def danbooru(tag: str, limit):

    resp_list = []
    db_base_url = "https://danbooru.donmai.us"

    if isinstance(limit, int):
        limit = limit

    else:
        limit = 3

    msg = tag
    resp = await http_request(
        "GET",
        f"{db_base_url}/autocomplete?search%5Bquery%5D={msg}&search%5Btype%5D=tag_query&version=1&limit={limit}",
        proxy=True,
        text=True
    )

    soup = BeautifulSoup(resp, 'html.parser')
    tags = soup.find_all('li', class_='ui-menu-item')

    data_values = []
    raw_data_values = []
    for tag in tags:
        data_value = tag['data-autocomplete-value']
        raw_data_values.append(data_value)
        data_value_space = data_value.replace('_', ' ')
        data_values.append(data_value_space)

    resp = await txt_audit(str(data_values))
    if 'yes' in resp:
        raise ComfyuiExceptions.TextContentNotSafeError

    build_msg = []

    for tag in raw_data_values:
        build_msg.append(f"({tag}:1)")
        # tag = tag.replace(' ', '_').replace('(', '%28').replace(')', '%29')

        resp = RespMsg()

        image_resp = await http_request(
            "GET",
            f"{db_base_url}/posts?tags={tag}",
            text=True,
            proxy=True
        )

        soup = BeautifulSoup(image_resp, 'html.parser')
        img_urls = [img['src'] for img in soup.find_all('img') if img['src'].startswith('http')][:2]
        msg = ''
        for url in img_urls:
            base64_image, bytes_image = await download_img(url)
            if config.comfyui_audit:
                is_nsfw = await pic_audit_standalone(base64_image)
                is_nsfw = is_nsfw["is_nsfw"]
                if is_nsfw:
                    msg += "太涩了"
                else:
                    msg += UniMessage.image(raw=bytes_image)
            else:
                msg += UniMessage.image(raw=bytes_image)

        resp.resp_img += f"({tag}:1)\n"
        resp.resp_img += msg

        resp_list.append(resp)

    return resp_list
