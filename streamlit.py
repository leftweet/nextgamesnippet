import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import google.generativeai as genai
from datetime import datetime
import re # For parsing time and opponent

# --- Configuration: MLB Teams Data ---
# (Abbr, url_friendly_name, Mascot Name)
MLB_TEAMS = {
    "Arizona Diamondbacks": ("ARI", "arizona-diamondbacks", "Diamondbacks"),
    "Atlanta Braves": ("ATL", "atlanta-braves", "Braves"),
    "Baltimore Orioles": ("BAL", "baltimore-orioles", "Orioles"),
    "Boston Red Sox": ("BOS", "boston-red-sox", "Red Sox"),
    "Chicago Cubs": ("CHC", "chicago-cubs", "Cubs"),
    "Chicago White Sox": ("CHW", "chicago-white-sox", "White Sox"),
    "Cincinnati Reds": ("CIN", "cincinnati-reds", "Reds"),
    "Cleveland Guardians": ("CLE", "cleveland-guardians", "Guardians"),
    "Colorado Rockies": ("COL", "colorado-rockies", "Rockies"),
    "Detroit Tigers": ("DET", "detroit-tigers", "Tigers"),
    "Houston Astros": ("HOU", "houston-astros", "Astros"),
    "Kansas City Royals": ("KC", "kansas-city-royals", "Royals"),
    "Los Angeles Angels": ("LAA", "los-angeles-angels", "Angels"),
    "Los Angeles Dodgers": ("LAD", "los-angeles-dodgers", "Dodgers"),
    "Miami Marlins": ("MIA", "miami-marlins", "Marlins"),
    "Milwaukee Brewers": ("MIL", "milwaukee-brewers", "Brewers"),
    "Minnesota Twins": ("MIN", "minnesota-twins", "Twins"),
    "New York Mets": ("NYM", "new-york-mets", "Mets"),
    "New York Yankees": ("NYY", "new-york-yankees", "Yankees"),
    "Oakland Athletics": ("OAK", "oakland-athletics", "Athletics"),
    "Philadelphia Phillies": ("PHI", "philadelphia-phillies", "Phillies"),
    "Pittsburgh Pirates": ("PIT", "pittsburgh-pirates", "Pirates"),
    "San Diego Padres": ("SD", "san-diego-padres", "Padres"),
    "San Francisco Giants": ("SF", "san-francisco-giants", "Giants"),
    "Seattle Mariners": ("SEA", "seattle-mariners", "Mariners"),
    "St. Louis Cardinals": ("STL", "st-louis-cardinals", "Cardinals"),
    "Tampa Bay Rays": ("TB", "tampa-bay-rays", "Rays"),
    "Texas Rangers": ("TEX", "texas-rangers", "Rangers"),
    "Toronto Blue Jays": ("TOR", "toronto-blue-jays", "Blue Jays"),
    "Washington Nationals": ("WSH", "washington-nationals", "Nationals"),
}

# For reverse lookup of abbreviation to full name and mascot
MLB_TEAMS_BY_ABBR = {details[0]: (name, details[2]) for name, details in MLB_TEAMS.items()}


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- Gemini API Configuration ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest') # or 'gemini-pro'
except KeyError:
    GEMINI_API_KEY = None
    gemini_model = None
    st.error("GEMINI_API_KEY not found in Streamlit secrets. Snippet generation will be disabled.")
except Exception as e:
    GEMINI_API_KEY = None
    gemini_model = None
    st.error(f"Error configuring Gemini API: {e}. Snippet generation will be disabled.")


def generate_team_url(team_abbr, team_url_name):
    return f"https://www.cbssports.com/mlb/teams/{team_abbr.upper()}/{team_url_name}/schedule/"

