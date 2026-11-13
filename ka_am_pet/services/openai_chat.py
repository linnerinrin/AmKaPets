"""OpenAI 兼容 Chat Completions 客户端与结构化中文错误。

严禁 import Qt；本模块在 worker 线程中被调用，通过 Qt Signal 回主线程。
POST {base_url}/chat/completions（base_url 去末尾 /），
Header: Authorization: Bearer <api_key>；解析 choices[0].message.content；
HTTP 非 2xx / 缺字段 / 空 choices / 连接错误 / 超时统一转为中文 ChatError。
"""

from __future__ import annotations

import requests

from ka_am_pet.models import ChatSettings


class ChatError(Exception):
    """对话请求失败，message 为可直接展示的中文错误信息。"""

    def __init__(self, message: str) -> None:
        """:param message: 面向用户的中文错误描述。"""
        super().__init__(message)
        self.message: str = message


class ChatService:
    """OpenAI 兼容 Chat Completions 服务封装（同步，供 worker 线程调用）。"""

    def __init__(self, settings: ChatSettings, session: requests.Session | None = None) -> None:
        """初始化服务。

        :param settings: 对话设置（base_url/api_key/model/timeout 等）。
        :param session: 可注入的 requests.Session（便于测试 mock）。
        """
        self._settings = settings
        self._session = session or requests.Session()

    def send(self, pet_id: str, user_text: str, history: list[dict]) -> str:
        """发送一轮对话，返回助手文本。

        messages = system prompt + history + 当前 user_text；显式 timeout；
        temperature=0.8；不依赖 response_format/tools/stream。

        :param pet_id: 宠物 id（用于日志/扩展，不发送）。
        :param user_text: 用户输入。
        :param history: 最近 N 轮消息字典列表。
        :return: 助手回复文本。
        :raises ChatError: 未配 Key / 网络 / 超时 / HTTP 非 2xx / 缺字段，中文描述。
        """
        s = self._settings
        if not s.api_key.strip():
            raise ChatError("还没有配置 API Key，请先在设置里填写。")

        url = f"{s.base_url.rstrip('/')}/chat/completions"
        messages = [{"role": "system", "content": s.system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})
        payload = {"model": s.model, "messages": messages, "temperature": 0.8}
        headers = {
            "Authorization": f"Bearer {s.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = self._session.post(url, json=payload, headers=headers, timeout=s.timeout_seconds)
        except requests.Timeout as exc:
            raise ChatError(f"请求超时（{s.timeout_seconds} 秒），请检查网络或稍后再试。") from exc
        except requests.ConnectionError as exc:
            raise ChatError("连接失败，请检查 base_url 和网络。") from exc
        except requests.RequestException as exc:
            raise ChatError(f"网络请求失败：{exc}") from exc

        if not (200 <= resp.status_code < 300):
            detail = ""
            try:
                err = resp.json()
                if isinstance(err, dict):
                    detail = str(err.get("error", {}).get("message", ""))[:200]
            except ValueError:
                detail = resp.text[:200]
            raise ChatError(f"服务返回错误（HTTP {resp.status_code}）：{detail or '无详细信息'}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise ChatError("服务返回的不是合法 JSON。") from exc

        try:
            choices = data["choices"]
            if not choices:
                raise ChatError("服务返回了空的 choices。")
            content = choices[0]["message"]["content"]
        except ChatError:
            raise
        except (KeyError, IndexError, TypeError) as exc:
            raise ChatError("服务返回格式异常，缺少 choices[0].message.content。") from exc
        if not isinstance(content, str) or not content.strip():
            raise ChatError("服务返回了空回复。")
        return content.strip()
