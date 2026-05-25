"""
LLM 工具注册模块（解耦自 Main）。

## 为什么不用 @filter.llm_tool 装饰器

@filter.llm_tool 是在 Python 导入模块时（类定义阶段）执行的装饰器，
比 __init__ 更早。这导致两个问题：

  1. 无论 enable_llm_tool 配置如何，工具都会被写入全局 llm_tools 单例。
     运行时的 if not enable_llm_tool() 只能让工具调用返回错误提示，
     但工具对 LLM 始终可见，LLM 会在不该调用的时候调用它。

  2. 把工具移到 llm_tools.py 后，handler.__module__ 变为
     "data.plugins.suno302.llm_tools"，而 star_manager 只识别
     metadata.module_path（即 "data.plugins.suno302.main"），
     导致 self 绑定被静默跳过，工具调用时缺少 self 参数直接崩溃。

## 正确做法

在 Main.__init__ 里手动调用 context.provider_manager.llm_tools.add_func()，
此时 enable_llm_tool=False 可以直接跳过注册，工具对 LLM 完全不可见。
handler 是 functools.partial(self._tool_impl, self) 形式，
不依赖 star_manager 的 module_path 匹配，也无需额外的 Star 子类。
"""

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

# suno_generate 的工具描述（与原装饰器 docstring 保持一致）
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
    """提交任务并轮询结果（纯函数，不持有 self）。"""
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
        from .formatter import fmt_result  # 延迟导入，避免循环

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
    """
    suno_generate 工具的实际逻辑。

    此函数以普通异步函数（非方法）形式存在，
    避免依赖 star_manager 的 module_path 绑定机制。
    由 register() 用 functools.partial 直接包装后传给 add_func。
    """
    if not config_mgr.api_key():
        yield event.plain_result(_NO_KEY_MSG)
        return

    async for r in _generate(
        event, build_auto(prompt, config_mgr.default_model()), "全自动",
        prompt_hint=prompt,
    ):
        yield r


def register(context: Context) -> bool:
    """
    向框架注册 suno_generate LLM 工具。

    在 enable_llm_tool=True 时由 Main.__init__ 调用。
    返回 True 表示注册成功。

    与装饰器方案的区别：
      - 注册发生在运行时（__init__），而非导入时（类定义）。
      - handler 通过 add_func 直接传入，不依赖 star_manager 的
        module_path 匹配，彻底绕开 llm_tools.py vs main.py 的路径冲突。
    """
    try:
        mgr = context.provider_manager.llm_tools
        mgr.add_func(
            name=_TOOL_NAME,
            func_args=_TOOL_ARGS,
            desc=_TOOL_DESC,
            handler=_tool_impl,
        )
        # 标记为后台任务：框架立即返回并以 3600s 超时在后台执行，
        # 完成后自动唤醒 LLM 汇报结果，避免默认 60s 超时导致的 CancelledError。
        tool = mgr.get_func(_TOOL_NAME)
        if tool is not None:
            tool.is_background_task = True
        logger.info(f"[suno302] LLM 工具已注册（后台模式）：{_TOOL_NAME}")
        return True
    except Exception as e:
        logger.error(f"[suno302] LLM 工具注册失败：{e}")
        return False


def unregister(context: Context) -> None:
    """卸载 suno_generate 工具（插件卸载时可调用）。"""
    try:
        context.provider_manager.llm_tools.remove_func(_TOOL_NAME)
        logger.info(f"[suno302] LLM 工具已注销：{_TOOL_NAME}")
    except Exception as e:
        logger.warning(f"[suno302] LLM 工具注销时出错（可忽略）：{e}")
