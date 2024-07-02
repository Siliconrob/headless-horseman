import urllib
import uuid
import pendulum
from price_parser import Price
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import cachetools
from icecream import ic
from urllib.parse import urlparse

from core.Property import extract_paged_properties
from core.Review import Review, parse_review, extract_review_page_links
from async_lru import alru_cache
from parse import parse

from core.VacationRental import extract_vacation_rental

response_cache = cachetools.TTLCache(maxsize=32, ttl=30)
ic.configureOutput(prefix='|> ')

header_identifier = 'X-Forwarded-Host'
wait_action = 'networkidle'
base_target_url = 'https://app.ownerrez.com'


async def intercept_response(current_response):
    global response_cache
    target_request = current_response.request
    if target_request.method == "GET":
        if target_request.url.startswith(f'{base_target_url}/widgets/quote'):
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


def extract_pricing(page_content, target_url):
    parsed_results = {}
    soup = BeautifulSoup(page_content, "html.parser")
    page_cards = soup.find_all("div", {"class": ["card-body"]})
    parsed_results["property"] = extract_property_details({
        "property_img": soup.find("div", {"class": ["card-img-top"]}),
        "property_header": soup.find("h5", {"class": ["card-title"]}),
        "property_location": soup.find("h6", {"class": ["card-subtitle"]}),
    })

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


def extract_property_details(property_elements: dict) -> dict:
    property_details = {}
    if property_elements.get("property_img") is not None:
        div_style = property_elements.get("property_img").get("style")
        result = parse("background-image:url({url});", div_style)
        property_details["image"] = result["url"]
    if property_elements.get("property_header") is not None:
        property_details["title"] = property_elements.get("property_header").text
    if property_elements.get("property_location") is not None:
        property_details["location"] = extract_address(property_elements.get("property_location").text)
    return property_details


def extract_address(address_text: str) -> dict:
    if address_text is None or address_text == "":
        return None
    location_pieces = dict(enumerate(map(str, address_text.split(","))))
    address = {
        "city": location_pieces.get(0).strip() if location_pieces.get(0) is not None else None,
        "state": location_pieces.get(1).strip() if location_pieces.get(1) is not None else None,
        "country": location_pieces.get(2).strip() if location_pieces.get(2) is not None else None,
    }
    return address


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
    use_interceptor = ic(not target_url.startswith("https://booking.ownerrez.com/request"))
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(extra_http_headers={header_identifier: request_id})
        page = await context.new_page()
        if use_interceptor:
            page.on("response", intercept_response)
        await page.goto(target_url)
        await page.wait_for_load_state(wait_action)
        if not use_interceptor:
            page_contents = await page.content()
            response_cache[request_id] = ic(extract_pricing(page_contents, target_url))
        await browser.close()
    return response_cache.get(ic(request_id), default=None)


@alru_cache(ttl=3600)
async def extract_reviews(iframe_content) -> list[Review]:
    parsed_results = []
    soup = BeautifulSoup(iframe_content, "html.parser")
    reviews = soup.find_all("div", {"class": ["review-item"]})
    for review in reviews:
        extracted_review = parse_review(review)
        if extracted_review is not None:
            parsed_results.append(extracted_review)
    return parsed_results


@alru_cache(ttl=3600)
async def scrape_properties_url(target_url: str):
    properties_content = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(target_url)
        await page.wait_for_load_state(wait_action)
        properties_content.extend(await extract_paged_properties(page, target_url))
        for property_element in properties_content:
            property_url = ic(property_element.property_url)
            if property_url is None or property_url == "":
                continue
            await page.goto(property_url)
            property_page_contents = await page.content()
            property_element.rental_details = await extract_vacation_rental(property_page_contents)
        await browser.close()
        ic(f'Extracted properties count {len(properties_content)}')
    return properties_content


@alru_cache(ttl=3600)
async def scrape_reviews_url(target_url: str):
    reviews_content = []
    base_widget_url = f"{base_target_url}/widgets"
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(target_url)
        await page.wait_for_load_state(wait_action)
        review_links_to_visit = []
        for iframe in page.frames:
            if iframe.url.startswith(base_widget_url):
                page_content = await iframe.content()
                review_links_to_visit = extract_review_page_links(page_content, base_target_url)
        for review_link_to_visit in set(review_links_to_visit):
            reviews_in_target_page = await extract_paged_reviews(page, review_link_to_visit)
            reviews_content.extend(reviews_in_target_page)
        await browser.close()
        ic(f'Extracted reviews count {len(reviews_content)}')
    return reviews_content


@alru_cache(ttl=3600)
async def extract_paged_reviews(page, review_link_to_visit) -> list[Review]:
    await page.goto(ic(review_link_to_visit))
    page_content = await page.content()
    return await extract_reviews(page_content)
