"""
请求体构建器。

把用户参数组装成符合 302.AI API 规范的 payload dict。
纯函数，无副作用，无外部依赖，便于单元测试。

API 端点：POST https://api.302.ai/suno/submit/music
"""

from __future__ import annotations


def build_auto(
    prompt: str,
    model: str,
    instrumental: bool = False,
) -> dict:
    """
    全自动模式 payload。

    Args:
        prompt: 歌曲描述，AI 据此自动生成歌词和风格。
        model: Suno 模型名，如 chirp-crow。
        instrumental: True 时生成纯音乐（无人声）。
    """
    return {
        "gpt_description_prompt": prompt,
        "mv": model,
        "make_instrumental": instrumental,
    }


def build_custom(
    title: str,
    lyrics: str,
    tags: str,
    model: str,
    instrumental: bool = False,
    vocal_gender: str | None = None,
    negative_tags: str | None = None,
    style_weight: float | None = None,
    weirdness: float | None = None,
) -> dict:
    """
    自定义模式 payload。

    Args:
        title: 歌曲标题，最多 80 字符。
        lyrics: 歌词内容，支持 [Verse]/[Chorus] 等标记。
        tags: 风格标签，逗号分隔，如 "pop, guitar, female vocal"。
        model: Suno 模型名。
        instrumental: True 时忽略 lyrics，生成纯音乐。
        vocal_gender: 人声性别，"f" 女声 / "m" 男声 / None 不指定。
        negative_tags: 排除的风格标签。
        style_weight: 风格参考度 0.0~1.0。
        weirdness: 创意发散度 0.0~1.0。
    """
    payload: dict = {
        "title": title[:80],
        "tags": tags,
        "mv": model,
        "make_instrumental": instrumental,
    }
    if not instrumental:
        payload["prompt"] = lyrics
    if negative_tags:
        payload["negative_tags"] = negative_tags

    # 构造可选 metadata 块
    meta: dict = {"create_mode": "custom"}
    can_control: list[str] = []
    sliders: dict = {}

    if vocal_gender in ("f", "m"):
        meta["vocal_gender"] = vocal_gender
    if style_weight is not None:
        sliders["style_weight"] = round(max(0.0, min(1.0, style_weight)), 2)
        can_control.append("style_weight")
    if weirdness is not None:
        sliders["weirdness_constraint"] = round(max(0.0, min(1.0, weirdness)), 2)
        can_control.append("weirdness_constraint")
    if sliders:
        meta["control_sliders"] = sliders
        meta["can_control_sliders"] = can_control

    # 只有 metadata 中有实质内容（除 create_mode 外）才附加
    if len(meta) > 1:
        payload["metadata"] = meta

    return payload
