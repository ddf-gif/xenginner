"""
应用配置管理。

从环境变量或 .env 文件加载配置项。
敏感信息（如 API Key）通过环境变量注入，不硬编码在代码中。
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── DeepSeek API 配置 ──
    # DeepSeek 提供兼容 OpenAI 的 API，使用相同的 SDK 调用
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ── 应用配置 ──
    APP_TITLE: str = "AI 小说转剧本工具"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # 模型配置
    MAX_INPUT_TOKENS: int = 128000  # DeepSeek 上下文窗口
    MAX_OUTPUT_TOKENS: int = 8192

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# 全局单例
settings = Settings()
