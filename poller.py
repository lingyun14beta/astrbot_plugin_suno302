"""
任务轮询器。

定时调用 SunoApiClient.fetch() 查询任务状态，
直到所有 clip 完成、任务失败或超时为止。
"""

import asyncio

from astrbot.api import logger

from .api_client import SunoApiClient
from .constants import CLIP_COMPLETE, CLIP_ERROR, TASK_FAILED, TASK_SUCCESS


class SunoPoller:
    def __init__(
        self,
        client: SunoApiClient,
        max_poll: int = 40,
        poll_interval: int = 5,
    ) -> None:
        """
        Args:
            client: 已初始化的 SunoApiClient 实例。
            max_poll: 最大轮询次数，超出后抛出 TimeoutError。
            poll_interval: 每次轮询之间等待的秒数。
        """
        self.client = client
        self.max_poll = max_poll
        self.poll_interval = poll_interval

    async def poll(self, task_id: str) -> list[dict]:
        """
        轮询直到任务完成，返回已完成的 clip 列表。

        Fetch 返回结构（data 字段）：
            {
                "status": "IN_PROGRESS" | "SUCCESS" | "FAILED",
                "progress": "50%",
                "fail_reason": "",
                "data": [
                    {
                        "id": "...",
                        "title": "...",
                        "status": "complete" | "streaming" | "error" | "SUCCESS",
                        "audio_url": "https://cdn1.suno.ai/....mp3",
                        "image_url": "https://cdn1.suno.ai/....png",
                        "metadata": {"tags": "...", "duration": 169.52, ...},
                    },
                    ...
                ],
            }

        Raises:
            RuntimeError: 任务失败或 clip 级别错误。
            TimeoutError: 超过 max_poll 次仍未完成。
        """
        for attempt in range(1, self.max_poll + 1):
            await asyncio.sleep(self.poll_interval)

            task = await self.client.fetch(task_id)
            status = task.get("status", "")
            clips: list[dict] = task.get("data", [])
            progress = task.get("progress", "")

            logger.debug(
                f"[suno302] task={task_id[:8]}… "
                f"attempt={attempt}/{self.max_poll} "
                f"status={status} progress={progress}"
            )

            if status == TASK_FAILED:
                reason = task.get("fail_reason") or "未知错误"
                raise RuntimeError(f"任务失败: {reason}")

            done = [c for c in clips if c.get("status") in CLIP_COMPLETE]
            errors = [c for c in clips if c.get("status") == CLIP_ERROR]

            if errors and not done:
                msg = errors[0].get("metadata", {}).get("error_message") or "未知错误"
                raise RuntimeError(f"生成失败: {msg}")

            if status == TASK_SUCCESS or (done and len(done) >= len(clips)):
                return done if done else clips

        raise TimeoutError(
            f"任务超时（已等待 {self.max_poll * self.poll_interval} 秒），"
            f"可用 /suno status {task_id} 稍后查询"
        )
