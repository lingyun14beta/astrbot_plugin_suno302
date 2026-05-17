"""
302.AI Suno API 客户端。

复用单个 ClientSession 减少 TCP 握手开销。
所有 HTTP 响应均强制读取文本后手动解析 JSON，
避免服务端返回 text/plain 时 aiohttp 抛出 ContentTypeError。
"""

import json

import aiohttp

API_BASE = "https://api.302.ai"
SUBMIT_URL = f"{API_BASE}/suno/submit/music"
FETCH_URL = f"{API_BASE}/suno/fetch/{{task_id}}"


class SunoApiClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._session: aiohttp.ClientSession | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """关闭 ClientSession，应在 finally 块中调用。"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get_json(self, resp: aiohttp.ClientResponse, context: str) -> dict:
        """强制解析响应体为 dict，类型不符时抛出 RuntimeError。"""
        text = await resp.text()
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"{context}（HTTP {resp.status}），响应非 JSON：{text[:200]}"
            )
        if not isinstance(body, dict):
            raise RuntimeError(
                f"{context}（HTTP {resp.status}），响应格式异常：{text[:200]}"
            )
        return body

    async def submit(self, payload: dict) -> str:
        """提交生成任务，返回 task_id。"""
        session = self._get_session()
        async with session.post(
            SUBMIT_URL,
            json=payload,
            headers=self._headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            body = await self._get_json(resp, "提交失败")

        if resp.status != 200:
            raise RuntimeError(
                f"提交失败（HTTP {resp.status}）: {body.get('message', body)}"
            )
        code = str(body.get("code", ""))
        if code not in ("200", "0", "success"):
            raise RuntimeError(f"提交失败（code={code}）: {body.get('message', body)}")
        task_id = body.get("data", "")
        if not task_id:
            raise RuntimeError(f"返回中无 task_id，响应：{body}")
        return str(task_id)

    async def fetch(self, task_id: str) -> dict:
        """查询任务状态，返回 data 对象。"""
        url = FETCH_URL.format(task_id=task_id)
        session = self._get_session()
        async with session.get(
            url,
            headers=self._headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            body = await self._get_json(resp, "查询失败")

        if resp.status != 200:
            raise RuntimeError(
                f"查询失败（HTTP {resp.status}）: {body.get('message', body)}"
            )
        return body.get("data", {})
