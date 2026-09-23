from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from nonebot_plugin_alconna import UniMessage

from ..config import config
from ..exceptions import TextContentNotSafeError
from ..services.comfy_client import comfy_client
from ..services.audit import audit_image, text_audit


@dataclass
class DanbooruItem:
    resp_img: UniMessage = field(default_factory=UniMessage)


async def danbooru(tag: str, limit: int = 3) -> list[DanbooruItem]:
    resp_list: list[DanbooruItem] = []
    db_base_url = "https://danbooru.donmai.us"
    lim = limit if isinstance(limit, int) else 3

    resp = await comfy_client.request(
        "GET",
        f"{db_base_url}/autocomplete?search%5Bquery%5D={tag}&search%5Btype%5D=tag_query&version=1&limit={lim}",
        as_text=True,
        proxy=True
    )

    soup = BeautifulSoup(resp, 'html.parser')
    tags = soup.find_all('li', class_='ui-menu-item')

    raw_data_values = []
    for t in tags:
        v = t.get('data-autocomplete-value')
        if v:
            raw_data_values.append(v)

    # 审核词条
    audit_res = await text_audit(str(raw_data_values))
    if 'yes' in audit_res:
        raise TextContentNotSafeError("Danbooru 词条内容违规")

    for t_val in raw_data_values:
        item = DanbooruItem()
        item.resp_img += f"({t_val}:1)\n"

        try:
            image_resp = await comfy_client.request(
                "GET",
                f"{db_base_url}/posts?tags={t_val}",
                as_text=True,
                proxy=True
            )
            sub_soup = BeautifulSoup(image_resp, 'html.parser')
            img_urls = [img['src'] for img in sub_soup.find_all('img') if img.get('src', '').startswith('http')][:2]

            for u in img_urls:
                clean_url = u.replace("gchat.qpic.cn", "multimedia.nt.qq.com.cn")
                byte_img = await comfy_client.request("GET", clean_url, as_json=False)
                if config.comfyui_audit:
                    a_res = await audit_image(byte_img)
                    if a_res.get("is_nsfw"):
                        item.resp_img += "太涩了\n"
                    else:
                        item.resp_img += UniMessage.image(raw=byte_img)
                else:
                    item.resp_img += UniMessage.image(raw=byte_img)
        except Exception:
            pass

        resp_list.append(item)

    return resp_list
