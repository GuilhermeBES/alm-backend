from pydantic import BaseModel


class ItemBase(BaseModel):
    title: str
    description: str | None = None
    completed: bool = False


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    completed: bool | None = None


class Item(ItemBase):
    id: int

    class Config:
        from_attributes = True
