import urllib
from dataclasses import dataclass, field
import re
from urllib.parse import urlencode, urlparse

from bs4 import BeautifulSoup
from icecream import ic

ic.configureOutput(prefix='|> ')


@dataclass
class ReviewUrlParameters:
    min: int = 0
    max: int = 0
    uri: str = None
    path: str = None
    query_string: dict = field(default_factory=dict)


@dataclass
class Review:
    title: str = None
    reviewer_name: str = None
    property_name: str = None
    date_line: str = None
    content: str = None
    response: str = None
    stars: int = 0


def extract_partial_links(paged_reviews) -> list[str]:
    partial_links = []
    for review_element in paged_reviews:
        possible_links = review_element.find_all("a")
        for possible_link in possible_links:
            partial_links.append(possible_link.get("href"))
    return partial_links


def build_url(base_url: str, review_params: ReviewUrlParameters, page_index: int) -> str:
    review_params.query_string["pagenumber"] = page_index
    return f'{base_url}{review_params.path}?{urlencode(review_params.query_string)}'


def extract_review_page_links(iframe_content: str, base_url: str) -> list[str]:
    review_paged_links = []
    soup = BeautifulSoup(iframe_content, "html.parser")
    review_pager = soup.find_all("div", {"class": ["reviews-pager"]})
    if len(review_pager) == 0:
        return review_paged_links

    review_params = get_review_link_parameters(review_pager)
    for page_index in range(review_params.min, review_params.max + 1):
        review_paged_links.append(build_url(base_url, review_params, page_index))

    return review_paged_links


def get_review_link_parameters(review_pager) -> ReviewUrlParameters:
    extracted = ReviewUrlParameters()
    for partial_link in extract_partial_links(review_pager):
        parsed_uri = urlparse(partial_link.lower())
        if not parsed_uri.path.endswith("getreviews"):
            continue
        query_parts = urllib.parse.parse_qsl(parsed_uri.query)
        extracted_params = {}
        for query_part in query_parts:
            key = query_part[0]
            value = query_part[1]
            if key == "pagenumber":
                target_page = int(value)
            extracted_params[key] = value
        extracted.min = target_page if target_page < extracted.min else extracted.min
        extracted.max = target_page if target_page > extracted.max else extracted.max
        extracted.query_string = extracted_params
        extracted.uri = parsed_uri
        extracted.path = parsed_uri.path
    extracted.min = 1 if extracted.max > 0 else extracted.min
    return extracted


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
    review_property = None

    stay_line = date_split[1].split(" in ")
    if len(stay_line) > 1:
        review_date = stay_line[1].strip()
        review_property = stay_line[0].split(" at ")[1].strip()
    else:
        review_date = stay_line[0].replace("stayed", "").replace("   ", "").strip()

    return review_date, reviewer_name, review_property


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
            review_data.date_line, review_data.reviewer_name, review_data.property_name = extract_from_date_line(date_line)
        content_items = review_html.find("div", {"class": ["has-read-more"]}).children
        if content_items is not None:
            review_data.content, review_data.response = extract_from_content_line(content_items)
    except Exception as e:
        ic(e)
    return review_data
