import uuid
from playwright.async_api import async_playwright
import cachetools
from icecream import ic

response_cache = cachetools.TTLCache(maxsize=32, ttl=30)
ic.configureOutput(prefix='|> ')


async def intercept_response(current_response):
    global response_cache
    global request_id
    target_request = current_response.request
    if target_request.method == "GET":
        if target_request.url.startswith("https://secure.ownerrez.com/widgets/quote"):
            response_cache[request_id] = ic(await current_response.json())
            return current_response
    return current_response


async def scrape_price_url(target_url: str):
    global response_cache
    global request_id
    request_id = ic(str(uuid.uuid4()))
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        page.on("response", intercept_response)
        await page.goto(target_url)
        await page.wait_for_load_state("networkidle")
        await browser.close()
    return response_cache.get(ic(request_id), default=None)
