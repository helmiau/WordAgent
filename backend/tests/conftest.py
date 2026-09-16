"""仅由 pytest 加载；不影响 main.py 正常启动。"""

import os


# 测试收集会导入 Agent，需提前关闭追踪，避免上传假模型记录。
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGSMITH_TRACING_V2"] = "false"
# 避免宿主环境的 DEBUG=release 等非布尔值干扰测试配置。
os.environ["DEBUG"] = "false"
