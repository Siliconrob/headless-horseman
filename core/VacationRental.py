import json

from async_lru import alru_cache
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


@alru_cache(ttl=3600)
async def extract_vacation_rental(property_page_url: str) -> list[dict]:
    parsed_results = []
    if property_page_url is None or property_page_url == "":
        return parsed_results
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(property_page_url)
        page_contents = await page.content()
        soup = BeautifulSoup(page_contents, "html.parser")
        json_lds = soup.find_all("script", {"type": ["application/ld+json"]})
        parsed_results = []
        for json_ld in json_lds:
            data = json.loads(json_ld.text)
            json_ld_type = data.get('@type', None)
            if json_ld_type is None or json_ld_type.lower() != "VacationRental".lower():
                continue
            parsed_results.append(data)
        await browser.close()
    return parsed_results
