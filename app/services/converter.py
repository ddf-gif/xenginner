"""
AI 小说转剧本服务。

核心业务逻辑：调用 LLM API 将小说文本转换为结构化 YAML 剧本。
支持多模型提供商（DeepSeek、Kimi、GLM 等），用户可自传 API Key。
"""

import json
import logging
import re
from typing import Optional

import yaml
from openai import OpenAI

from app.core.config import settings
from app.core.models import Screenplay

logger = logging.getLogger(__name__)


# ── 支持的模型提供商 ─────────────────────────────────────
# 均为 OpenAI 兼容 API，可使用同一 SDK 调用
PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "kimi": {
        "name": "Kimi (月之暗面)",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
    },
    "glm": {
        "name": "GLM (智谱清言)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
    "tongyi": {
        "name": "通义千问 (阿里云)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "doubao": {
        "name": "豆包 (火山引擎)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": "ep-20250225155357-abcde",  # 用户需替换为实际接入点
    },
}


# ── 系统提示词 ─────────────────────────────────────────
SYSTEM_PROMPT = """你是一个专业的剧本改编助手。你的任务是将小说文本转换为结构化的 YAML 剧本格式。

## 输出规范

请严格按照以下 YAML 结构输出（只输出 YAML，不要包含多余的解释）：

```yaml
title: "剧本标题"
characters:
  - name: "角色名"
    description: "角色简要描述"
acts:
  - act_number: 1
    scenes:
      - scene_number: 1
        location: "地点"
        time: "时间描述"
        characters_present: ["角色1", "角色2"]
        events:
          - type: "stage_direction"
            description: "环境或氛围描写"
          - type: "dialogue"
            character: "角色名"
            line: "台词内容"
            emotion: "可选的情感标记"
          - type: "action"
            character: "角色名"
            description: "动作描述"
          - type: "voiceover"
            character: "旁白"
            text: "独白或叙述内容"
```

## 事件类型说明

1. **stage_direction** — 舞台指示/环境描写
2. **dialogue** — 对话（可带 emotion 情感标记）
3. **action** — 角色动作
4. **voiceover** — 旁白/心理独白

## 转换规则

1. **分幕规则**：按小说章节映射为幕，每章内部可拆为多个场景
2. **场景划分**：以地点转移或明显的时间跳跃为界
3. **角色提取**：从文本中提取所有有台词或重要行为的角色
4. **情感标记**：只在有明显情感色彩时添加 emotion 字段
5. **叙述转化**：
   - 纯环境/外貌描写 → stage_direction
   - 含"说/道/问/答"等 → dialogue
   - 动作性叙述 → action
   - 心理活动/回忆 → voiceover
6. **语言**：保留原文语言（中文输出中文）

## 质量要求

- 保持原文的文学性和情感张力
- 不遗漏重要情节和对话
- 角色名称保持原文一致
- 每段 stage_direction 不宜过长，适当拆分
"""


def _build_user_prompt(novel_text: str) -> str:
    """构建用户提示词，包含待转换的小说文本。"""
    return f"""请将以下小说文本转换为 YAML 格式的结构化剧本：

---
{novel_text}
---

注意：
1. 如果文本跨越多个章节，每章作为一幕
2. 仔细识别所有角色、场景切换和情节节点
3. 只输出 YAML 内容，不要添加任何额外的文字说明
4. 用 ```yaml ... ``` 包裹 YAML 内容"""


def _extract_yaml(text: str) -> str:
    """从 AI 回复中提取 YAML 内容。"""
    # 尝试提取代码块
    pattern = r"```(?:yaml|yml)?\s*\n?(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return max(matches, key=len).strip()

    # 没有代码块，尝试直接解析
    stripped = text.strip()
    if stripped.startswith("---"):
        return stripped
    if re.search(r"^title:\s*", stripped, re.MULTILINE):
        return stripped

    raise ValueError("AI 返回内容中未找到有效的 YAML 数据")


def convert_novel_to_screenplay(
    novel_text: str,
    *,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Screenplay:
    """
    将小说文本转换为结构化剧本。

    支持多模型提供商：
    - 用户传入 api_key + provider → 使用用户自己的 API Key 和模型
    - 不传则 fallback 到服务器配置（DeepSeek）

    Args:
        novel_text: 小说文本内容
        temperature: 生成温度 (0-1)
        max_tokens: 最大输出 token 数
        provider: 模型提供商（deepseek / kimi / glm / tongyi / doubao）
        api_key: 用户自己的 API Key
        model: 模型名称（不传则用对应 provider 的默认模型）

    Returns:
        Screenplay: 校验通过的剧本数据模型
    """
    # ── 确定 API 参数 ──
    if api_key and provider:
        # 用户指定了 provider 和 key
        prov = PROVIDERS.get(provider)
        if not prov:
            raise ValueError(f"不支持的模型提供商: {provider}，可选: {', '.join(PROVIDERS.keys())}")
        base_url = prov["base_url"]
        effective_model = model or prov["default_model"]
        effective_key = api_key
        source = f"用户自选 ({prov['name']})"
    elif settings.DEEPSEEK_API_KEY:
        # 使用服务器默认配置
        base_url = settings.DEEPSEEK_BASE_URL
        effective_model = model or settings.DEEPSEEK_MODEL
        effective_key = settings.DEEPSEEK_API_KEY
        source = "服务器默认 (DeepSeek)"
    else:
        raise ConnectionError(
            "未配置 API Key。请创建 .env 文件并设置 DEEPSEEK_API_KEY，\n"
            "或在页面设置中填入你自己的 API Key。"
        )

    logger.info("使用 %s | model=%s", source, effective_model)

    # ── 创建客户端 ──
    client = OpenAI(
        api_key=effective_key,
        base_url=base_url,
    )

    # ── 调用 API ──
    response = client.chat.completions.create(
        model=effective_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(novel_text)},
        ],
        temperature=temperature,
        max_tokens=max_tokens or settings.MAX_OUTPUT_TOKENS,
        stream=False,
    )

    raw_text = response.choices[0].message.content
    if not raw_text:
        raise ValueError("AI 返回内容为空")

    # ── 解析 YAML ──
    yaml_text = _extract_yaml(raw_text)

    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise ValueError(f"YAML 解析失败: {e}\n\n原始返回:\n{raw_text[:500]}")

    if not isinstance(data, dict):
        raise ValueError(f"YAML 根元素应为字典，实际得到 {type(data).__name__}")

    # ── 校验 ──
    required = ["title", "characters", "acts"]
    for field in required:
        if field not in data:
            raise ValueError(f"缺少必填字段 '{field}'")

    try:
        screenplay = Screenplay.model_validate(data)
    except Exception as e:
        raise ValueError(f"数据校验失败: {e}")

    logger.info(
        "转换成功: title=%s, characters=%d, acts=%d | source=%s",
        screenplay.title,
        len(screenplay.characters),
        len(screenplay.acts),
        source,
    )
    return screenplay
