from sqlalchemy import Column, Integer, String, Text
from database import Base

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(String, unique=True, index=True) # ID статьи на хабре
    title = Column(String)
    content = Column(Text)
    image_url = Column(String, nullable=True)
    comments_count = Column(Integer, default=0)
    votes_count = Column(String) # Строка, т.к. может быть "+1", "-2"
    bookmarks_count = Column(Integer, default=0)