def get_starter_info(cell_td):
    full_name_from_url = None
    stats_text = ""
    link_tag = cell_td.find('a')
    if link_tag and link_tag.has_attr('href'):
        player_url_path = link_tag['href']
        path_segments = player_url_path.strip('/').split('/')
        if len(path_segments) > 0:
            name_slug = path_segments[-1]
            if '-' in name_slug and all(c.isalnum() or c == '-' for c in name_slug):
                name_parts = name_slug.split('-')
                capitalized_names = [part.capitalize() for part in name_parts]
                full_name_from_url = " ".join(capitalized_names)

    cell_all_texts = list(cell_td.stripped_strings)
    for text_part in cell_all_texts:
        if text_part.startswith("(") and text_part.endswith(")"):
            stats_text = text_part
            break
    if full_name_from_url:
        return f"{full_name_from_url} {stats_text}".strip()
    else:
        original_text = " ".join(cell_all_texts)
        return original_text if original_text else "N/A"

def scrape_team_schedule(team_url, team_display_name):
    # ... (scraping logic remains largely the same) ...
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
        while len(cells) < 6: 
            cells.append(BeautifulSoup("<td></td>", "html.parser").td)

    date_val = " ".join(cells[0].get_text(separator=" ", strip=True).split())
    opp_val_raw = " ".join(cells[1].get_text(separator=" ", strip=True).split()) # Keep raw for processing
    time_tv_val_raw = " ".join(cells[2].get_text(separator=" ", strip=True).split()) # Keep raw
    venue_val = " ".join(cells[3].get_text(separator=" ", strip=True).split())
    
    home_starter_val = get_starter_info(cells[4])
    away_starter_val = get_starter_info(cells[5])

    return {
        "Date": date_val,
        "OPP_raw": opp_val_raw, # Store raw opponent string
        "Time_TV_raw": time_tv_val_raw, # Store raw time/TV string
        "Venue": venue_val,
        "Home_starter": home_starter_val,
        "Away_starter": away_starter_val,
        "Scraped_team_full_name": team_display_name # Add the name of the team we scraped FOR
    }


