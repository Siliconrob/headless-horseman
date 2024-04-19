import re
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from icecream import ic

ic.configureOutput(prefix='|> ')

wait_action = 'networkidle'


@dataclass
class Property:
    title: str = None
    sleeps: int = 0
    bedrooms: int = 0
    bathrooms: int = 0
    full_bathrooms: int = 0
    half_bathrooms: int = 0
    photo_url: str = None
    property_url: str = None
    amenities: list = field(default_factory=list[str])


async def extract_properties(page, base_url: str, page_index: int) -> list[Property]:
    extracted_properties = []
    if (page_index == 0):
        return extracted_properties
    url_to_visit = f'{base_url}?page={page_index}'
    await page.goto(url_to_visit)
    await page.wait_for_load_state(wait_action)
    page_contents = await page.content()
    soup = BeautifulSoup(page_contents, "html.parser")
    property_page_tile = soup.find_all("a", {"class": ["property-result-tile"]})
    for property_page_tile in property_page_tile:
        title = property_page_tile.find("span", {"class": ["h3", "media-heading"]}).text
        extracted = Property(title)
        extracted.property_url = f'{base_url}{property_page_tile.get("href")}'
        extracted.photo_url = property_page_tile.find("img").get("src")
        extracted.amenities = [z.get("data-original-title") for z in property_page_tile.find_all("span", {"class": ["amenity-list-item"]})]
        details_line = property_page_tile.find("span", {"class": ["caption"]}).text.strip()
        numbers = re.findall(r'\d+', details_line)
        values = list(map(int, numbers))
        extracted.sleeps = values[0]
        if len(values) > 1:
            extracted.bedrooms = values[1]
        if len(values) > 2:
            extracted.bathrooms = values[2]
        if len(values) > 3:
            extracted.full_bathrooms = values[3]
        if len(values) > 4:
            extracted.half_bathrooms = values[4]
        extracted_properties.append(extracted)
    return extracted_properties


async def extract_paged_properties(page, base_url: str) -> list[Property]:
    properties = []
    page_contents = await page.content()
    soup = BeautifulSoup(page_contents, "html.parser")
    property_pager_links = soup.find_all("a", {"class": ["result-page"]})
    if len(property_pager_links) == 0:
        return properties

    page_ids = parsed_property_ids(property_pager_links)
    for page_id in page_ids:
        properties.extend(await extract_properties(page, base_url, page_id))
    return properties


def parsed_property_ids(property_pager_links) -> list[int]:
    link_ids = []
    for link_id in [z.get("data-page") for z in property_pager_links]:
        try:
            link_ids.append(int(link_id))
        except ValueError:
            ic(f"{link_id} not an integer")
    return link_ids
