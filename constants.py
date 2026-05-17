"""公共常量，避免各模块重复定义。"""

# clip 级别完成状态
# 302.AI 实测返回 "SUCCESS"，API 文档写 "complete"，两者都兼容
CLIP_COMPLETE: frozenset[str] = frozenset({"complete", "SUCCESS"})

# 任务整体状态
TASK_SUCCESS = "SUCCESS"
TASK_FAILED = "FAILED"
CLIP_ERROR = "error"
