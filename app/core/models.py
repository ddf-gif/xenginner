"""
剧本数据模型（Pydantic）。

定义与 schema.yaml 对应的 Python 数据模型，用于：
1. 对 AI 返回结果做结构化校验
2. 提供类型提示和自动补全
3. 序列化为 JSON / YAML 输出
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ── 事件层 ─────────────────────────────────────────────


class DialogueEvent(BaseModel):
    """对话事件：角色之间的对白。"""
    type: str = "dialogue"
    character: str = Field(..., description="说话角色名 [required]")
    line: str = Field(..., description="台词内容 [required]")
    emotion: Optional[str] = Field(None, description="情感标记 [optional]，如'愤怒'、'低声'")


class ActionEvent(BaseModel):
    """动作事件：角色执行的动作。"""
    type: str = "action"
    character: str = Field(..., description="执行动作的角色名 [required]，群体可写'众人'")
    description: str = Field(..., description="动作描述 [required]")


class StageDirectionEvent(BaseModel):
    """舞台指示：环境描写、氛围渲染。"""
    type: str = "stage_direction"
    description: str = Field(..., description="环境或氛围描写 [required]")


class VoiceoverEvent(BaseModel):
    """旁白/画外音/心理独白。"""
    type: str = "voiceover"
    character: Optional[str] = Field("旁白", description="独白所属角色，第三人称叙述写'旁白' [optional]")
    text: str = Field(..., description="独白或叙述内容 [required]")


# 联合类型：任何一个事件类型
ScreenplayEvent = DialogueEvent | ActionEvent | StageDirectionEvent | VoiceoverEvent


# ── 场景层 ─────────────────────────────────────────────


class Scene(BaseModel):
    """场景：特定时间、地点下发生的一系列事件。"""
    scene_number: int = Field(..., description="场景序号，整数 [required]")
    location: str = Field(..., description="地点描述 [required]")
    time: str = Field(..., description="时间描述，如'上午'、'深夜' [required]")
    characters_present: List[str] = Field(..., description="本场景出场角色名列表 [required]")
    events: list = Field(..., description="事件列表，按时间顺序排列 [required]")


# ── 幕层 ───────────────────────────────────────────────


class Act(BaseModel):
    """幕：剧本的大段落，包含多个场景。"""
    act_number: int = Field(..., description="幕序号，整数 [required]")
    scenes: list[Scene] = Field(..., description="场景列表 [required]")


# ── 顶层 ───────────────────────────────────────────────


class Character(BaseModel):
    """角色定义。"""
    name: str = Field(..., description="角色姓名 [required]，作为唯一标识符")
    description: str = Field(..., description="角色简要描述 [required]")


class Screenplay(BaseModel):
    """剧本顶层结构。"""
    title: str = Field(..., description="剧本标题 [required]")
    characters: list[Character] = Field(..., description="角色列表 [required]")
    acts: list[Act] = Field(..., description="幕的列表 [required]")
