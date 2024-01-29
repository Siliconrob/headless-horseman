from dataclasses import dataclass
import re

from icecream import ic

ic.configureOutput(prefix='|> ')


@dataclass
class Review:
    title: str = None
    reviewer_name: str = None
    date_line: str = None
    content: str = None
    response: str = None
    stars: int = 0


def extract_text_content(input_text: str):
    if input_text is None or len(input_text) == 0:
        return None
    return input_text.replace("\n", "").strip()


def extract_from_date_line(date_line: str) -> (str, str):
    if date_line is None or len(date_line) == 0:
        return None, None

    date_split = re.split(r',|–', date_line)
    if len(date_split) != 2:
        return None, None

    reviewer_name = date_split[0].replace("By", "").strip()
    review_date = date_split[1].replace("stayed", "").replace("   ", "").strip()

    return review_date, reviewer_name


def extract_from_content_line(content) -> (str, str):
    if content is None:
        return None, None
    review_response = None
    review_content = None
    for index, content_text in enumerate(content):
        review_response = extract_text_content(content_text.text)
        if index == 0:
            review_content = review_response
            review_response = None
    if review_content is not None and review_content == review_response:
        review_response = None
    return review_content, review_response

def parse_review(review_html) -> Review:
    review_data = None
    try:
        review_data = Review()
        review_data.stars = len(review_html.find_all("span", {"class": ["fa-star"]}))
        review_data.title = extract_text_content(review_html.find("span", {"class": ["review-item-title"]}).text)
        date_line = extract_text_content(review_html.find("div", {"class": ["review-item-by-line"]}).text)
        if date_line is not None:
            review_data.date_line, review_data.reviewer_name = extract_from_date_line(date_line)
        content_items = review_html.find("div", {"class": ["has-read-more"]}).children
        if content_items is not None:
            review_data.content, review_data.response = extract_from_content_line(content_items)
    except Exception as e:
        ic(e)
    return review_data
