from pydantic import BaseModel, HttpUrl


class URLBase(BaseModel):
    # This ensures the input URL is a valid HTTP or HTTPS URL
    original_url: HttpUrl


class URLCreate(URLBase):
    pass


class URL(URLBase):
    id: int
    short_code: str
    visits: int

    class Config:
        # This is required to make Pydantic models compatible with SQLAlchemy ORM
        from_attributes = True



class URLDelete(BaseModel):
    count_items_deleted : int

class ShortURLResponse(BaseModel):
    short_url: str
