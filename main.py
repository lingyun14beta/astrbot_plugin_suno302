"""
AstrBot Plugin: Suno AI Music via 302.AI

命令列表：
  /suno help                        显示帮助
  /suno auto <描述>                 全自动模式
  /suno inst <描述>                 纯音乐（别名：/suno instrumental）
  /suno custom <标题> <风格> [男/女]  自定义模式第一步（标题和风格不能含空格）
  /suno lyrics <歌词>               自定义模式第二步，一次性发完歌词
  /suno status <task_id>            查询任务
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

    # ── 内部：提交 → 轮询 → yield 结果 ──────────────────────────────────────

    async def _generate(self, event: AstrMessageEvent, payload: dict, mode: str):
        """统一校验 key、提交任务、轮询结果。"""
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

    # ── /suno help ────────────────────────────────────────────────────────────

    @suno.command("help")
    async def cmd_help(self, event: AstrMessageEvent):
        """显示帮助信息。"""
        yield event.plain_result(HELP_TEXT)

    # ── /suno auto <描述> ─────────────────────────────────────────────────────

    @suno.command("auto")
    async def cmd_auto(self, event: AstrMessageEvent, prompt: GreedyStr):
        """全自动模式。用法：/suno auto <描述>"""
        if not config_mgr.api_key():
            yield event.plain_result(_NO_KEY_MSG)
            return
        yield event.plain_result(
            f"🎼 正在生成音乐，请稍候（约 60~120 秒）……\n描述：{prompt}"
        )
        async for r in self._generate(
            event, build_auto(prompt, config_mgr.default_model()), "全自动"
        ):
            yield r

    # ── /suno inst <描述>（别名 /suno instrumental）───────────────────────────

    @suno.command("inst", alias={"instrumental"})
    async def cmd_inst(self, event: AstrMessageEvent, prompt: GreedyStr):
        """纯音乐（无人声）。用法：/suno inst <描述>"""
        if not config_mgr.api_key():
            yield event.plain_result(_NO_KEY_MSG)
            return
        yield event.plain_result(
            f"🎹 正在生成纯音乐，请稍候（约 60~120 秒）……\n描述：{prompt}"
        )
        async for r in self._generate(
            event,
            build_auto(prompt, config_mgr.default_model(), instrumental=True),
            "纯音乐",
        ):
            yield r

    # ── /suno custom <标题> <风格> [男/女]（第一步）──────────────────────────

    @suno.command("custom")
    async def cmd_custom(
        self,
        event: AstrMessageEvent,
        title: str,
        style: str,
        gender: str = "",
    ):
        """自定义模式第一步。用法：/suno custom <标题> <风格> [男/女]（标题和风格不能含空格）"""
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

    # ── /suno lyrics <歌词>（第二步）─────────────────────────────────────────

    @suno.command("lyrics")
    async def cmd_lyrics(self, event: AstrMessageEvent, lyrics: GreedyStr):
        """自定义模式第二步，发送歌词。用法：/suno lyrics <歌词>"""
        if not config_mgr.api_key():
            yield event.plain_result(_NO_KEY_MSG)
            return

        # 将字面 \n 转为真实换行，方便用户在单行消息中表示段落
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

        yield event.plain_result(
            f"🎼 正在生成音乐，请稍候（约 60~120 秒）……\n"
            f"标题：{title}  风格：{style}"
            + (f"  人声：{gender_label}" if vocal_gender else "")
        )
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
        ):
            yield r

    # ── LLM 工具（可在配置中开关）────────────────────────────────────────────────

    @filter.llm_tool(name="suno_generate")
    async def tool_generate(self, event: AstrMessageEvent, prompt: str):
        """根据描述生成 AI 音乐，每次产出 1~2 首歌曲。仅在用户明确要求生成音乐时调用。

        Args:
            prompt(string): 歌曲描述，例如"一首轻快的夏日流行曲，女声"
        """
        if not config_mgr.enable_llm_tool():
            yield event.plain_result("❌ Suno 音乐生成工具未启用，请在管理面板中开启。")
            return
        if not config_mgr.api_key():
            yield event.plain_result(_NO_KEY_MSG)
            return
        yield event.plain_result(
            f"🎼 正在生成音乐，请稍候（约 60~120 秒）……\n描述：{prompt}"
        )
        async for r in self._generate(
            event, build_auto(prompt, config_mgr.default_model()), "全自动"
        ):
            yield r

    # ── /suno status <task_id> ────────────────────────────────────────────────

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