def format_data_for_gemini_prompt(game_data, selected_team_info):
    """
    Formats the raw scraped game data according to specific rules for the Gemini prompt.
    selected_team_info is a tuple: (abbr, url_name, mascot_name)
    """
    formatted = {}

    # 1. Date: Month and Date only (no year)
    try:
        # Handle dates like "Mon, Mar 25" or "Mar 25, 2024" or "Mar 25"
        date_str = game_data['Date']
        if ',' in date_str:
            date_part = date_str.split(',')[1].strip() # "Mar 25" or "Mar 25 2024"
            if len(date_part.split()) > 2: # e.g. "Mar 25 2024"
                 date_part = " ".join(date_part.split()[:2])
        else: # "Mar 25"
            date_part = date_str

        dt_obj = datetime.strptime(date_part, "%b %d")
        formatted['date'] = dt_obj.strftime("%B %d")
    except ValueError:
        formatted['date'] = game_data['Date'] # Fallback if parsing fails

    # 2. Scraped Team: Mascot name only
    formatted['scraped_team_mascot'] = selected_team_info[2] # Mascot name from MLB_TEAMS

    # 3. Opponent: Full name
    # game_data['OPP_raw'] might be "vs NYM", "@ ATL", "New York Mets"
    opp_raw = game_data['OPP_raw']
    opponent_full_name = opp_raw # Default
    
    # Try to extract abbreviation like "NYM" from "vs NYM" or "@ NYM"
    match = re.search(r'(?:vs\.?|@)\s*([A-Z]{2,3})', opp_raw)
    if match:
        opp_abbr = match.group(1)
        if opp_abbr in MLB_TEAMS_BY_ABBR:
            opponent_full_name = MLB_TEAMS_BY_ABBR[opp_abbr][0] # Full name
    elif opp_raw.isupper() and len(opp_raw) in [2,3] and opp_raw in MLB_TEAMS_BY_ABBR: # e.g. "NYM"
        opponent_full_name = MLB_TEAMS_BY_ABBR[opp_raw][0]
    else: # If it's already a full name or something else, clean it up
        opponent_full_name = opp_raw.replace("vs. ", "").replace("@ ", "").strip()
    formatted['opponent_full_name'] = opponent_full_name

    # Determine if scraped team is home or away for "vs" or "at" phrasing
    # If venue contains scraped team city/name OR "Home", they are home.
    # This is a heuristic and might need refinement.
    # For simplicity, let's check if the opponent string indicates away.
    if "@" in opp_raw:
        formatted['matchup_conjunction'] = "at"
    else: # Assumed "vs" or home game
        formatted['matchup_conjunction'] = "vs."


    # 4. Time / TV
    time_tv_raw = game_data['Time_TV_raw']
    formatted_time = "TBD"
    formatted_tv = "Not specified"

    # Time: 0:00 p.m. ET
    time_match = re.search(r'(\d{1,2}:\d{2})\s*([apAP])\.?[mM]\.?', time_tv_raw)
    if not time_match: # try for "7:05p" format
        time_match = re.search(r'(\d{1,2}:\d{2})([apAP])', time_tv_raw)

    if time_match:
        time_part = time_match.group(1)
        am_pm = time_match.group(2).lower()
        formatted_time = f"{time_part} {am_pm}.m. ET"
    elif "TBD" in time_tv_raw.upper():
        formatted_time = "TBD"
    
    # TV Channel replacements
    tv_replacements = {"ATV": "Apple TV", "AMZN": "Amazon", "MLBN": "MLB Network"}
    # Try to extract TV part (often after " / " or if time is TBD, the whole string)
    if "/" in time_tv_raw:
        potential_tv = time_tv_raw.split('/')[-1].strip()
    elif formatted_time == "TBD" and time_tv_raw != "TBD":
        potential_tv = time_tv_raw
    else: # Attempt to find TV channel if not explicitly separated by /
        parts = time_tv_raw.split()
        potential_tv = ""
        # Find part that isn't time and isn't ET
        for part in parts:
            if not re.match(r'\d{1,2}:\d{2}',part) and part.lower() not in ['et', 'pm', 'am', 'p', 'a', 'p.m.', 'a.m.']:
                potential_tv = part
                break
    
    if 'potential_tv' in locals() and potential_tv:
        for short, long_name in tv_replacements.items():
            potential_tv = potential_tv.replace(short, long_name)
        formatted_tv = potential_tv
    
    formatted['time'] = formatted_time
    formatted['tv'] = formatted_tv

    # 5. Venue, Starters (pass through if not N/A or TBD, Gemini can choose to include)
    formatted['venue'] = game_data['Venue'] if game_data['Venue'] not in ["TBD", "N/A", ""] else "Venue TBD"
    formatted['home_starter'] = game_data['Home_starter'] if game_data['Home_starter'] not in ["TBD", "N/A", ""] else "Starter TBD"
    formatted['away_starter'] = game_data['Away_starter'] if game_data['Away_starter'] not in ["TBD", "N/A", ""] else "Starter TBD"
    
    # Determine which starter belongs to the scraped team
    if formatted['matchup_conjunction'] == "vs.": # Scraped team is home
        formatted['scraped_team_starter'] = formatted['home_starter']
        formatted['opponent_starter'] = formatted['away_starter']
    else: # Scraped team is away
        formatted['scraped_team_starter'] = formatted['away_starter']
        formatted['opponent_starter'] = formatted['home_starter']


    return formatted

