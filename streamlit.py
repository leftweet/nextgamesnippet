import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd # Keep for optional full table display

# --- Configuration: MLB Teams Data ---
MLB_TEAMS = {
    "Arizona Diamondbacks": ("ARI", "arizona-diamondbacks"),
    "Atlanta Braves": ("ATL", "atlanta-braves"),
    "Baltimore Orioles": ("BAL", "baltimore-orioles"),
    "Boston Red Sox": ("BOS", "boston-red-sox"),
    "Chicago Cubs": ("CHC", "chicago-cubs"),
    "Chicago White Sox": ("CHW", "chicago-white-sox"),
    "Cincinnati Reds": ("CIN", "cincinnati-reds"),
    "Cleveland Guardians": ("CLE", "cleveland-guardians"),
    "Colorado Rockies": ("COL", "colorado-rockies"),
    "Detroit Tigers": ("DET", "detroit-tigers"),
    "Houston Astros": ("HOU", "houston-astros"),
    "Kansas City Royals": ("KC", "kansas-city-royals"),
    "Los Angeles Angels": ("LAA", "los-angeles-angels"),
    "Los Angeles Dodgers": ("LAD", "los-angeles-dodgers"),
    "Miami Marlins": ("MIA", "miami-marlins"),
    "Milwaukee Brewers": ("MIL", "milwaukee-brewers"),
    "Minnesota Twins": ("MIN", "minnesota-twins"),
    "New York Mets": ("NYM", "new-york-mets"),
    "New York Yankees": ("NYY", "new-york-yankees"),
    "Oakland Athletics": ("OAK", "oakland-athletics"),
    "Philadelphia Phillies": ("PHI", "philadelphia-phillies"),
    "Pittsburgh Pirates": ("PIT", "pittsburgh-pirates"),
    "San Diego Padres": ("SD", "san-diego-padres"),
    "San Francisco Giants": ("SF", "san-francisco-giants"),
    "Seattle Mariners": ("SEA", "seattle-mariners"),
    "St. Louis Cardinals": ("STL", "st-louis-cardinals"),
    "Tampa Bay Rays": ("TB", "tampa-bay-rays"),
    "Texas Rangers": ("TEX", "texas-rangers"),
    "Toronto Blue Jays": ("TOR", "toronto-blue-jays"),
    "Washington Nationals": ("WSH", "washington-nationals"),
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def generate_team_url(team_abbr, team_url_name):
    return f"https://www.cbssports.com/mlb/teams/{team_abbr.upper()}/{team_url_name}/schedule/"

def get_starter_info(cell_td):
    """
    Extracts starter information:
    - Tries to get the full name from a player link URL.
    - Preserves stats found in parentheses (e.g., "(W-L, ERA)").
    - Falls back to the cell's text content if no link or if it's "TBD".
    """
    full_name_from_url = None
    stats_text = ""

    # 1. Try to get full name from player link URL
    link_tag = cell_td.find('a')
    if link_tag and link_tag.has_attr('href'):
        player_url_path = link_tag['href']
        # Expected format: /mlb/players/PLAYERID/firstname-lastname/
        path_segments = player_url_path.strip('/').split('/')
        
        if len(path_segments) > 0:
            name_slug = path_segments[-1] # Last segment is firstname-lastname
            # Basic validation
            if '-' in name_slug and all(c.isalnum() or c == '-' for c in name_slug):
                name_parts = name_slug.split('-')
                capitalized_names = [part.capitalize() for part in name_parts]
                full_name_from_url = " ".join(capitalized_names)

    # 2. Get all text parts from the cell, looking for stats
    # .stripped_strings helps get individual text nodes without extra whitespace.
    cell_all_texts = list(cell_td.stripped_strings)
    
    # 3. Find stats (text in parentheses)
    # The stats are often in a separate text node or span after the <a> tag.
    for text_part in cell_all_texts:
        if text_part.startswith("(") and text_part.endswith(")"):
            stats_text = text_part
            break # Assume first parenthetical is the stats

    # 4. Combine name and stats
    if full_name_from_url:
        if stats_text:
            return f"{full_name_from_url} {stats_text}"
        else:
            return full_name_from_url # Return just name if no stats found
    else:
        # If no name from URL (e.g., "TBD" or empty cell), return the joined original cell text.
        original_text = " ".join(cell_all_texts)
        return original_text if original_text else "N/A"


def scrape_team_schedule(team_url, team_display_name):
    try:
        response = requests.get(team_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching URL for {team_display_name}: {team_url}\nDetails: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')
    tables = soup.find_all('table', class_='TableBase-table')

    if not tables:
        st.error(f"No tables with class 'TableBase-table' found on the page for {team_display_name}.")
        return None
    
    if len(tables) < 2:
        st.error(f"Found {len(tables)} table(s) with class 'TableBase-table' for {team_display_name}, but expected at least 2. Cannot find the schedule table.")
        return None

    schedule_table = tables[1]
    tbody = schedule_table.find('tbody')
    if not tbody:
        st.error(f"Could not find a <tbody> in the schedule table for {team_display_name}.")
        return None
    
    first_data_row = tbody.find('tr')
    if not first_data_row:
        st.error(f"No data rows (<tr>) found in the <tbody> of the schedule table for {team_display_name}.")
        return None

    cells = first_data_row.find_all('td')
    
    if len(cells) < 6:
        st.warning(f"Warning: Expected at least 6 data cells in the row for {team_display_name}, but found {len(cells)}. Data might be incomplete.")
        while len(cells) < 6: # Pad with empty td to avoid IndexError
            cells.append(BeautifulSoup("<td></td>", "html.parser").td) # Create an empty td tag

    date_val = " ".join(cells[0].get_text(separator=" ", strip=True).split())
    opp_val = " ".join(cells[1].get_text(separator=" ", strip=True).split())
    time_tv_val = " ".join(cells[2].get_text(separator=" ", strip=True).split())
    venue_val = " ".join(cells[3].get_text(separator=" ", strip=True).split())
    
    # Home Starter & Away Starter using the new helper function
    home_starter_val = get_starter_info(cells[4])
    away_starter_val = get_starter_info(cells[5])

    return {
        "Date": date_val,
        "OPP": opp_val,
        "Time / TV": time_tv_val,
        "Venue": venue_val,
        "Home starter": home_starter_val,
        "Away starter": away_starter_val,
    }

# --- Streamlit App UI ---
st.set_page_config(page_title="MLB Team Schedule Scraper", layout="wide")
st.title("⚾ MLB Team Schedule Scraper")
st.markdown("Select an MLB team and click 'Scrape' to get the next game's info from CBS Sports.")

sorted_team_names = sorted(MLB_TEAMS.keys())
options = ["-- Select a Team --"] + sorted_team_names
selected_team_display_name = st.selectbox(
    "Choose an MLB Team:",
    options=options,
    index=0
)

if selected_team_display_name != "-- Select a Team --":
    team_abbr, team_url_name = MLB_TEAMS[selected_team_display_name]
    target_url = generate_team_url(team_abbr, team_url_name)
    
    st.markdown(f"**Scraping for:** {selected_team_display_name}")
    st.caption(f"URL to be scraped: [{target_url}]({target_url})")

    if st.button(f"Scrape Next Game Info for {selected_team_display_name}"):
        with st.spinner(f"Scraping CBS Sports for {selected_team_display_name} schedule..."):
            game_data = scrape_team_schedule(target_url, selected_team_display_name)

        if game_data:
            st.success(f"Successfully scraped the data for {selected_team_display_name}!")
            st.subheader(f"First Listed Game Details for {selected_team_display_name}:")
            st.markdown(f"**Date:** {game_data['Date']}")
            st.markdown(f"**OPP:** {game_data['OPP']}")
            st.markdown(f"**Time / TV:** {game_data['Time / TV']}")
            st.markdown(f"**Venue:** {game_data['Venue']}")
            st.markdown(f"**Home starter:** {game_data['Home starter']}")
            st.markdown(f"**Away starter:** {game_data['Away starter']}")
        else:
            st.warning(f"Could not retrieve game data for {selected_team_display_name}. Check error messages.")
else:
    st.info("Please select an MLB team from the dropdown above to begin.")

st.markdown("---")
st.caption("Note: Web scraping can be unreliable if the website structure changes. Data from CBS Sports.")
