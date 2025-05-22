import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import google.generativeai as genai
from datetime import datetime
import re
import json # For robust JS string escaping

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

MLB_TEAMS_BY_ABBR = {details[0]: (name, details[2]) for name, details in MLB_TEAMS.items()}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
except KeyError:
    GEMINI_API_KEY = None
    gemini_model = None
except Exception:
    GEMINI_API_KEY = None
    gemini_model = None

if not GEMINI_API_KEY or not gemini_model:
    st.error("GEMINI_API_KEY not found/valid in Streamlit secrets or Gemini API configuration failed. AI snippet generation will be disabled.", icon="⚠️")

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
            stats_text = text_part; break
    if full_name_from_url: return f"{full_name_from_url} {stats_text}".strip()
    original_text = " ".join(cell_all_texts); return original_text if original_text else "N/A"

def scrape_team_schedule(team_url, team_display_name):
    try:
        response = requests.get(team_url, headers=HEADERS, timeout=15); response.raise_for_status()
    except requests.exceptions.RequestException as e: st.error(f"Error fetching URL: {e}"); return None
    soup = BeautifulSoup(response.content, 'html.parser')
    tables = soup.find_all('table', class_='TableBase-table')
    if not tables or len(tables) < 2: st.error(f"Could not find the required schedule table."); return None
    schedule_table = tables[1]
    tbody = schedule_table.find('tbody')
    if not tbody: st.error("Could not find table body."); return None
    first_data_row = tbody.find('tr')
    if not first_data_row: st.error("No data rows found."); return None
    cells = first_data_row.find_all('td')
    if len(cells) < 6:
        st.warning(f"Expected 6 cells, found {len(cells)}. Data might be incomplete.")
        while len(cells) < 6: cells.append(BeautifulSoup("<td></td>", "html.parser").td)
    return {
        "Date": " ".join(cells[0].get_text(separator=" ", strip=True).split()),
        "OPP_raw": " ".join(cells[1].get_text(separator=" ", strip=True).split()),
        "Time_TV_raw": " ".join(cells[2].get_text(separator=" ", strip=True).split()),
        "Venue": " ".join(cells[3].get_text(separator=" ", strip=True).split()),
        "Home_starter": get_starter_info(cells[4]),
        "Away_starter": get_starter_info(cells[5]),
        "Scraped_team_full_name": team_display_name
    }

def format_data_for_gemini_prompt(game_data, selected_team_info):
    formatted = {}
    try:
        date_str = game_data['Date']
        date_part = date_str.split(',')[1].strip() if ',' in date_str else date_str
        if len(date_part.split()) > 2: date_part = " ".join(date_part.split()[:2])
        dt_obj = datetime.strptime(date_part, "%b %d")
        formatted['date'] = dt_obj.strftime("%B %d")
    except: formatted['date'] = game_data['Date']
    formatted['scraped_team_mascot'] = selected_team_info[2]
    opp_raw = game_data['OPP_raw']
    match = re.search(r'(?:vs\.?|@)\s*([A-Z]{2,3})', opp_raw)
    if match and match.group(1) in MLB_TEAMS_BY_ABBR: formatted['opponent_full_name'] = MLB_TEAMS_BY_ABBR[match.group(1)][0]
    elif opp_raw.isupper() and len(opp_raw) in [2,3] and opp_raw in MLB_TEAMS_BY_ABBR: formatted['opponent_full_name'] = MLB_TEAMS_BY_ABBR[opp_raw][0]
    else: formatted['opponent_full_name'] = opp_raw.replace("vs. ", "").replace("@ ", "").strip()
    formatted['matchup_conjunction'] = "at" if "@" in opp_raw else "vs."
    time_tv_raw = game_data['Time_TV_raw']
    time_match = re.search(r'(\d{1,2}:\d{2})\s*([apAP])\.?[mM]\.?', time_tv_raw) or re.search(r'(\d{1,2}:\d{2})([apAP])', time_tv_raw)
    formatted['time'] = f"{time_match.group(1)} {time_match.group(2).lower()}.m. ET" if time_match else "TBD"
    tv_replacements = {"ATV": "Apple TV", "AMZN": "Amazon", "MLBN": "MLB Network"}
    potential_tv_str = time_tv_raw.split('/')[-1].strip() if "/" in time_tv_raw else (time_tv_raw if formatted['time'] == "TBD" and time_tv_raw != "TBD" else "")
    if not potential_tv_str:
        for part in time_tv_raw.split():
            if not re.match(r'\d{1,2}:\d{2}',part) and part.lower() not in ['et', 'pm', 'am', 'p', 'a', 'p.m.', 'a.m.']: potential_tv_str = part; break
    formatted['tv'] = tv_replacements.get(potential_tv_str.upper(), potential_tv_str) if potential_tv_str else "Not specified"
    formatted['venue'] = game_data['Venue'] if game_data['Venue'] not in ["TBD", "N/A", ""] else "Venue TBD"
    home_starter = game_data['Home_starter'] if game_data['Home_starter'] not in ["TBD", "N/A", ""] else "Starter TBD"
    away_starter = game_data['Away_starter'] if game_data['Away_starter'] not in ["TBD", "N/A", ""] else "Starter TBD"
    formatted['scraped_team_starter'] = home_starter if formatted['matchup_conjunction'] == "vs." else away_starter
    formatted['opponent_starter'] = away_starter if formatted['matchup_conjunction'] == "vs." else home_starter
    return formatted

