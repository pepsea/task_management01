from datetime import datetime
from urllib.parse import urlsplit
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

DT_FORMAT = "%Y-%m-%dT%H:%M"

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Priority = Literal["high", "mid", "low"]


def check_datetime(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    # strptime は形式が違えば ValueError を出し、Pydantic が 422 に変換する
    datetime.strptime(value, DT_FORMAT)
    if len(value) != 16:
        raise ValueError("日時は YYYY-MM-DDTHH:MM 形式で指定してください")
    return value


class TaskLink(BaseModel):
    url: str
    label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = ""

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        # 画面では href にそのまま入れるので、javascript: などを防ぐため http/https だけを許可する
        value = value.strip()
        parts = urlsplit(value)
        if (
            parts.scheme not in ("http", "https")
            or not parts.netloc
            or any(c.isspace() for c in value)
            or len(value) > 2000
        ):
            raise ValueError("リンクは http:// または https:// で始まる URL にしてください")
        return value


Links = Annotated[list[TaskLink], Field(max_length=20)]


class TaskCreate(BaseModel):
    area: NonEmptyStr
    related: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    title: NonEmptyStr
    start_at: str
    due_at: str
    priority: Priority
    done: bool = False
    idea_id: Optional[int] = None
    memo: Annotated[str, StringConstraints(max_length=10000)] = ""
    # 「今日のタスク」に選んだ日（YYYY-MM-DD）。その日だけ今日のタスクとして強調する
    today_on: Optional[str] = None
    links: Links = []

    @field_validator("start_at", "due_at")
    @classmethod
    def validate_datetimes(cls, value):
        return check_datetime(value)

    @field_validator("today_on")
    @classmethod
    def validate_today_on(cls, value):
        return check_date(value)

    @model_validator(mode="after")
    def due_not_before_start(self):
        if self.due_at < self.start_at:
            raise ValueError("期限は開始日時以降にしてください")
        return self


class TaskUpdate(BaseModel):
    area: Optional[NonEmptyStr] = None
    related: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None
    title: Optional[NonEmptyStr] = None
    start_at: Optional[str] = None
    due_at: Optional[str] = None
    priority: Optional[Priority] = None
    done: Optional[bool] = None
    idea_id: Optional[int] = None
    memo: Optional[Annotated[str, StringConstraints(max_length=10000)]] = None
    today_on: Optional[str] = None
    links: Optional[Links] = None

    @field_validator("start_at", "due_at")
    @classmethod
    def validate_datetimes(cls, value):
        return check_datetime(value)

    @field_validator("today_on")
    @classmethod
    def validate_today_on(cls, value):
        return check_date(value)


class TaskOut(BaseModel):
    id: int
    area: str
    related: str
    title: str
    start_at: str
    due_at: str
    priority: Priority
    done: bool
    idea_id: Optional[int]
    memo: str
    today_on: Optional[str]
    links: list[TaskLink]
    created_at: str
    updated_at: str


TagName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
ColorStr = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]


class TagOut(BaseModel):
    id: int
    name: str
    color: str


class TagUpdate(BaseModel):
    name: Optional[TagName] = None
    color: Optional[ColorStr] = None


class IdeaCreate(BaseModel):
    title: NonEmptyStr
    body: str = ""
    tags: list[TagName] = []


class IdeaUpdate(BaseModel):
    title: Optional[NonEmptyStr] = None
    body: Optional[str] = None
    tags: Optional[list[TagName]] = None
    archived: Optional[bool] = None
    prioritized: Optional[bool] = None


class IdeaReorder(BaseModel):
    # 画面に表示されている順のアイディア ID
    ids: Annotated[list[int], Field(min_length=1)]


class IdeaOut(BaseModel):
    id: int
    title: str
    body: str
    archived_at: Optional[str]
    prioritized: bool
    created_at: str
    updated_at: str
    task_count: int
    tags: list[TagOut]


class BrainstormCreate(BaseModel):
    # 昇格するとそのままアイディアのタイトルになるので、タイトルと同じ制約にする
    text: NonEmptyStr


class BrainstormOut(BaseModel):
    id: int
    text: str
    created_at: str


def check_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    datetime.strptime(value, "%Y-%m-%d")
    if len(value) != 10:
        raise ValueError("日付は YYYY-MM-DD 形式で指定してください")
    return value


def check_time(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    datetime.strptime(value, "%H:%M")
    if len(value) != 5:
        raise ValueError("時刻は HH:MM 形式で指定してください")
    return value


class DecisionCreate(BaseModel):
    title: NonEmptyStr
    date: str
    time: Optional[str] = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value):
        return check_date(value)

    @field_validator("time")
    @classmethod
    def validate_time(cls, value):
        return check_time(value)


class DecisionUpdate(BaseModel):
    title: Optional[NonEmptyStr] = None
    date: Optional[str] = None
    time: Optional[str] = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value):
        return check_date(value)

    @field_validator("time")
    @classmethod
    def validate_time(cls, value):
        return check_time(value)


class DecisionOut(BaseModel):
    id: int
    title: str
    date: str
    time: Optional[str]
    created_at: str
    updated_at: str


MasterName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class MasterNameIn(BaseModel):
    name: MasterName


class MasterOut(BaseModel):
    id: int
    name: str


class AreaOut(MasterOut):
    color: str


class AreaUpdate(BaseModel):
    name: Optional[MasterName] = None
    color: Optional[ColorStr] = None


class ReorderIn(BaseModel):
    # 画面に表示されている順の ID
    ids: Annotated[list[int], Field(min_length=1)]


NoteTitle = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class NoteCreate(BaseModel):
    # タイトルは本文とは別に入力する（空でもよい。画面では「無題」と表示）
    title: NoteTitle = ""
    body: Annotated[str, StringConstraints(max_length=200000)] = ""
    tags: list[TagName] = []
    # メモの日付。省略すると今日
    note_date: Optional[str] = None

    @field_validator("note_date")
    @classmethod
    def validate_note_date(cls, value):
        return check_date(value)


class NoteUpdate(BaseModel):
    title: Optional[NoteTitle] = None
    body: Optional[Annotated[str, StringConstraints(max_length=200000)]] = None
    tags: Optional[list[TagName]] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None
    note_date: Optional[str] = None

    @field_validator("note_date")
    @classmethod
    def validate_note_date(cls, value):
        return check_date(value)


class NoteOut(BaseModel):
    id: int
    title: str
    body: str
    pinned: bool
    archived_at: Optional[str]
    note_date: str
    created_at: str
    updated_at: str
    tags: list[TagOut]


class MarkdownIn(BaseModel):
    blocks: Annotated[list[Annotated[str, StringConstraints(max_length=200000)]], Field(max_length=2000)]


class MarkdownOut(BaseModel):
    html: list[str]
