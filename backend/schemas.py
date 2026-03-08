from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    platform: str = Field(pattern="^(sub2api|cliproxy)$")
    base_url: str
    email: str | None = None
    password: str


class AccountActionRequest(BaseModel):
    account_id: int | None = None
    delete_name: str | None = None
    model_id: str = "gpt-5.4"


class DuplicateDeleteRequest(BaseModel):
    keys: list[str] = Field(default_factory=list)


class BulkDeleteItem(BaseModel):
    account_id: int | None = None
    delete_name: str | None = None


class BatchHealthCheckRequest(BaseModel):
    model_id: str = "gpt-5.4"
    items: list[BulkDeleteItem] = Field(default_factory=list)


class BulkDeleteRequest(BaseModel):
    items: list[BulkDeleteItem] = Field(default_factory=list)
