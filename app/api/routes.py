"""
API 路由定义。

提供 RESTful 接口：
- POST /api/convert — 小说文本转剧本
- GET  /api/schema  — 获取 Schema 定义
- GET  /api/sample-novel — 获取示例小说
- GET  /api/health — 健康检查
"""

import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.converter import convert_novel_to_screenplay

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ── 请求 / 响应模型 ────────────────────────────────────


class ConvertRequest(BaseModel):
    """转换请求体。"""
    novel_text: str = Field(..., min_length=1, description="待转换的小说文本")
    temperature: float = Field(0.3, ge=0, le=1, description="生成温度")
    max_tokens: int = Field(8192, ge=256, le=32768, description="最大输出 token")


class ConvertResponse(BaseModel):
    """转换响应体。"""
    success: bool
    data: dict | None = None
    yaml_text: str | None = None
    error: str | None = None
    stats: dict | None = None


# ── 接口 ───────────────────────────────────────────────


@router.post("/convert", response_model=ConvertResponse)
async def convert(req: ConvertRequest):
    """
    将小说文本转换为结构化 YAML 剧本。

    **请求示例：**
    ```json
    {
      "novel_text": "第一章\\n林晓舟把最后一只玻璃杯...",
      "temperature": 0.3
    }
    ```

    **响应示例：**
    ```json
    {
      "success": true,
      "data": { "title": "...", "characters": [...], "acts": [...] },
      "yaml_text": "title: ...\\ncharacters:\\n  ...",
      "stats": { "characters": 5, "acts": 2, "scenes": 4, "events": 140 }
    }
    ```
    """
    if not req.novel_text.strip():
        raise HTTPException(status_code=400, detail="小说文本不能为空")

    if not settings.DEEPSEEK_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="服务未配置 API Key。管理员请创建 .env 文件并设置 DEEPSEEK_API_KEY。",
        )

    try:
        screenplay = convert_novel_to_screenplay(
            req.novel_text,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )

        # 转字典
        data = screenplay.model_dump(mode="json")

        # 生成 YAML 文本
        yaml_text = yaml.dump(
            data,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
        )

        # 统计信息
        total_scenes = sum(len(act["scenes"]) for act in data.get("acts", []))
        total_events = sum(
            len(scene.get("events", []))
            for act in data.get("acts", [])
            for scene in act.get("scenes", [])
        )

        return ConvertResponse(
            success=True,
            data=data,
            yaml_text=yaml_text,
            stats={
                "characters": len(data.get("characters", [])),
                "acts": len(data.get("acts", [])),
                "scenes": total_scenes,
                "events": total_events,
            },
        )

    except ValueError as e:
        logger.warning("转换失败: %s", e)
        return ConvertResponse(success=False, error=str(e))

    except Exception as e:
        logger.exception("转换异常")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}")


@router.get("/schema")
async def get_schema():
    """
    返回剧本 YAML Schema 定义。

    用于前端展示或客户端校验。
    """
    try:
        with open("schema.yaml", "r", encoding="utf-8") as f:
            content = f.read()
        data = yaml.safe_load(content)
        return {
            "success": True,
            "data": data,
            "yaml_text": content,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="schema.yaml 文件未找到")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sample-novel")
async def get_sample_novel():
    """返回示例小说文本（sample_novel.txt）。"""
    sample_path = Path("sample_novel.txt")
    if sample_path.exists():
        text = sample_path.read_text(encoding="utf-8")
        return {"success": True, "text": text}
    return {"success": False, "error": "示例小说文件不存在"}


@router.get("/health")
async def health_check():
    """健康检查接口。"""
    return {
        "status": "ok",
        "app": settings.APP_TITLE,
        "api_configured": bool(settings.DEEPSEEK_API_KEY),
    }
