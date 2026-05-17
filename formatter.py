"""
结果格式化工具。

把 API 返回的 clip/task 对象转成用户可读文本。
纯函数，无副作用，无外部依赖。
"""

from .constants import CLIP_COMPLETE


def fmt_clip(clip: dict, idx: int) -> str:
    """格式化单条 clip 为多行文本。"""
    title = clip.get("title") or "无题"
    meta = clip.get("metadata") or {}
    tags = meta.get("tags") or ""
    duration = meta.get("duration")
    audio_url = clip.get("audio_url") or ""
    image_url = clip.get("image_url") or ""
    clip_id = clip.get("id") or ""

    lines = [f"🎵 第{idx}首：{title}"]
    if tags:
        lines.append(f"🎸 风格：{tags}")
    if duration is not None:
        m, s = divmod(int(float(duration)), 60)
        lines.append(f"⏱ 时长：{m}:{s:02d}")
    if audio_url:
        lines.append(f"🔗 音频：{audio_url}")
    if image_url:
        lines.append(f"🖼 封面：{image_url}")
    if clip_id:
        lines.append(f"🆔 Clip ID：{clip_id}")
    return "\n".join(lines)


def fmt_result(clips: list[dict], task_id: str, mode: str) -> str:
    """格式化完整生成结果（所有 clip + task_id）。"""
    lines = [f"✅ {mode}生成完成！共 {len(clips)} 首\n"]
    for i, clip in enumerate(clips, 1):
        lines.append(fmt_clip(clip, i))
        lines.append("")
    lines.append(f"📌 task_id：{task_id}")
    return "\n".join(lines).strip()


def fmt_status(task: dict, task_id: str) -> str:
    """格式化任务状态查询结果。"""
    task_status = task.get("status", "未知")
    progress = task.get("progress", "")
    fail_reason = task.get("fail_reason", "")
    clips: list[dict] = task.get("data", [])

    lines = [f"📋 任务 {task_id[:8]}… 状态：{task_status}"]
    if progress:
        lines.append(f"进度：{progress}")
    if fail_reason:
        lines.append(f"失败原因：{fail_reason}")
    lines.append("")

    for i, clip in enumerate(clips, 1):
        clip_status = clip.get("status", "未知")
        clip_title = clip.get("title") or "无题"
        clip_id = clip.get("id") or ""
        audio_url = clip.get("audio_url") or ""
        meta = clip.get("metadata") or {}
        duration = meta.get("duration")

        lines.append(f"【第{i}首】{clip_title}  ({clip_status})")
        if clip_id:
            lines.append(f"  Clip ID：{clip_id}")
        if duration is not None:
            m, s = divmod(int(float(duration)), 60)
            lines.append(f"  时长：{m}:{s:02d}")
        if audio_url and clip_status in CLIP_COMPLETE:
            lines.append(f"  音频：{audio_url}")

    return "\n".join(lines).strip()


HELP_TEXT = (
    "🎵 Suno AI 音乐生成（302.AI）\n\n"
    "━━━━ 命令列表 ━━━━\n\n"
    "▶ /suno auto <描述>\n"
    "  全自动模式，AI 自动编词+配乐\n"
    "  例：/suno auto 轻快的夏日吉他流行曲\n\n"
    "▶ /suno inst <描述>\n"
    "  纯音乐（无人声），别名：/suno instrumental\n"
    "  例：/suno inst epic orchestral battle music\n\n"
    "▶ /suno custom <标题> <风格> [男/女]\n"
    "  自定义模式第一步，设置标题和风格\n"
    "  ⚠️ 标题和风格不能含空格\n"
    "  例：/suno custom 夏天的风 pop 女\n\n"
    "▶ /suno lyrics <歌词>\n"
    "  自定义模式第二步，一次性发完全部歌词\n"
    "  换行可直接回车，或用 \\n 代替\n"
    "  例：/suno lyrics [Verse]\n  阳光照耀海面\n  [Chorus]\n  夏天的风\n\n"
    "▶ /suno status <task_id>\n"
    "  查询任务状态及结果\n\n"
    "▶ /suno help\n"
    "  显示本帮助\n\n"
    "━━━━ 说明 ━━━━\n"
    "• 每次生成 1~2 首歌，耗时约 60~120 秒\n"
    "• 生成文件保留 14 天后自动删除\n"
    "• 可在管理面板配置默认模型和轮询参数"
)
