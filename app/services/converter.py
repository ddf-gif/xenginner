"""
AI 小说转剧本服务。

核心业务逻辑：调用 DeepSeek API 将小说文本转换为结构化 YAML 剧本。
使用 OpenAI 兼容 SDK 与 DeepSeek 通信。
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


# ── 系统提示词 ─────────────────────────────────────────
# 精心设计的 prompt，指导 AI 按照 schema.yaml 的规范输出
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
   - 用于：场景切换、环境氛围、时间过渡的描写
   - 不含对话和角色动作的纯叙述性文字

2. **dialogue** — 对话
   - 每个对话事件只包含一位角色的台词
   - 可选的 emotion 字段标注情感（愤怒、低声、苦笑、讽刺等）

3. **action** — 角色动作
   - 描述角色做了什么
   - character 字段可写"众人"表示群体动作

4. **voiceover** — 旁白/心理独白
   - 角色的内心活动、回忆、心理描写
   - 第三人称叙述时 character 写"旁白"

## 转换规则

1. **分幕规则**：按小说章节映射为幕（chapter 1 → act 1），每章内部可拆为多个场景
2. **场景划分**：以地点转移或明显的时间跳跃为界划分场景
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
    """
    从 AI 回复中提取 YAML 内容。

    处理两种情况：
    1. 被 ```yaml ... ``` 代码块包裹
    2. 裸 YAML 文本
    """
    # 尝试提取代码块
    pattern = r"```(?:yaml|yml)?\s*\n?(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        # 取最长的匹配块（通常是主体内容）
        return max(matches, key=len).strip()

    # 没有代码块，尝试直接解析
    # 检查是否以 --- 开头或包含 title: 等 YAML 特征
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
) -> Screenplay:
    """
    将小说文本转换为结构化剧本。

    Args:
        novel_text: 小说文本内容
        temperature: 生成温度 (0-1)，越低越稳定
        max_tokens: 最大输出 token 数，默认使用配置值

    Returns:
        Screenplay: 校验通过的剧本数据模型

    Raises:
        ValueError: AI 返回内容无法解析或校验失败
        ConnectionError: API 调用失败
    """
    if not settings.DEEPSEEK_API_KEY:
        raise ConnectionError(
            "未配置 DEEPSEEK_API_KEY。请创建 .env 文件并填入 API Key。\n"
            "参考 .env.example 文件。"
        )

    client = OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
    )

    # 调用 DeepSeek API
    response = client.chat.completions.create(
        model=settings.DEEPSEEK_MODEL,
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

    # 提取 YAML
    yaml_text = _extract_yaml(raw_text)

    # 解析 YAML
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise ValueError(f"YAML 解析失败: {e}\n\n原始返回:\n{raw_text}")

    if not isinstance(data, dict):
        raise ValueError(f"YAML 根元素应为字典，实际得到 {type(data).__name__}")

    # 校验必填字段
    required = ["title", "characters", "acts"]
    for field in required:
        if field not in data:
            raise ValueError(f"缺少必填字段 '{field}'")

    # 通过 Pydantic 做完整校验
    try:
        screenplay = Screenplay.model_validate(data)
    except Exception as e:
        raise ValueError(f"数据校验失败: {e}\n\n原始数据:\n{json.dumps(data, ensure_ascii=False, indent=2)}")

    logger.info(
        "转换成功: title=%s, characters=%d, acts=%d",
        screenplay.title,
        len(screenplay.characters),
        len(screenplay.acts),
    )
    return screenplay
