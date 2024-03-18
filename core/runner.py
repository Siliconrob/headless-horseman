import urllib
import uuid

import pendulum
from price_parser import Price
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import cachetools
from icecream import ic
from urllib.parse import urlparse
from core.Review import Review, parse_review

response_cache = cachetools.TTLCache(maxsize=32, ttl=30)
ic.configureOutput(prefix='|> ')

header_identifier = 'X-Forwarded-Host'
wait_action = 'networkidle'


async def intercept_response(current_response):
    global response_cache
    target_request = current_response.request
    if target_request.method == "GET":
        if target_request.url.startswith("https://secure.ownerrez.com/widgets/quote"):
            request_id = ic(await target_request.header_value(header_identifier))
            response_cache[request_id] = ic(await current_response.json())
            return current_response
    return current_response


def extract_table_detail(table_element, table_section_tag: str):
    target_element = table_element.find(table_section_tag)
    if target_element is None:
        return None
    details = {}
    rows = target_element.find_all("tr")
    for row in rows:
        row_cells = row.find_all("td")
        row_detail = []
        for cell in row_cells:
            row_detail.append(cell.text.strip())
        if len(row_detail) == 0:
            continue
        possible_new_key = row_detail[:1]
        if possible_new_key:
            new_value = row_detail[1:]
            new_key = str(possible_new_key.pop()).replace(" ", "_").lower()
            if new_key == "":
                continue
            new_key_value = new_value.pop() if new_value else None
            if new_key_value is None:
                continue
            details[new_key] = {"original_value": new_key_value, "parsed": Price.fromstring(new_key_value).amount}
    return details



async def extract_pricing(page_content, target_url):
    parsed_results = {}
    soup = BeautifulSoup(await page_content, "html.parser")
    page_cards = soup.find_all("div", {"class": ["card-body"]})
    for page_card in page_cards:
        inner_table = page_card.find("table", {"class": ["table"]})
        if inner_table is None:
            continue
        body_details = ic(extract_table_detail(inner_table, "tbody"))
        if body_details is None:
            continue
        footer_details = ic(extract_table_detail(inner_table, "tfoot"))
        if footer_details is None:
            continue
        parsed_results["details"] = body_details
        parsed_results["summary"] = footer_details
        parsed_results["nights"] = get_duration(target_url).days
        first_summary_key = list(footer_details.keys())[:1].pop()
        parsed_results["total"] = footer_details[first_summary_key]['parsed']
        break

    return parsed_results


def get_duration(target_url):
    parsed_uri = urlparse(target_url.lower())
    query_parts = urllib.parse.parse_qs(parsed_uri.query)
    start_date = pendulum.parse(str(query_parts["arrival"].pop()), strict=False)
    end_date = pendulum.parse(str(query_parts["departure"].pop()), strict=False)
    duration = ic(end_date.diff(start_date))
    return duration


async def scrape_price_url(target_url: str):
    global response_cache
    request_id = ic(str(uuid.uuid4()))
    use_interceptor = not target_url.startswith("https://booking.ownerrez.com/request")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(extra_http_headers={header_identifier: request_id})
        page = await context.new_page()
        if use_interceptor:
            page.on("response", intercept_response)
        await page.goto(target_url)
        await page.wait_for_load_state(wait_action)
        if not use_interceptor:
            response_cache[request_id] = ic(await extract_pricing(page.content(), target_url))
        await browser.close()
    return response_cache.get(ic(request_id), default=None)


async def extract_reviews(iframe_content) -> list[Review]:
    parsed_results = []
    soup = BeautifulSoup(await iframe_content.content(), "html.parser")
    reviews = soup.find_all("div", {"class": ["review-item"]})
    for review in reviews:
        extracted_review = parse_review(review)
        if extracted_review is not None:
            parsed_results.append(extracted_review)
    return parsed_results


async def scrape_reviews_url(target_url: str):
    reviews_content = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(target_url)
        await page.wait_for_load_state(wait_action)
        for iframe in page.frames:
            if iframe.url.startswith("https://secure.ownerrez.com/widgets"):
                reviews_content = await extract_reviews(iframe)
        await browser.close()
    return reviews_content
