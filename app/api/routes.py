"""
API 路由定义。

提供 RESTful 接口：
- POST /api/convert — 小说文本转剧本
- POST /api/upload — 上传并解析文件（.docx / .txt）
- GET  /api/schema  — 获取 Schema 定义
- GET  /api/providers — 获取支持的模型提供商列表
- GET  /api/sample-novel — 获取示例小说
- GET  /api/health — 健康检查
"""

import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.converter import convert_novel_to_screenplay, PROVIDERS
from app.services.file_parser import extract_text_from_docx_bytes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ── 请求 / 响应模型 ────────────────────────────────────


class ConvertRequest(BaseModel):
    """转换请求体。"""
    novel_text: str = Field(..., min_length=1, description="待转换的小说文本")
    temperature: float = Field(0.3, ge=0, le=1, description="生成温度")
    max_tokens: int = Field(8192, ge=256, le=32768, description="最大输出 token")
    provider: str | None = Field(None, description="模型提供商，不传则用服务器默认配置")
    api_key: str | None = Field(None, description="用户自己的 API Key")
    model: str | None = Field(None, description="模型名称，不传则用对应提供商的默认模型")


class ConvertResponse(BaseModel):
    """转换响应体。"""
    success: bool
    data: dict | None = None
    yaml_text: str | None = None
    error: str | None = None
    stats: dict | None = None
    api_source: str | None = None


# ── 接口 ───────────────────────────────────────────────


@router.post("/convert", response_model=ConvertResponse)
async def convert(req: ConvertRequest):
    """
    将小说文本转换为结构化 YAML 剧本。

    支持多模型提供商：
    - 不传 provider/api_key 时，使用服务器配置的 DeepSeek
    - 传入 provider + api_key 时，使用用户自己的 API Key

    **请求示例：**
    ```json
    {
      "novel_text": "第一章...",
      "provider": "deepseek",
      "api_key": "sk-xxx",
      "model": "deepseek-chat",
      "temperature": 0.3
    }
    ```
    """
    if not req.novel_text.strip():
        raise HTTPException(status_code=400, detail="小说文本不能为空")

    try:
        screenplay = convert_novel_to_screenplay(
            req.novel_text,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            provider=req.provider,
            api_key=req.api_key,
            model=req.model,
        )

        data = screenplay.model_dump(mode="json")

        yaml_text = yaml.dump(
            data,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
        )

        total_scenes = sum(len(act["scenes"]) for act in data.get("acts", []))
        total_events = sum(
            len(scene.get("events", []))
            for act in data.get("acts", [])
            for scene in act.get("scenes", [])
        )

        api_source = "用户自选" if req.provider else "服务器默认"

        return ConvertResponse(
            success=True,
            data=data,
            yaml_text=yaml_text,
            api_source=api_source,
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


@router.get("/providers")
async def get_providers():
    """返回支持的模型提供商列表，供前端选择。"""
    return {
        "success": True,
        "providers": {
            key: {
                "name": info["name"],
                "default_model": info["default_model"],
            }
            for key, info in PROVIDERS.items()
        },
    }


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    上传并解析文件内容。

    支持格式：
    - .txt — 直接返回文本内容
    - .docx — 提取段落和表格文本

    返回解析后的纯文本，供前端填入编辑器。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    ext = Path(file.filename).suffix.lower()

    try:
        data = await file.read()

        if ext == ".docx":
            text = extract_text_from_docx_bytes(data)
        elif ext == ".txt":
            text = data.decode("utf-8")
        elif ext == ".md":
            text = data.decode("utf-8")
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {ext}，仅支持 .txt / .docx / .md",
            )

        if not text.strip():
            raise HTTPException(status_code=400, detail="文件内容为空")

        return {"success": True, "text": text, "filename": file.filename, "length": len(text)}

    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码不是 UTF-8，请使用 .docx 格式")
    except Exception as e:
        logger.exception("文件解析失败")
        raise HTTPException(status_code=500, detail=f"文件解析失败: {e}")


@router.get("/schema")
async def get_schema():
    """返回剧本 YAML Schema 定义。"""
    try:
        with open("schema.yaml", "r", encoding="utf-8") as f:
            content = f.read()
        data = yaml.safe_load(content)
        return {"success": True, "data": data, "yaml_text": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="schema.yaml 文件未找到")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sample-novel")
async def get_sample_novel():
    """返回示例小说文本。"""
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
        "providers_available": list(PROVIDERS.keys()),
    }
