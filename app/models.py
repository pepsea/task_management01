from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, StringConstraints, field_validator, model_validator

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


class TaskCreate(BaseModel):
    area: NonEmptyStr
    related: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    title: NonEmptyStr
    start_at: str
    due_at: str
    priority: Priority
    done: bool = False
    idea_id: Optional[int] = None

    @field_validator("start_at", "due_at")
    @classmethod
    def validate_datetimes(cls, value):
        return check_datetime(value)

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

    @field_validator("start_at", "due_at")
    @classmethod
    def validate_datetimes(cls, value):
        return check_datetime(value)


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
    created_at: str
    updated_at: str


class IdeaCreate(BaseModel):
    title: NonEmptyStr
    body: str = ""


class IdeaUpdate(BaseModel):
    title: Optional[NonEmptyStr] = None
    body: Optional[str] = None


class IdeaOut(BaseModel):
    id: int
    title: str
    body: str
    created_at: str
    updated_at: str
    task_count: int


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
