"""
FastAPI 应用工厂。

创建并配置 FastAPI 应用实例，注册路由和中间件。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.routes import router as api_router
from app.core.config import settings


def create_app() -> FastAPI:
    """创建并返回配置好的 FastAPI 应用实例。"""
    app = FastAPI(
        title=settings.APP_TITLE,
        description="AI 辅助剧本创作工具 — 将小说自动转换为结构化 YAML 剧本",
        version="1.0.0",
    )

    # ── 根路径：返回前端页面 ──
    @app.get("/", response_class=HTMLResponse)
    async def root():
        index_path = Path("static/index.html")
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        return HTMLResponse(content=settings.APP_TITLE)

    # ── 注册 API 路由 ──
    app.include_router(api_router)

    return app


# 创建全局应用实例
app = create_app()
