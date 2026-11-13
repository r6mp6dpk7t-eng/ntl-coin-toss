
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://nottinghamtouchleagues.co.uk"
LEAGUES_URL = f"{BASE_URL}/leagues/"

OUTPUT_FILE = Path("data/fixtures.json")

HEADERS = {
    "User-Agent": "NTL-Coin-Toss-Fixture-Importer/1.0"
}

DATE_PATTERN = re.compile(
    r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$"
)

TIME_PATTERN = re.compile(
    r"^\d{1,2}:\d{2}$"
)


def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def get_leagues():
    soup = get_page(LEAGUES_URL)
    leagues = []

    for link in soup.select("a[href]"):
        href = urljoin(BASE_URL, link["href"])
        name = link.get_text(" ", strip=True)

        if "/leagues/" not in href:
            continue

        if href.rstrip("/") == LEAGUES_URL.rstrip("/"):
            continue

        if not name or href in [x["url"] for x in leagues]:
            continue

        leagues.append({
            "name": name,
            "url": href
        })

    return leagues


def extract_fixtures(league):
    soup = get_page(league["url"])

    heading = soup.find("h1")
    league_name = (
        heading.get_text(" ", strip=True)
        if heading else league["name"]
    )

    fixtures_heading = soup.find(
        lambda tag: tag.name in ["h2", "h3", "h4"]
        and tag.get_text(" ", strip=True).lower() == "fixtures"
    )

    if not fixtures_heading:
        print(f"No fixtures heading found: {league_name}")
        return []

    table = fixtures_heading.find_next("table")

    if not table:
        print(f"No fixture table found: {league_name}")
        return []

    fixtures = []
    current_date = None

    for row in table.find_all("tr"):
        cells = [
            cell.get_text(" ", strip=True)
            for cell in row.find_all(["td", "th"])
        ]

        if not cells:
            continue

        # Ignore header rows
        if any("team" in cell.lower() for cell in cells[:2]):
            continue

        # Expected columns:
        # Date, Time, Home, Home score, separator,
        # Away score, Away, Referee

        if len(cells) < 7:
            continue

        if DATE_PATTERN.match(cells[0]):
            current_date = cells[0]

        if not current_date:
            continue

        time_index = next(
            (i for i, cell in enumerate(cells)
             if TIME_PATTERN.match(cell)),
            None
        )

        if time_index is None:
            continue

        if len(cells) < time_index + 6:
            continue

        kickoff = cells[time_index]
        team_a = cells[time_index + 1]
        score_a = cells[time_index + 2]
        score_b = cells[time_index + 4]
        team_b = cells[time_index + 5]

        if not team_a or not team_b:
            continue

        completed = bool(score_a or score_b)

        fixtures.append({
            "date": current_date,
            "kickoff": kickoff,
            "teamA": team_a,
            "teamB": team_b,
            "scoreA": score_a or None,
            "scoreB": score_b or None,
            "completed": completed
        })

    return fixtures


def main():
    print("Starting NTL fixture import...")

    leagues = get_leagues()

    if not leagues:
        raise RuntimeError(
            "No league pages found. Import stopped."
        )

    print(f"Found {len(leagues)} league pages.")

    results = []

    for league in leagues:
        print(f"Reading: {league['name']}")

        try:
            fixtures = extract_fixtures(league)

            results.append({
                "name": league["name"],
                "url": league["url"],
                "fixtures": fixtures
            })

            print(f"  Imported {len(fixtures)} fixtures.")

        except Exception as error:
            print(f"  ERROR: {error}")
            raise

    output = {
        "source": LEAGUES_URL,
        "generatedAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "leagueCount": len(results),
        "leagues": results
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    total = sum(
        len(league["fixtures"])
        for league in results
    )

    print("Import complete.")
    print(f"Leagues: {len(results)}")
    print(f"Fixtures: {total}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
