import time
import requests
import logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
from sqlalchemy.orm import Session
from models import Article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}
URL = "https://habr.com/ru/feed/"


def clean_int(text: str) -> int:
    if not text: return 0
    text = text.upper().replace('K', '000').replace(',', '').replace('.', '')
    digits = ''.join(filter(str.isdigit, text))
    return int(digits) if digits else 0


def parse_habr(db: Session):
    try:
        response = requests.get(URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Ошибка сети при получении ленты: {e}")
        return {"status": "error", "message": str(e)}

    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.find_all("article")

    added_count = 0

    for article in articles:
        try:
            post_id = article.get("id")
            if not post_id:
                continue

            if db.query(Article).filter(Article.post_id == post_id).first():
                continue

            title_tag = article.find(["h1", "h2"], class_=lambda c: c and "tm-title" in c)
            title = title_tag.text.strip() if title_tag else "Без заголовка"

            title_link = title_tag.find("a") if title_tag else None
            read_more_link = article.find("a", class_=lambda c: c and "readmore" in c)

            final_content = ""
            main_image = None

            if read_more_link and title_link:
                href = title_link.get("href")
                full_url = urljoin("https://habr.com", href)

                try:
                    time.sleep(1)
                    full_resp = requests.get(full_url, headers=HEADERS, timeout=10)
                    full_resp.raise_for_status()

                    full_soup = BeautifulSoup(full_resp.text, "html.parser")
                    body_tag = full_soup.find("div", {"id": "post-content-body"})

                    if body_tag:
                        for img in body_tag.find_all("img"):
                            img_url = (
                                    img.get("data-src") or
                                    img.get("src") or
                                    (img.get("srcset").split(",")[0].split(" ")[0] if img.get("srcset") else None)
                            )

                            if img_url:
                                img_url = urljoin("https://habr.com", img_url)
                                if not main_image:
                                    main_image = img_url

                                img.replace_with(f"\n\n*\\{img_url}\\*\n\n")

                        lines = []

                        # Все возможные теги с инфой
                        valid_tags = ['p', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'pre', 'figure', 'blockquote']

                        for element in body_tag.find_all(valid_tags):
                            if element.name in ['ul', 'ol']:
                                for li in element.find_all('li'):
                                    lines.append(f"• {li.get_text(strip=True)}")
                            else:
                                text = element.get_text(strip=True)
                                if text:
                                    lines.append(text)

                        if lines:
                            final_content = "\n\n".join(lines)
                        else:
                            # Если что то новое придумают
                            final_content = body_tag.get_text(separator="\n\n", strip=True)

                    logger.info(f"Успешно спарсена полная статья: {post_id}")
                except Exception as e:
                    logger.error(f"Ошибка при парсинге расширенной версии {post_id}: {e}")
                    continue
            else:
                body_tag = article.find("div", class_=lambda c: c and "article-formatted-body" in c)
                if body_tag:
                    for img in body_tag.find_all("img"):
                        img_url = img.get("src") or img.get("data-src")
                        if img_url:
                            if not main_image: main_image = img_url
                            img.replace_with(f" *\\{img_url}\\* ")

                    final_content = body_tag.get_text(separator="\n\n", strip=True)

            # Статистика поста
            votes_tag = article.find("span", class_=lambda c: c and "tm-votes-lever__score-counter" in c)
            votes_count = votes_tag.text.strip() if votes_tag else "0"

            comments_link = article.find("a", class_=lambda c: c and "article-comments-counter-link" in c)
            comments_count = 0
            if comments_link:
                val_span = comments_link.find("span", class_="value")
                if val_span: comments_count = clean_int(val_span.text)

            bookmarks_btn = article.find("button", class_=lambda c: c and "bookmarks-button" in c)
            bookmarks_count = 0
            if bookmarks_btn:
                counter_span = bookmarks_btn.find("span", class_="counter")
                if counter_span: bookmarks_count = clean_int(counter_span.text)

            # Сохранение в БД
            new_article = Article(
                post_id=post_id,
                title=title,
                content=final_content,
                image_url=main_image,
                comments_count=comments_count,
                votes_count=votes_count,
                bookmarks_count=bookmarks_count
            )
            db.add(new_article)
            added_count += 1

        except Exception as e:
            logger.error(f"Критическая ошибка на посте {article.get('id')}: {e}")
            continue

    db.commit()
    return {"status": "success", "added": added_count}