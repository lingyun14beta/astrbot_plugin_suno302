"""
AstrBot Plugin: Suno AI Music via 302.AI

命令列表：
  /suno help                        显示帮助
  /suno auto <描述>                 全自动模式
  /suno inst <描述>                 纯音乐（别名：/suno instrumental）
  /suno custom <标题> <风格> [男/女]  自定义模式第一步（标题和风格不能含空格）
  /suno lyrics <歌词>               自定义模式第二步，一次性发完歌词
  /suno status <task_id>            查询任务

LLM 工具（可在配置中开关）：
  由 llm_tools.register() 在 __init__ 中按需注册。
  enable_llm_tool=False 时工具完全不可见，不影响 LLM 行为。
"""

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.star.filter.command import GreedyStr

from . import config_mgr
from .api_client import SunoApiClient
from .formatter import HELP_TEXT, fmt_result, fmt_status
from .payload_builder import build_auto, build_custom
from .poller import SunoPoller

_NO_KEY_MSG = (
    "❌ 未配置 302.AI API Key。\n"
    "请在 AstrBot 管理面板 → 插件 → astrbot_plugin_suno302 → 配置 中填写。"
)

# 用户待定的自定义参数：key = sender_id, value = (title, style, vocal_gender)
_PENDING_CUSTOM: dict[str, tuple[str, str, str | None]] = {}


class Main(Star):
    def __init__(self, context: Context, config=None) -> None:
        super().__init__(context)
        config_mgr.init(config)
        self._register_llm_tool(context)

    def _register_llm_tool(self, context: Context) -> None:
        """
        按需注册 LLM 工具。

        在 __init__（运行时）注册，而非在模块导入时（装饰器）注册，
        使 enable_llm_tool=False 时工具对 LLM 完全不可见。
        """
        if not config_mgr.enable_llm_tool():
            logger.debug("[suno302] enable_llm_tool=False，跳过 LLM 工具注册")
            return

        from . import llm_tools  # 按需导入
        llm_tools.register(context)

    # ── 内部：提交 → 轮询 → yield 结果 ──────────────────────────────────────

    async def _generate(
        self, event: AstrMessageEvent, payload: dict, mode: str, prompt_hint: str = ""
    ):
        """统一校验 key、提交任务、轮询结果。

        Args:
            prompt_hint: 显示在"正在生成"消息里的描述文字（可为空）。
        """
        key = config_mgr.api_key()
        if not key:
            yield event.plain_result(_NO_KEY_MSG)
            return

        max_poll, interval = config_mgr.poll_params()
        client = SunoApiClient(key)
        poller = SunoPoller(client, max_poll=max_poll, poll_interval=interval)

        try:
            task_id = await client.submit(payload)
            logger.info(f"[suno302] {mode} 任务已提交 task_id={task_id}")

            # 提交成功后才发"正在生成"消息，此时已有 task_id 可附上
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
            logger.error(f"[suno302] {mode} 生成失败: {e}")
            yield event.plain_result(f"❌ {mode}生成失败：{e}")
        finally:
            await client.close()

    # ── /suno 指令组 ──────────────────────────────────────────────────────────

    @filter.command_group("suno")
    def suno(self):
        pass

    @suno.command("help")
    async def cmd_help(self, event: AstrMessageEvent):
        """显示帮助信息。"""
        yield event.plain_result(HELP_TEXT)

    @suno.command("auto")
    async def cmd_auto(self, event: AstrMessageEvent, prompt: GreedyStr):
        """全自动模式。用法：/suno auto <描述>"""
        if not config_mgr.api_key():
            yield event.plain_result(_NO_KEY_MSG)
            return
        async for r in self._generate(
            event, build_auto(prompt, config_mgr.default_model()), "全自动",
            prompt_hint=prompt,
        ):
            yield r

    @suno.command("inst", alias={"instrumental"})
    async def cmd_inst(self, event: AstrMessageEvent, prompt: GreedyStr):
        """纯音乐（无人声）。用法：/suno inst <描述>"""
        if not config_mgr.api_key():
            yield event.plain_result(_NO_KEY_MSG)
            return
        async for r in self._generate(
            event,
            build_auto(prompt, config_mgr.default_model(), instrumental=True),
            "纯音乐",
            prompt_hint=prompt,
        ):
            yield r

    @suno.command("custom")
    async def cmd_custom(
        self,
        event: AstrMessageEvent,
        title: str,
        style: str,
        gender: str = "",
    ):
        """自定义模式第一步。用法：/suno custom <标题> <风格> [男/女]"""
        if not config_mgr.api_key():
            yield event.plain_result(_NO_KEY_MSG)
            return

        vocal_gender = None
        if gender.lower() in ("女", "f"):
            vocal_gender = "f"
        elif gender.lower() in ("男", "m"):
            vocal_gender = "m"

        gender_label = {"f": "女", "m": "男"}.get(vocal_gender, "")
        _PENDING_CUSTOM[event.get_sender_id()] = (title, style, vocal_gender)

        gender_info = f"  人声：{gender_label}" if vocal_gender else ""
        yield event.plain_result(
            "✅ 已设置\n"
            f"标题：{title}  风格：{style}{gender_info}\n\n"
            "📝 请用 /suno lyrics <歌词> 发送歌词（支持换行，一次性发完）"
        )

    @suno.command("lyrics")
    async def cmd_lyrics(self, event: AstrMessageEvent, lyrics: GreedyStr):
        """自定义模式第二步，发送歌词。用法：/suno lyrics <歌词>"""
        if not config_mgr.api_key():
            yield event.plain_result(_NO_KEY_MSG)
            return

        lyrics = lyrics.replace("\\n", "\n").strip()
        if not lyrics:
            yield event.plain_result("❌ 歌词不能为空。")
            return

        pending = _PENDING_CUSTOM.pop(event.get_sender_id(), None)
        if not pending:
            yield event.plain_result(
                "❌ 请先用 /suno custom <标题> <风格> 设置标题和风格。"
            )
            return

        title, style, vocal_gender = pending
        gender_label = {"f": "女", "m": "男"}.get(vocal_gender, "")

        async for r in self._generate(
            event,
            build_custom(
                title=title,
                lyrics=lyrics,
                tags=style,
                model=config_mgr.default_model(),
                vocal_gender=vocal_gender,
            ),
            "自定义",
            prompt_hint=f"{title}  {style}" + (f"  {gender_label}声" if vocal_gender else ""),
        ):
            yield r

    @suno.command("status")
    async def cmd_status(self, event: AstrMessageEvent, task_id: str):
        """查询任务状态。用法：/suno status <task_id>"""
        key = config_mgr.api_key()
        if not key:
            yield event.plain_result(_NO_KEY_MSG)
            return
        client = SunoApiClient(key)
        try:
            task = await client.fetch(task_id)
            yield event.plain_result(fmt_status(task, task_id))
        except Exception as e:
            logger.error(f"[suno302] 状态查询失败: {e}")
            yield event.plain_result(f"❌ 查询失败：{e}")
        finally:
            await client.close()
