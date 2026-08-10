"""Collects DoVA faculty name, title, and bio/practice description from their profile pages."""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REQUEST_DELAY_SEC = 5  # be polite to the department site
HTTP_TIMEOUT_SEC = 15
USER_AGENT = "Mozilla/5.0 (compatible; DovaMatchBot/0.1; +https://github.com/beat755-jung/DovaMatch)"
FACULTY_LISTING_URL = "https://dova.uchicago.edu/people/faculty"


def load_faculty_entries(filename="faculty_list.txt"):
    """Read 'Name,URL' pairs (one per line) from a file in data/."""
    list_path = DATA_DIR / filename
    entries = []
    with open(list_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, url = [part.strip() for part in line.split(",", 1)]
            entries.append((name, url))
    return entries


_BARE_DOMAIN_RE = re.compile(r"^(www\.)?[a-z0-9-]+(\.[a-z0-9-]+)+/?$", re.IGNORECASE)


def _extract_homepage(bio_paragraphs, base_url):
    """Find the professor's external personal/portfolio site linked in their bio, if any.

    Bio text sometimes contains other external links (citations, press mentions).
    Only treat a link as the homepage when its visible text is a bare domain
    (e.g. "lauraletinsky.com"), which is how this site displays personal sites.
    """
    for p in bio_paragraphs:
        for link in p.select("a[href]"):
            href = link["href"]
            if href.startswith("mailto:"):
                continue
            if "dova.uchicago.edu" in href or href.startswith("/"):
                continue
            link_text = link.get_text(strip=True)
            if _BARE_DOMAIN_RE.match(link_text):
                return href
    return ""


def _extract_events(soup):
    """Extract the 'Related Events' block (title, url, date, host, location), if present."""
    events = []
    for row in soup.select("#block-views-block-related-events-block-1 .views-row"):
        link_el = row.select_one("h2 a")
        date_el = row.select_one(".field--name-field-event-date")
        host_el = row.select_one(".field--name-field-event-host")
        location_el = row.select_one(".field--name-field-event-location")
        events.append(
            {
                "title": link_el.get_text(strip=True) if link_el else "",
                "url": (
                    requests.compat.urljoin("https://dova.uchicago.edu", link_el["href"])
                    if link_el
                    else ""
                ),
                "date": date_el.get_text(strip=True) if date_el else "",
                "host": host_el.get_text(strip=True) if host_el else "",
                "location": location_el.get_text(strip=True) if location_el else "",
            }
        )
    return events


def _extract_header_image(soup):
    img_el = soup.select_one(".field--name-field-header-image img")
    if not img_el or not img_el.get("src"):
        return ""
    return requests.compat.urljoin("https://dova.uchicago.edu", img_el["src"])


# Some faculty pages don't have a header image field populated, but a suitable
# portrait/work image is available elsewhere (e.g. the professor's own site).
HEADER_IMAGE_OVERRIDES = {
    "Jason Salavon": "https://salavon.com/site_media/projects/todem/openseaLogo.png",
}


def parse_profile(html, url):
    """Extract name, title, contact info, bio, header image, homepage, and events from a profile page."""
    soup = BeautifulSoup(html, "html.parser")

    name_el = soup.select_one("#block-department2017-page-title h1")
    title_el = soup.select_one(".field--name-field-person-faculty-title")
    email_el = soup.select_one(".field--name-field-person-email a")
    office_el = soup.select_one(".field--name-field-person-office-address")
    teaching_since_el = soup.select_one(".teaching-at")
    bio_paragraphs = soup.select(".field--name-field-paragraph-body p")

    bio = " ".join(
        p.get_text(separator=" ", strip=True) for p in bio_paragraphs
    ).strip()

    name = name_el.get_text(strip=True) if name_el else ""
    image = _extract_header_image(soup) or HEADER_IMAGE_OVERRIDES.get(name, "")

    return {
        "name": name,
        "title": title_el.get_text(strip=True) if title_el else "",
        "url": url,
        "image": image,
        "email": email_el.get_text(strip=True) if email_el else "",
        "office": office_el.get_text(strip=True) if office_el else "",
        "teaching_since": teaching_since_el.get_text(strip=True) if teaching_since_el else "",
        "homepage": _extract_homepage(bio_paragraphs, url),
        "bio": bio,
        "events": _extract_events(soup),
    }


def fetch_category_map(url=FACULTY_LISTING_URL):
    """Map each person's name to their listing category (Faculty, Lecturers, ...).

    Used as a title fallback when a profile page has no faculty-title field set
    (e.g. Mari Eastman, Anna Martine Whitehead) but is still grouped under a
    heading like "Faculty" on the department's people listing page.
    """
    response = requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT_SEC
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    category_map = {}
    for heading in soup.select(".item-list h3"):
        listing = heading.find_next_sibling("ul")
        if not listing:
            continue
        category = heading.get_text(strip=True)
        for link in listing.select("a"):
            category_map[link.get_text(strip=True)] = category
    return category_map


def fetch_profile(url):
    response = requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT_SEC
    )
    response.raise_for_status()
    return parse_profile(response.text, url)


def collect_faculty_data(entries):
    """Fetch and parse profile pages for a list of (name, url) tuples."""
    try:
        category_map = fetch_category_map()
    except requests.RequestException as e:
        print(f"[scraper] failed to fetch listing page for title fallback: {e}")
        category_map = {}

    faculty_data = []
    for name, url in entries:
        try:
            data = fetch_profile(url)
        except requests.RequestException as e:
            print(f"[scraper] failed to fetch '{name}' ({url}): {e}")
            continue
        if not data["title"]:
            data["title"] = category_map.get(data["name"], "")
        faculty_data.append(data)
        time.sleep(REQUEST_DELAY_SEC)
    return faculty_data


def save_faculty_data(faculty_data, filename="faculty_data.json"):
    DATA_DIR.mkdir(exist_ok=True)
    output_path = DATA_DIR / filename
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(faculty_data, f, ensure_ascii=False, indent=2)
    return output_path


if __name__ == "__main__":
    entries = load_faculty_entries()
    data = collect_faculty_data(entries)
    saved_path = save_faculty_data(data)
    print(f"Saved {len(data)} professor records to {saved_path}")