def generate_game_snippet(formatted_game_data):
    if not gemini_model: return "Gemini API not configured. Cannot generate snippet."
    prompt = f"""
    You are an expert sports journalist AI. Generate a 1-2 sentence snippet summarizing the upcoming MLB game.
    Tone: human-like, professional, suitable for a news article.
    Formatting Rules:
    - Date: Month and Day (e.g., "July 4").
    - Scraped Team: Mascot name only (e.g., "Phillies").
    - Opponent: Full team name (e.g., "New York Mets").
    - Game Time: "0:00 p.m. ET" or "0:00 a.m. ET". If TBD, state that.
    - TV Channel: Full names: "Apple TV" for ATV, "Amazon" for AMZN, "MLB Network" for MLBN. If other, use as provided. If not specified, omit TV info or say "check local listings".
    - Punctuation: End sentences with a period. Avoid semicolons; use periods.
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
    Snippet (1-2 sentences, using periods instead of semicolons):
    """
    try:
        response = gemini_model.generate_content(prompt)
        if response.parts: return response.text.strip()
        if response.candidates and response.candidates[0].finish_reason == 'SAFETY':
            safety_feedback = f" Details: {response.prompt_feedback.safety_ratings}" if response.prompt_feedback and response.prompt_feedback.safety_ratings else ""
            return f"Snippet generation failed (safety).{safety_feedback}"
        return "Gemini returned an empty/blocked response."
    except Exception as e: return f"Error generating snippet with Gemini: {e}"

st.set_page_config(page_title="MLB Team Schedule Scraper", layout="wide")
st.title("⚾ MLB Team Schedule Scraper")
st.markdown("Select an MLB team and click 'Scrape' to get the next game's info and an AI-generated snippet.")

sorted_team_names = sorted(MLB_TEAMS.keys())
options = ["-- Select a Team --"] + sorted_team_names
selected_team_display_name = st.selectbox("Choose an MLB Team:", options=options, index=0)

