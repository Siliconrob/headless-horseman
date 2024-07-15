import collections.abc
import re

import pendulum
from bs4 import BeautifulSoup
from icecream import ic

ic.configureOutput(prefix='|> ')


def extract_availability(page_contents: str) -> list:
    parsed_results = []
    if page_contents is None or len(page_contents) == 0:
        return parsed_results

    match_date_pattern = r'(?:const|var|let)\s*bookedDates\s*=\s*([^.map;]*)'

    soup = BeautifulSoup(page_contents, "html.parser")
    scripts = soup.find_all("script", {"type": ["text/javascript"]})
    for script in scripts:
        replacements = {'\r': '', '\n': ''}
        pattern = '|'.join(replacements.keys())
        script_text = re.sub(pattern, lambda z: replacements[z.group(0)], script.get_text())
        match = re.search(match_date_pattern, script_text, re.IGNORECASE | re.MULTILINE)
        if match is None:
            continue
        availability_params = ic(match.groups()[0].replace('const bookedDates = ', ''))
        parsed_results.append(compute_availability(availability_params))

    return parsed_results


def compute_availability(availability_params):
    unavailable_dates = get_unavailable_dates(availability_params)
    available_dates = []
    start_date = pendulum.now('UTC').date()
    end_date = pendulum.now('UTC').add(years=2).date()
    date_interval = pendulum.interval(start_date, end_date)
    for date in date_interval:
        if date in unavailable_dates:
            continue
        available_dates.append(date)
    return available_dates


def get_unavailable_dates(availability_params):
    unavailable_dates = []
    try:
        for date_segment in eval(availability_params):
            if isinstance(date_segment, collections.abc.Iterable):
                end_date = ic(pendulum.parse(date_segment.pop()))
                start_date = ic(pendulum.parse(date_segment.pop()))
                date_interval = pendulum.interval(start_date, end_date)
                for date in date_interval:
                    unavailable_dates.append(date.date())
                continue
            unavailable_dates.append(pendulum.parse(date_segment).date())
    except Exception as error:
        ic(error)
    results = list(dict.fromkeys(unavailable_dates))
    return results
