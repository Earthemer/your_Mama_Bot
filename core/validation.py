import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

class MamaName(BaseModel):
    name: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Имя для бота 'Твоя Мама'"
    )

    @field_validator('name')
    @classmethod
    def validate(cls, value: Any) -> str:
        if not re.fullmatch(r"[А-Яа-яЁё\s-]+", value):
            raise ValueError("Имя должно состоять только из кириллицы, пробелов и дефисов.")
        return value