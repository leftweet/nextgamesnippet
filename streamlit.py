import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd # Keep for optional full table display

# --- Configuration: MLB Teams Data ---
# This dictionary maps display names to a tuple: (3-letter_abbr, url_friendly_name_part)
# You might need to verify/update these if CBS Sports changes its URL structure
# or for specific teams.
MLB_TEAMS = {
    "Arizona Diamondbacks": ("ARI", "arizona-diamondbacks"),
    "Atlanta Braves": ("ATL", "atlanta-braves"),
    "Baltimore Orioles": ("BAL", "baltimore-orioles"),
    "Boston Red Sox": ("BOS", "boston-red-sox"),
    "Chicago Cubs": ("CHC", "chicago-cubs"),
    "Chicago White Sox": ("CHW", "chicago-white-sox"),
    "Cincinnati Reds": ("CIN", "cincinnati-reds"),
    "Cleveland Guardians": ("CLE", "cleveland-guardians"), # Formerly Indians
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

# Headers to mimic a browser visit
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def generate_team_url(team_abbr, team_url_name):
    """Generates the CBS Sports schedule URL for a given team."""
    return f"https://www.cbssports.com/mlb/teams/{team_abbr.upper()}/{team_url_name}/schedule/"

def scrape_team_schedule(team_url, team_display_name):
    """
    Scrapes the CBS Sports website for a team's schedule,
    finds the second table with class 'TableBase-table',
    and extracts data from the first row after the header.
    """
    try:
        response = requests.get(team_url, headers=HEADERS, timeout=15) # Increased timeout slightly
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
        # You could add debugging here to print the content of tables[0] if it exists
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
    
    # Expected columns: Date, OPP, Time / TV, Venue, Home Starter, Away Starter
    # Sometimes the structure might vary slightly (e.g., fewer columns for postponed games)
    # We'll try to be somewhat flexible but log if less than 6.
    if len(cells) < 6:
        st.warning(f"Warning: Expected at least 6 data cells in the row for {team_display_name}, but found {len(cells)}. Data might be incomplete.")
        # Pad with "N/A" if cells are missing to avoid IndexError
        while len(cells) < 6:
            cells.append(BeautifulSoup("<td>N/A</td>", "html.parser").td)


    date_val = " ".join(cells[0].get_text(separator=" ", strip=True).split())
    opp_val = " ".join(cells[1].get_text(separator=" ", strip=True).split())
    time_tv_val = " ".join(cells[2].get_text(separator=" ", strip=True).split())
    venue_val = " ".join(cells[3].get_text(separator=" ", strip=True).split())
    
    home_starter_val = " ".join(cells[4].get_text(separator=" ", strip=True).split())
    if not home_starter_val: home_starter_val = "N/A"
        
    away_starter_val = " ".join(cells[5].get_text(separator=" ", strip=True).split())
    if not away_starter_val: away_starter_val = "N/A"

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

# Team selection dropdown
# Sort team names alphabetically for user convenience
sorted_team_names = sorted(MLB_TEAMS.keys())
# Add a placeholder option
options = ["-- Select a Team --"] + sorted_team_names
selected_team_display_name = st.selectbox(
    "Choose an MLB Team:",
    options=options,
    index=0 # Default to the placeholder
)

if selected_team_display_name != "-- Select a Team --":
    team_abbr, team_url_name = MLB_TEAMS[selected_team_display_name]
    target_url = generate_team_url(team_abbr, team_url_name)
    
    st.markdown(f"**Scraping for:** {selected_team_display_name}")
    st.caption(f"URL to be scraped: {target_url}")

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
            
            # Optional: Display the whole table (for context)
            # if st.checkbox(f"Show full scraped table for {selected_team_display_name} (first few rows)", False):
            #     try:
            #         response_for_df = requests.get(target_url, headers=HEADERS, timeout=10)
            #         response_for_df.raise_for_status()
            #         soup_for_df = BeautifulSoup(response_for_df.content, 'html.parser')
            #         all_tables_for_df = soup_for_df.find_all('table', class_='TableBase-table')
            #         if len(all_tables_for_df) >= 2:
            #             df = pd.read_html(str(all_tables_for_df[1]))[0]
            #             st.dataframe(df.head())
            #         else:
            #             st.warning("Could not find the schedule table to display as a dataframe.")
            #     except Exception as e:
            #         st.warning(f"Could not display full table preview: {e}")
        else:
            st.warning(f"Could not retrieve game data for {selected_team_display_name}. Check error messages.")
else:
    st.info("Please select an MLB team from the dropdown above to begin.")


st.markdown("---")
st.caption("Note: Web scraping can be unreliable if the website structure changes. Data from CBS Sports.")
