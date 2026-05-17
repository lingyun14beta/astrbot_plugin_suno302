"""
插件配置管理。

AstrBot 在实例化插件时，若插件目录存在 _conf_schema.json，
会将解析好的 AstrBotConfig 作为第二个参数 config 传入 __init__。
AstrBotConfig 继承自 dict，直接用 .get() 读取即可。

Schema 结构（对应 _conf_schema.json）：
    config["api_key"]                      -> str
    config["default_model"]                -> str
    config["poll_config"]["max_poll"]      -> int
    config["poll_config"]["poll_interval"] -> int
"""

_DEFAULTS: dict = {
    "api_key": "",
    "default_model": "chirp-crow",
    "max_poll": 40,
    "poll_interval": 5,
}

_config: dict = {}


def init(config: dict | None) -> None:
    """由 Main.__init__(context, config) 调用，保存 config 引用。"""
    global _config
    _config = config if isinstance(config, dict) else {}


def api_key() -> str:
    return str(_config.get("api_key", _DEFAULTS["api_key"])).strip()


def default_model() -> str:
    return str(_config.get("default_model", _DEFAULTS["default_model"])).strip()


def enable_llm_tool() -> bool:
    return bool(_config.get("enable_llm_tool", False))


def poll_params() -> tuple[int, int]:
    poll_cfg: dict = _config.get("poll_config", {}) or {}
    return (
        int(poll_cfg.get("max_poll", _DEFAULTS["max_poll"])),
        int(poll_cfg.get("poll_interval", _DEFAULTS["poll_interval"])),
    )
