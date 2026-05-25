from __future__ import annotations

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context

from . import config_mgr
from .api_client import SunoApiClient
from .payload_builder import build_auto
from .poller import SunoPoller

_NO_KEY_MSG = (
    "❌ 未配置 302.AI API Key。\n"
    "请在 AstrBot 管理面板 → 插件 → astrbot_plugin_suno302 → 配置 中填写。"
)

_TOOL_NAME = "suno_generate"
_TOOL_DESC = "根据描述生成 AI 音乐，每次产出 1~2 首歌曲。仅在用户明确要求生成音乐时调用。"
_TOOL_ARGS = [
    {
        "type": "string",
        "name": "prompt",
        "description": "歌曲描述，例如：一首轻快的夏日流行曲，女声",
    }
]


async def _generate(event: AstrMessageEvent, payload: dict, mode: str, prompt_hint: str = ""):
    key = config_mgr.api_key()
    if not key:
        yield event.plain_result(_NO_KEY_MSG)
        return

    max_poll, interval = config_mgr.poll_params()
    client = SunoApiClient(key)
    poller = SunoPoller(client, max_poll=max_poll, poll_interval=interval)

    try:
        task_id = await client.submit(payload)
        logger.info(f"[suno302/llm_tool] {mode} 任务已提交 task_id={task_id}")
        from .formatter import fmt_result

        icon = "🎹" if "纯音乐" in mode else "🎼"
        hint_line = f"\n描述：{prompt_hint}" if prompt_hint else ""
        yield event.plain_result(
            f"{icon} 正在生成{mode}，请稍候（约 60~120 秒）……"
            f"{hint_line}\n📌 task_id：{task_id}"
        )

        clips = await poller.poll(task_id)
        if not clips:
            yield event.plain_result(
                "❌ 生成完成但未返回任何歌曲，请稍后用 /suno status 查询。"
            )
            return
        yield event.plain_result(fmt_result(clips, task_id, mode))
    except TimeoutError as e:
        yield event.plain_result(f"⏰ {e}")
    except Exception as e:
        logger.error(f"[suno302/llm_tool] {mode} 生成失败: {e}")
        yield event.plain_result(f"❌ {mode}生成失败：{e}")
    finally:
        await client.close()


async def _tool_impl(event: AstrMessageEvent, prompt: str):
    if not config_mgr.api_key():
        yield event.plain_result(_NO_KEY_MSG)
        return

    async for r in _generate(
        event, build_auto(prompt, config_mgr.default_model()), "全自动",
        prompt_hint=prompt,
    ):
        yield r


def register(context: Context) -> bool:
    try:
        mgr = context.provider_manager.llm_tools
        mgr.add_func(
            name=_TOOL_NAME,
            func_args=_TOOL_ARGS,
            desc=_TOOL_DESC,
            handler=_tool_impl,
        )
        tool = mgr.get_func(_TOOL_NAME)
        if tool is not None:
            tool.is_background_task = True
        logger.info(f"[suno302] LLM 工具已注册（后台模式）：{_TOOL_NAME}")
        return True
    except Exception as e:
        logger.error(f"[suno302] LLM 工具注册失败：{e}")
        return False


def unregister(context: Context) -> None:
    try:
        context.provider_manager.llm_tools.remove_func(_TOOL_NAME)
        logger.info(f"[suno302] LLM 工具已注销：{_TOOL_NAME}")
    except Exception as e:
        logger.warning(f"[suno302] LLM 工具注销时出错（可忽略）：{e}")
