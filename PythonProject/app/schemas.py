from pydantic import BaseModel
from typing import Optional

class ArticleBase(BaseModel):
    post_id: str
    title: str
    content: str
    image_url: Optional[str] = None
    comments_count: int
    votes_count: str
    bookmarks_count: int

class ArticleResponse(ArticleBase):
    id: int

    class Config:
        from_attributes = True