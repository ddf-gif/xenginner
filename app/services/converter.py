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


# ── 剧本风格预设 ───────────────────────────────────────
# 每种风格使用不同的系统提示词，引导 AI 输出不同侧重点的剧本
PRESETS = {
    "film": {
        "name": "电影剧本",
        "description": "经典电影剧本格式，场景驱动，适合改编为电影",
        "prompt_extra": """
## 风格要求：电影剧本

请以经典电影剧本的节奏感来组织内容：

1. **场景切换**：每个场景应像电影镜头一样有明确的视觉起点和终点
2. **对话精炼**：台词应简洁有力，符合电影对白的节奏
3. **动作描写**：用现在时态描写角色动作，像摄影机记录
4. **情感张力**：标注角色的微表情和潜台词，帮助演员理解
5. **节奏控制**：紧张场景用短句，抒情场景用细腻描写
6. **转场提示**：相邻场景之间如果有时空跳跃，在 stage_direction 中体现

每幕对应电影的一「幕」（Act），建议 3 幕结构：
- 第一幕：建立人物和冲突
- 第二幕：矛盾升级
- 第三幕：高潮与解决
""",
    },
    "tv": {
        "name": "电视剧本",
        "description": "多集/多幕结构，适合改编为电视剧或网剧",
        "prompt_extra": """
## 风格要求：电视剧本

请以电视剧的叙事节奏来组织内容：

1. **多线叙事**：识别小说中的多条故事线，在场景中标注视角
2. **钩子设计**：每幕结尾可以设计悬念钩子（cliffhanger）
3. **节奏明快**：电视剧场景通常较短，建议每章拆分为 3-5 个短场景
4. **对话密度**：电视剧对话量通常大于电影，保留更多精彩对白
5. **角色弧光**：关注角色成长轨迹，在 voiceover 中体现内心变化

每章对应一「集」（Episode），每集内部再分幕：
- 每集 4-6 个场景，确保节奏紧凑
- 场景切换可加入时间标题（如「同日稍后」「次日清晨」）
""",
    },
    "stage": {
        "name": "舞台剧",
        "description": "舞台表演格式，重对话和舞台指示，适合话剧改编",
        "prompt_extra": """
## 风格要求：舞台剧本

请以舞台剧的表现形式来组织内容：

1. **场景集中**：舞台场景变化有限，合并相近地点的事件
2. **舞台指示详细**：每个 stage_direction 应包含灯光、音效、道具提示
3. **对话为主**：舞台剧依赖对白推动，保留所有重要对话
4. **出入场标记**：在 action 中明确标注角色的上场和下场
5. **独白保留**：重要的心理描写可以转化为角色独白（voiceover + character）
6. **幕间暗示**：如果场景间有暗场转换，在 stage_direction 中标注

每幕对应舞台剧的一「幕」：
- 通常 2-3 幕，每幕 2-4 个场景
- 场景间可用「灯光渐暗」「音效过渡」等连接
""",
    },
    "short_video": {
        "name": "短视频脚本",
        "description": "精简快节奏，带时间标注和镜头提示，适合抖音/快手/B站",
        "prompt_extra": """
## 风格要求：短视频脚本

请以短视频的节奏和格式来组织内容：

1. **极度精简**：每个场景不超过 60 秒阅读时长，快速切入重点
2. **开头钩子**：第一个 stage_direction 应设计为抓人眼球的开场画面
3. **节奏紧凑**：对话短促有力，去除所有修饰性废话
4. **画面感**：在 stage_direction 中加入视觉描述（构图、色调、镜头运动）
5. **时间标注**：在 time 字段中使用「0:00 - 0:15」这样的时间码格式
6. **重点突出**：核心台词或反转点用 emotion 标注

每「幕」对应一个短视频（15-60 秒）：
- 每个场景严格控制 3-5 个事件
- 开场即高潮，不要铺垫
- voiceover 可用作出镜旁白
""",
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


def convert_novel_streaming(
    novel_text: str,
    *,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    preset: Optional[str] = None,
):
    """
    流式转换：调用 AI 并将文本块逐个 yield。

    Yields:
        dict: {"type": "chunk", "text": "..."}  — 实时文本片段
        dict: {"type": "done", "data": {...}, "stats": {...}, "yaml": "..."}  — 最终结果
        dict: {"type": "error", "message": "..."}  — 错误信息
    """
    # ── 确定 API 参数 ──
    if api_key and provider:
        prov = PROVIDERS.get(provider)
        if not prov:
            yield {"type": "error", "message": f"不支持的模型提供商: {provider}"}
            return
        base_url = prov["base_url"]
        effective_model = model or prov["default_model"]
        effective_key = api_key
    elif settings.DEEPSEEK_API_KEY:
        base_url = settings.DEEPSEEK_BASE_URL
        effective_model = model or settings.DEEPSEEK_MODEL
        effective_key = settings.DEEPSEEK_API_KEY
    else:
        yield {"type": "error", "message": "未配置 API Key，请在设置中填入"}
        return

    # ── 确定风格预设 ──
    if preset and preset in PRESETS:
        preset_info = PRESETS[preset]
        effective_prompt = SYSTEM_PROMPT + "\n" + preset_info["prompt_extra"]
        preset_name = preset_info["name"]
    else:
        effective_prompt = SYSTEM_PROMPT
        preset_name = "标准"

    logger.info("流式 | model=%s | preset=%s", effective_model, preset_name)

    # ── 创建客户端 ──
    client = OpenAI(api_key=effective_key, base_url=base_url)

    # ── 流式调用 API ──
    try:
        response = client.chat.completions.create(
            model=effective_model,
            messages=[
                {"role": "system", "content": effective_prompt},
                {"role": "user", "content": _build_user_prompt(novel_text)},
            ],
            temperature=temperature,
            max_tokens=max_tokens or settings.MAX_OUTPUT_TOKENS,
            stream=True,
        )
    except Exception as e:
        logger.exception("API 调用失败")
        yield {"type": "error", "message": f"API 调用失败: {e}"}
        return

    full_text = ""
    for chunk in response:
        if chunk.choices and len(chunk.choices) > 0:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                full_text += delta.content
                yield {"type": "chunk", "text": delta.content}

    if not full_text.strip():
        yield {"type": "error", "message": "AI 返回内容为空"}
        return

    # ── 解析 YAML ──
    try:
        yaml_text = _extract_yaml(full_text)
    except ValueError as e:
        yield {"type": "error", "message": f"{e}"}
        return

    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        yield {"type": "error", "message": f"YAML 解析失败: {e}"}
        return

    if not isinstance(data, dict):
        yield {"type": "error", "message": f"YAML 根元素应为字典，实际得到 {type(data).__name__}"}
        return

    # ── 校验必填字段 ──
    required = ["title", "characters", "acts"]
    for field in required:
        if field not in data:
            yield {"type": "error", "message": f"缺少必填字段 '{field}'"}
            return

    try:
        screenplay = Screenplay.model_validate(data)
    except Exception as e:
        yield {"type": "error", "message": f"数据校验失败: {e}"}
        return

    # ── 统计 ──
    total_scenes = sum(len(s.get("scenes", [])) for s in data.get("acts", []))
    total_events = sum(
        len(s.get("events", []))
        for a in data.get("acts", [])
        for s in a.get("scenes", [])
    )
    stats = {
        "characters": len(data.get("characters", [])),
        "acts": len(data.get("acts", [])),
        "scenes": total_scenes,
        "events": total_events,
    }

    logger.info("流式完成: title=%s | stats=%s", screenplay.title, stats)
    yield {"type": "done", "data": data, "stats": stats, "yaml": yaml_text}


def convert_novel_to_screenplay(
    novel_text: str,
    *,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    preset: Optional[str] = None,
) -> Screenplay:
    """
    将小说文本转换为结构化剧本。

    支持多模型提供商：
    - 用户传入 api_key + provider → 使用用户自己的 API Key 和模型
    - 不传则 fallback 到服务器配置（DeepSeek）

    支持多风格预设：
    - film / tv / stage / short_video

    Args:
        novel_text: 小说文本内容
        temperature: 生成温度 (0-1)
        max_tokens: 最大输出 token 数
        provider: 模型提供商（deepseek / kimi / glm / tongyi / doubao）
        api_key: 用户自己的 API Key
        model: 模型名称（不传则用对应 provider 的默认模型）
        preset: 剧本风格（film / tv / stage / short_video）

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

    # ── 确定风格预设 ──
    if preset and preset in PRESETS:
        preset_info = PRESETS[preset]
        effective_prompt = SYSTEM_PROMPT + "\n" + preset_info["prompt_extra"]
        preset_name = preset_info["name"]
    else:
        effective_prompt = SYSTEM_PROMPT
        preset_name = "标准"

    logger.info("使用 %s | model=%s | preset=%s", source, effective_model, preset_name)

    # ── 创建客户端 ──
    client = OpenAI(
        api_key=effective_key,
        base_url=base_url,
    )

    # ── 调用 API ──
    response = client.chat.completions.create(
        model=effective_model,
        messages=[
            {"role": "system", "content": effective_prompt},
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
        "转换成功: title=%s, characters=%d, acts=%d | source=%s | preset=%s",
        screenplay.title,
        len(screenplay.characters),
        len(screenplay.acts),
        source,
        preset_name,
    )
    return screenplay
