# astrbot_plugin_suno302

AstrBot 插件，通过 [302.AI](https://302.ai) 提供的 Suno API 实现 AI 音乐生成。

## 命令

| 命令 | 说明 |
|------|------|
| `/suno help` | 显示帮助 |
| `/suno auto <描述>` | 全自动模式：AI 自动编词+配乐 |
| `/suno inst <描述>` | 纯音乐模式：无人声（别名：`/suno instrumental`） |
| `/suno custom <标题> <风格> [男/女]` | 自定义模式第一步，设置标题和风格；**标题和风格不能含空格** |
| `/suno lyrics <歌词>` | 自定义模式第二步，一次性发完全部歌词 |
| `/suno status <task_id>` | 查询任务状态及音频链接 |

## 安装

1. 将 `astrbot_plugin_suno302` 文件夹放入 AstrBot 的 `data/plugins/` 目录。
2. 重启 AstrBot 或在管理面板重载插件。
3. 进入管理面板 → **插件** → **astrbot_plugin_suno302** → **配置**，填写 API Key。

## 配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `api_key` | 302.AI API Key，格式 `sk-xxxxxxxx` | 空 |
| `default_model` | 默认 Suno 模型（下拉选择） | `chirp-crow` |
| `poll_config.max_poll` | 最大轮询次数 | `40`（最长等待 200 秒） |
| `poll_config.poll_interval` | 轮询间隔（秒） | `5` |

### 可选模型

| 模型名 | 对应版本 |
|--------|----------|
| `chirp-fenix` | Suno v5.5 |
| `chirp-crow` | Suno v5（默认） |
| `chirp-bluejay` | Suno v4.5+ |
| `chirp-auk` | Suno v4.5 |
| `chirp-v4` | Suno v4 |
| `chirp-v3-5` | Suno v3.5 |

### 获取 302.AI API Key

1. 注册 [302.AI](https://302.ai) 账号并充值。
2. 在控制台创建 API Key，复制后填入插件配置。

## 使用示例

**全自动生成：**
```
/suno auto 一首轻快的夏日流行曲，吉他弹唱，女声
```

**纯音乐：**
```
/suno inst epic orchestral battle music with choir
```

**自定义歌词（两步）：**
```
第一步：/suno custom 夏天的风 pop 女
机器人：✅ 已设置
        标题：夏天的风  风格：pop  人声：女
        📝 请用 /suno lyrics <歌词> 发送歌词（支持换行，一次性发完）

第二步：/suno lyrics [Verse]
阳光照耀海面
海风轻轻吹来
[Chorus]
夏天的风啊带走我的烦恼
机器人：🎼 正在生成音乐……
```

**查询任务：**
```
/suno status <task_id>
```

## 注意事项

- 每次生成产出 **1~2 首**（Suno 机制）
- 生成耗时约 **60~120 秒**，发送命令后会先收到"正在生成"提示
- 生成结果以**音频链接**形式返回，点击链接可在浏览器播放或下载
- 生成的文件 **14 天**后自动删除，请及时保存
- `/suno custom` 的标题和风格**不能含空格**（AstrBot 以空格切分参数）

## 项目结构

```
astrbot_plugin_suno302/
├── main.py             # 命令路由（指令组 /suno）
├── api_client.py       # HTTP 请求封装（submit / fetch），复用 ClientSession
├── poller.py           # 异步轮询任务状态
├── payload_builder.py  # 构造 API 请求体（纯函数）
├── formatter.py        # 结果文本格式化（纯函数）+ HELP_TEXT
├── config_mgr.py       # 配置读取封装
├── constants.py        # 公共常量（CLIP_COMPLETE 等）
├── _conf_schema.json   # AstrBot 配置面板 Schema
├── metadata.yaml       # 插件元信息
└── README.md
```

## License

MIT

---

![Moe Counter](https://count.getloli.com/get/@astrbot_plugin_suno302-lingyun?theme=moebooru)
