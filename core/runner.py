import uuid
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import cachetools
from icecream import ic

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


async def scrape_price_url(target_url: str):
    global response_cache
    request_id = ic(str(uuid.uuid4()))
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(extra_http_headers={header_identifier: request_id})
        page = await context.new_page()
        page.on("response", intercept_response)
        await page.goto(target_url)
        await page.wait_for_load_state(wait_action)
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
