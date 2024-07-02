import json

from async_lru import alru_cache
from bs4 import BeautifulSoup


@alru_cache(ttl=3600)
async def extract_vacation_rental(page_contents: str) -> list[dict]:
    parsed_results = []
    if page_contents is None or len(page_contents) == 0:
        return parsed_results

    soup = BeautifulSoup(page_contents, "html.parser")
    json_lds = soup.find_all("script", {"type": ["application/ld+json"]})
    parsed_results = []
    for json_ld in json_lds:
        data = json.loads(json_ld.text)
        json_ld_type = data.get('@type', None)
        if json_ld_type is None or json_ld_type.lower() != "VacationRental".lower():
            continue
        parsed_results.append(data)
    return parsed_results