def generate_game_snippet(formatted_game_data):
    if not gemini_model:
        return "Gemini API not configured. Cannot generate snippet."

    # Construct the prompt
    prompt = f"""
    You are an expert sports journalist AI.
    Generate a 1-2 sentence snippet summarizing the following upcoming MLB game.
    The tone should be human-like and professional, suitable for embedding directly into a news article.
    Follow these specific formatting and content rules:
    - Date: Month and Day only (e.g., "July 4").
    - Scraped Team: Use only the mascot name (e.g., "Phillies").
    - Opponent: Use the opponent's full team name (e.g., "New York Mets").
    - Game Time: Format as "0:00 p.m. ET" or "0:00 a.m. ET". If time is TBD, state that.
    - TV Channel: Use full names: "Apple TV" for ATV, "Amazon" for AMZN, "MLB Network" for MLBN. If other, use as provided. If not specified, omit TV info or say "check local listings".
    - Punctuation: Ensure all sentences end with a period. Avoid using semicolons; use periods to separate distinct clauses or before phrases like "check local listings".

    Game Details:
    - Date: {formatted_game_data['date']}
    - Scraped Team: {formatted_game_data['scraped_team_mascot']}
    - Opponent: {formatted_game_data['opponent_full_name']}
    - Matchup Type: {formatted_game_data['scraped_team_mascot']} {formatted_game_data['matchup_conjunction']} {formatted_game_data['opponent_full_name']}
    - Game Time: {formatted_game_data['time']}
    - TV: {formatted_game_data['tv']}
    - Venue: {formatted_game_data['venue']}
    - Scraped Team Starter: {formatted_game_data['scraped_team_starter']}
    - Opponent Starter: {formatted_game_data['opponent_starter']}

    Snippet (1-2 sentences, using periods instead of semicolons)::
    """

    try:
        # st.write("Sending prompt to Gemini:") # For debugging
        # st.text(prompt)
        response = gemini_model.generate_content(prompt)
        if response.parts:
            return response.text.strip()
        else: # Handle cases where response might be blocked or empty
            candidate = response.candidates[0]
            if candidate.finish_reason == 'SAFETY':
                return "Snippet generation failed due to safety settings. Please check the input data."
            return "Gemini returned an empty response."
    except Exception as e:
        return f"Error generating snippet with Gemini: {e}"


# --- Streamlit App UI ---
st.set_page_config(page_title="MLB Team Schedule Scraper", layout="wide")
st.title("⚾ MLB Team Schedule Scraper")
st.markdown("Select an MLB team and click 'Scrape' to get the next game's info and an AI-generated snippet.")

sorted_team_names = sorted(MLB_TEAMS.keys())
options = ["-- Select a Team --"] + sorted_team_names
selected_team_display_name = st.selectbox(
    "Choose an MLB Team:",
    options=options,
    index=0
)

if selected_team_display_name != "-- Select a Team --":
    team_abbr, team_url_name, team_mascot = MLB_TEAMS[selected_team_display_name]
    selected_team_info = MLB_TEAMS[selected_team_display_name] # Pass (abbr, url_name, mascot)
    target_url = generate_team_url(team_abbr, team_url_name)
    
    st.markdown(f"**Scraping for:** {selected_team_display_name}")
    st.caption(f"URL to be scraped: [{target_url}]({target_url})")

    if st.button(f"Scrape Next Game Info for {selected_team_display_name}"):
        game_data_raw = None
        with st.spinner(f"Scraping CBS Sports for {selected_team_display_name} schedule..."):
            game_data_raw = scrape_team_schedule(target_url, selected_team_display_name)

        if game_data_raw:
            st.success(f"Successfully scraped data for {selected_team_display_name}!")
            
            # Display raw scraped data as before
            st.subheader(f"First Listed Game Details (Scraped):")
            st.markdown(f"**Date:** {game_data_raw['Date']}")
            st.markdown(f"**OPP (raw):** {game_data_raw['OPP_raw']}")
            st.markdown(f"**Time / TV (raw):** {game_data_raw['Time_TV_raw']}")
            st.markdown(f"**Venue:** {game_data_raw['Venue']}")
            st.markdown(f"**Home starter:** {game_data_raw['Home_starter']}")
            st.markdown(f"**Away starter:** {game_data_raw['Away_starter']}")
            st.markdown("---")

            # Generate and display Gemini snippet
            if GEMINI_API_KEY and gemini_model:
                st.subheader("AI-Generated Game Snippet:")
                with st.spinner("Formatting data and generating snippet with Gemini..."):
                    formatted_data = format_data_for_gemini_prompt(game_data_raw, selected_team_info)
                    # st.write("Formatted data for prompt:", formatted_data) # For debugging
                    snippet = generate_game_snippet(formatted_data)
                st.markdown(f"> {snippet}")
            else:
                st.warning("Gemini API not configured. Snippet cannot be generated.")
        else:
            st.warning(f"Could not retrieve game data for {selected_team_display_name}. Check error messages.")
else:
    st.info("Please select an MLB team from the dropdown above to begin.")

st.markdown("---")
st.caption("Note: Web scraping can be unreliable. AI snippets are generated by Google Gemini.")
