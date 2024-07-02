import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

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
    rental_details: dict = field(default_factory=dict)


def parse_property_link(extracted_property_link: str, base_url: str):
    parsed_url = urlparse(extracted_property_link)
    if parsed_url.scheme not in ["http", "https"]:
        return f'{base_url}{extracted_property_link}'
    return extracted_property_link


async def extract_from_tiles(property_page_tiles, base_url: str) -> list[Property]:
    tile_properties = []
    for property_page_tile in property_page_tiles:
        extracted = await extract_property_details_from_tiles(base_url, property_page_tile)
        tile_properties.append(extracted)

    return tile_properties


async def extract_property_details_from_tiles(base_url, property_page_tile):
    title = property_page_tile.select('span.h3.media-heading').pop().text
    extracted = Property(title)
    extracted.property_url = parse_property_link(property_page_tile.get("href"), base_url.removesuffix("/properties"))
    extracted.photo_url = property_page_tile.find("img").get("src")
    extracted.amenities = [z.get("data-original-title") for z in
                           property_page_tile.find_all("span", {"class": ["amenity-list-item"]})]
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
    return extracted


def extract_amenities(amenities_parent) -> list[str]:
    amenities = [z.text if z.get("data-original-title") is None else z.get("data-original-title") for z in
                 amenities_parent.find_all("span", {"class": ["amenity-list-item"]})]
    return list(map(extract_amenity, amenities))


def extract_amenity(amenity_text: str) -> str:
    replacements = [
        ("\n", ""),
        (",", "")
    ]
    [amenity_text := amenity_text.replace(a, b) for a, b in replacements]
    return amenity_text.strip()


def extract_size(size_div) -> dict[str, str]:
    elements_text = []
    for element in size_div.children:
        size_detail_line = element.text.strip()
        numbers = re.findall(r'\d+', size_detail_line)
        if len(numbers) == 0:
            continue
        elements_text.append(int(max(numbers)))
    return elements_text


async def extract_from_list(property_page_list, base_url) -> list[Property]:
    list_properties = []
    if len(property_page_list) == 0:
        return list_properties

    property_list_rows = property_page_list[0].find_all("div", {"class": "row"})
    for property_list_row in property_list_rows:
        sections = property_list_row.find_all("div")
        if len(sections) == 0:
            continue
        extracted = await extract_property_details_from_list(base_url, sections)
        list_properties.append(extracted)
    return list_properties


async def extract_property_details_from_list(base_url, sections) -> Property:
    extracted = Property()
    link_section = sections[0]
    description_section = sections[1]
    if link_section is not None:
        photo_link = link_section.find("img", {"class": "media-object"})
        if photo_link is not None:
            extracted.photo_url = photo_link.get("src")
        header = link_section.find("h2", {"class": "media-heading"})
        if header is not None:
            title_link = header.find("a")
            extracted.title = title_link.text
            extracted.property_url = parse_property_link(title_link.get("href"), base_url.removesuffix("/properties"))
    extracted.amenities = extract_amenities(description_section)
    extracted_size = extract_size(description_section.find("div", {"class": "amenity-summary-size"}))
    if len(extracted_size) > 0:
        extracted.bedrooms = extracted_size[0]
    if len(extracted_size) > 1:
        extracted.bathrooms = extracted_size[1]
    if len(extracted_size) > 3:
        extracted.sleeps = extracted_size[3]
    return extracted


async def extract_properties(page_contents, base_url: str) -> list[Property]:
    extracted_properties = []
    soup = BeautifulSoup(page_contents, "html.parser")
    property_page_tiles = soup.find_all("a", {"class": ["property-result-tile"]})
    tile_properties = await extract_from_tiles(property_page_tiles, base_url)
    if len(tile_properties) > 0:
        extracted_properties.extend(tile_properties)
    property_page_list = soup.find_all("div", {"class": ["property-result-list"]})
    list_properties = await extract_from_list(property_page_list, base_url)
    if len(list_properties) > 0:
        extracted_properties.extend(list_properties)
        return extracted_properties
    return extracted_properties


async def extract_paged_properties(page, base_url: str) -> list[Property]:
    properties = []
    page_contents = await page.content()
    soup = BeautifulSoup(page_contents, "html.parser")
    property_pager_links = soup.find_all("a", {"class": ["result-page"]})
    if len(property_pager_links) == 0:
        properties.extend(await extract_properties(page_contents, base_url))
        return properties

    for page_id in set(parsed_property_ids(property_pager_links)):
        if page_id == 0:
            continue
        url_to_visit = f'{base_url}?page={page_id}'
        await page.goto(url_to_visit)
        await page.wait_for_load_state(wait_action)
        page_contents = await page.content()
        properties.extend(await extract_properties(page_contents, base_url))
    return properties


def parsed_property_ids(property_pager_links) -> list[int]:
    link_ids = []
    for link_id in [z.get("data-page") for z in property_pager_links]:
        try:
            link_ids.append(int(link_id))
        except ValueError:
            ic(f"{link_id} not an integer")
    return link_ids
