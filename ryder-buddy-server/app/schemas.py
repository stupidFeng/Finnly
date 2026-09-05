"""API 请求/响应模型。"""
from datetime import datetime

from pydantic import BaseModel, Field


# ---------- auth ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class JoinRequest(BaseModel):
    invite_code: str
    display_name: str = Field(default="家人", max_length=32)


class TokenResponse(BaseModel):
    token: str
    role: str
    display_name: str


class NewMemberRequest(BaseModel):
    display_name: str = Field(max_length=32)


class InviteResponse(BaseModel):
    invite_code: str


# ---------- family ----------
class MemoryProfile(BaseModel):
    """记忆档案——与 App 端 MemoryProfile 字段保持一致"""

    nickname: str = ""
    birthDate: str = ""
    heightWeight: str = ""
    likes: str = ""
    fears: str = ""
    routine: str = ""
    familyTitles: str = ""
    comfortKit: list[str] = []


class PersonaConfig(BaseModel):
    """莱德人设：说话方式 / 安全红线等，父亲可任意改"""

    characterName: str = "莱德队长"
    speakingStyle: str = ""
    safetyRules: str = ""
    catchphrase: str = "没有困难的任务，只有勇敢的狗狗！"
    extraPrompt: str = ""


class ProviderKeyRequest(BaseModel):
    provider: str = Field(pattern="^(llm|tts|asr)$")
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    voice: str = ""  # TTS 音色：克隆音色 URI 或预设音色名


class ProviderKeyMasked(BaseModel):
    provider: str
    base_url: str
    model: str
    api_key_masked: str
    voice: str = ""
    updated_at: datetime


# ---------- history ----------
class ChatLogItem(BaseModel):
    id: int
    member_name: str
    user_text: str
    reply_text: str
    source: str
    created_at: datetime


class ChatLogPage(BaseModel):
    items: list[ChatLogItem]
    total: int


# ---------- chat ----------
class ChatTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class MemberBrief(BaseModel):
    id: int
    display_name: str
    role: str
