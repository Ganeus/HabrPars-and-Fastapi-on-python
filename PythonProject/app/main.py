import io
import csv
import logging
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from urllib.parse import urljoin

import models, schemas
from database import engine, get_db, SessionLocal
from parser import parse_habr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Habr Parser: Fastapi  aps")


def scheduled_task():
    db = SessionLocal()
    try:
        logger.info("Автоматический запуск парсинга по расписанию...")
        result = parse_habr(db)
        logger.info(f"Парсинг завершен: {result}")
    except Exception as e:
        logger.error(f"Ошибка в фоновом парсинге: {e}")
    finally:
        db.close()


#планировщик
@app.on_event("startup")
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_task, 'interval', minutes=1)
    scheduler.start()
    logger.info("Планировщик запущен: интервал 1 минут")


#РОУТЫ 
@app.get("/api/articles", response_model=List[schemas.ArticleResponse])
def get_articles(
        search: Optional[str] = Query(None, description="Поиск по заголовку или тексту статьи"),
        skip: int = 0,
        limit: int = 50,
        db: Session = Depends(get_db)
):
    query = db.query(models.Article)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (models.Article.title.ilike(search_filter)) |
            (models.Article.content.ilike(search_filter))
        )

    return query.offset(skip).limit(limit).all()


@app.get("/api/articles/{article_id}", response_model=schemas.ArticleResponse)
def get_single_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return article


@app.get("/api/export/articles")
def export_articles(db: Session = Depends(get_db)):
    articles = db.query(models.Article).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['ID', 'Habr_ID', 'Title', 'Votes', 'Comments', 'Main_Image', 'Content_Preview'])

    for a in articles:
        preview = a.content[:1000].replace('\n', ' ') + "..." if a.content else ""
        writer.writerow([
            a.id,
            a.post_id,
            a.title,
            a.votes_count,
            a.comments_count,
            a.image_url,
            preview
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=habr_articles_export.csv"}
    )


# на всякий случай
@app.post("/parse/")
def trigger_parsing(db: Session = Depends(get_db)):
    return parse_habr(db)