if selected_team_display_name != "-- Select a Team --":
    team_abbr, team_url_name, team_mascot = MLB_TEAMS[selected_team_display_name]
    selected_team_info = MLB_TEAMS[selected_team_display_name]
    target_url = generate_team_url(team_abbr, team_url_name)
    st.markdown(f"**Scraping for:** {selected_team_display_name}")
    st.caption(f"URL to be scraped: [{target_url}]({target_url})")

    if st.button(f"Scrape Next Game Info for {selected_team_display_name}"):
        with st.spinner(f"Scraping CBS Sports for {selected_team_display_name} schedule..."):
            game_data_raw = scrape_team_schedule(target_url, selected_team_display_name)
        if game_data_raw:
            st.success(f"Successfully scraped data for {selected_team_display_name}!")
            st.subheader(f"First Listed Game Details (Scraped):")
            st.markdown(f"**Date:** {game_data_raw['Date']}")
            st.markdown(f"**OPP (raw):** {game_data_raw['OPP_raw']}")
            st.markdown(f"**Time / TV (raw):** {game_data_raw['Time_TV_raw']}")
            st.markdown(f"**Venue:** {game_data_raw['Venue']}")
            st.markdown(f"**Home starter:** {game_data_raw['Home_starter']}")
            st.markdown(f"**Away starter:** {game_data_raw['Away_starter']}")
            st.markdown("---")
            if GEMINI_API_KEY and gemini_model:
                st.subheader("AI-Generated Game Snippet:")
                with st.spinner("Formatting data and generating snippet with Gemini..."):
                    formatted_data = format_data_for_gemini_prompt(game_data_raw, selected_team_info)
                    snippet = generate_game_snippet(formatted_data)
                if snippet and not snippet.startswith("Error") and not snippet.startswith("Gemini API not configured") and not snippet.startswith("Snippet generation failed"):
                    # --- HTML/JS Copy Button (Improved) ---
                    # Create unique IDs to prevent conflicts if multiple buttons exist
                    unique_id_suffix = str(hash(snippet)) # Use hash of snippet for more uniqueness
                    button_id = f"copyBtn_{unique_id_suffix}"
                    msg_id = f"copyMsg_{unique_id_suffix}"
                    
                    # Use json.dumps for robust JavaScript string escaping.
                    # It produces a valid JSON string, which is also a valid JS string literal.
                    # We then slice off the surrounding double quotes that json.dumps adds.
                    text_to_copy_js_escaped = json.dumps(snippet)[1:-1]

                    copy_button_html = f"""
                        <div style="margin-bottom: 10px;">
                            <button id="{button_id}">📋 Copy Snippet</button>
                            <span id="{msg_id}" style="margin-left: 10px; font-size: 0.9em;"></span>
                        </div>
                        <script>
                        (function() {{ // IIFE to avoid polluting global scope and ensure code runs after element exists
                            const btn = document.getElementById('{button_id}');
                            const msgSpan = document.getElementById('{msg_id}');
                            const textToCopy = "{text_to_copy_js_escaped}"; // Injected escaped text

                            if (btn && msgSpan) {{
                                btn.addEventListener('click', async function() {{
                                    console.log("Copy button '{button_id}' clicked. Attempting to copy:", textToCopy);
                                    if (!navigator.clipboard) {{
                                        msgSpan.innerText = 'Clipboard API not available.';
                                        msgSpan.style.color = 'red';
                                        console.error('navigator.clipboard API not supported by this browser.');
                                        setTimeout(() => {{ msgSpan.innerText = ''; }}, 3000);
                                        return;
                                    }}
                                    try {{
                                        await navigator.clipboard.writeText(textToCopy);
                                        msgSpan.innerText = 'Copied!';
                                        msgSpan.style.color = 'green';
                                        console.log('Text copied to clipboard successfully!');
                                    }} catch (err) {{
                                        msgSpan.innerText = 'Failed to copy.';
                                        msgSpan.style.color = 'red';
                                        console.error('Failed to copy text using navigator.clipboard.writeText: ', err);
                                        // Log detailed error object
                                        console.error('Error name:', err.name, 'Error message:', err.message);
                                    }} finally {{
                                        setTimeout(() => {{
                                            msgSpan.innerText = '';
                                            msgSpan.style.color = 'green'; // Reset color
                                        }}, 3000);
                                    }}
                                }});
                            }} else {{
                                if (!btn) console.error("Copy button with ID '{button_id}' not found.");
                                if (!msgSpan) console.error("Message span with ID '{msg_id}' not found.");
                            }}
                        }})();
                        </script>
                    """
                    st.html(copy_button_html)
                    # --- End HTML/JS Copy Button ---
                    st.markdown(f"> {snippet}")
                else: st.warning(snippet)
            else: st.warning("Gemini API not configured. AI Snippet cannot be generated.")
        else: st.warning(f"Could not retrieve game data for {selected_team_display_name}. Check error messages.")
else: st.info("Please select an MLB team from the dropdown above to begin.")
st.markdown("---")
st.caption("Note: Web scraping can be unreliable. AI snippets are generated by Google Gemini.")
