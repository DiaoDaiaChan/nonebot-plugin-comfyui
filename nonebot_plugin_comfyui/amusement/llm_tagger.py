import json
from typing import Any
from ..config import config
from ..constants import DEFAULT_LLM_SYS_PROMPT, DEFAULT_LLM_CONVERSATIONS
from ..services.comfy_client import comfy_client
from ..services.audit.text_audit import clean_llm_response

user_session: dict[str | int, "Session"] = {}


class Session:
    def __init__(self, user_id: str | int) -> None:
        self.session_id = user_id

    async def main(self, to_openai: str, input_sys_text: str = "", preset: int = 0) -> str:
        if preset and preset < len(config.comfyui_llm_prompt_preset):
            llm_params = config.comfyui_llm_prompt_preset[preset]
        else:
            llm_params = config.comfyui_openai

        api_key = llm_params.get("token", "")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        finally_sys = input_sys_text or llm_params.get("prompt", DEFAULT_LLM_SYS_PROMPT)
        conversations = llm_params.get("conversations", DEFAULT_LLM_CONVERSATIONS)
        repeat_sys_prompt = llm_params.get("repeat_sys_prompt", False)

        ai_prompt = [{"role": "system", "content": finally_sys}]
        for i in range(0, len(conversations) - 1, 2):
            ai_prompt.append({"role": "user", "content": conversations[i]})
            ai_prompt.append({"role": "assistant", "content": conversations[i + 1]})

        final_user_content = to_openai
        if repeat_sys_prompt and finally_sys:
            final_user_content = f"{finally_sys}\n\n{to_openai}"

        conv = ai_prompt + [{"role": "user", "content": final_user_content}]
        payload: dict[str, Any] = {
            "messages": conv,
            "stop": [" Human:", " AI:"]
        }
        params = llm_params.get("params", {})
        payload.update(params)

        resp = await comfy_client.request(
            "POST",
            f"{llm_params['endpoint']}/chat/completions",
            json_data=payload,
            headers=headers,
            proxy=True
        )

        content = resp["choices"][0]["message"]["content"]
        return clean_llm_response(content)


def get_user_session(user_id: str | int) -> Session:
    if user_id not in user_session:
        user_session[user_id] = Session(user_id)
    return user_session[user_id]