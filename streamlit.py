import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# URL of the Phillies schedule page
URL = "https://www.cbssports.com/mlb/teams/PHI/philadelphia-phillies/schedule/"

# Headers to mimic a browser visit
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def scrape_phillies_schedule():
    """
    Scrapes the CBS Sports website for the Phillies schedule,
    finds the second table with class 'TableBase-table',
    and extracts data from the first row after the header.
    """
    try:
        response = requests.get(URL, headers=HEADERS, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching URL: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all tables with the specified class
    tables = soup.find_all('table', class_='TableBase-table')

    if not tables:
        st.error("No tables with class 'TableBase-table' found on the page.")
        return None
    
    if len(tables) < 2:
        st.error(f"Found {len(tables)} table(s) with class 'TableBase-table', but expected at least 2. Cannot find the second one.")
        # For debugging, you could show the content of the first table if it exists
        # if tables:
        #     st.write("Content of the first table found:")
        #     st.dataframe(pd.read_html(str(tables[0]))[0])
        return None

    # The second table is at index 1
    schedule_table = tables[1]

    # Extract header (optional, but good for verification)
    # thead = schedule_table.find('thead')
    # if not thead:
    #     st.error("Could not find a <thead> in the target table.")
    #     return None
    # header_row = thead.find('tr')
    # if not header_row:
    #     st.error("Could not find a <tr> in the <thead> of the target table.")
    #     return None
    # headers = [th.get_text(strip=True) for th in header_row.find_all('th')]
    # st.write("Detected Headers:", headers) # For debugging

    # Find the table body and then the first data row
    tbody = schedule_table.find('tbody')
    if not tbody:
        st.error("Could not find a <tbody> in the target table.")
        return None
    
    first_data_row = tbody.find('tr')
    if not first_data_row:
        st.error("No data rows (<tr>) found in the <tbody> of the target table.")
        return None

    cells = first_data_row.find_all('td')
    
    # Expected columns: Date, OPP, Time / TV, Venue, Home Starter, Away Starter
    if len(cells) < 6:
        st.error(f"Expected at least 6 data cells in the row, but found {len(cells)}.")
        # st.write([cell.get_text(strip=True) for cell in cells]) # Debug output
        return None

    # Extract text from each cell.
    # .get_text(separator=" ", strip=True) helps join text from nested tags with a space
    # and then .split() and .join(" ") cleans up multiple spaces.
    date_val = " ".join(cells[0].get_text(separator=" ", strip=True).split())
    
    # Opponent cell can be a bit complex with logos and names.
    # We'll try to get the primary text content.
    opp_val = " ".join(cells[1].get_text(separator=" ", strip=True).split())
    
    time_tv_val = " ".join(cells[2].get_text(separator=" ", strip=True).split())
    venue_val = " ".join(cells[3].get_text(separator=" ", strip=True).split())
    
    # Starters might be empty or say "TBD"
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
st.set_page_config(page_title="Phillies Schedule Scraper", layout="wide")
st.title("⚾ Philadelphia Phillies Schedule Scraper")
st.markdown(f"This app scrapes game information from [CBS Sports]({URL}).")

if st.button("Scrape Next Game Info"):
    with st.spinner("Scraping CBS Sports for Phillies schedule..."):
        game_data = scrape_phillies_schedule()

    if game_data:
        st.success("Successfully scraped the data for the first listed game!")
        st.subheader("First Game Details:")
        st.markdown(f"**Date:** {game_data['Date']}")
        st.markdown(f"**OPP:** {game_data['OPP']}")
        st.markdown(f"**Time / TV:** {game_data['Time / TV']}")
        st.markdown(f"**Venue:** {game_data['Venue']}")
        st.markdown(f"**Home starter:** {game_data['Home starter']}")
        st.markdown(f"**Away starter:** {game_data['Away starter']}")
        
        # Optionally, display the whole table for context (can be long)
        # st.subheader("Full Scraped Table (for context - showing first few rows)")
        # try:
        #     response_for_df = requests.get(URL, headers=HEADERS, timeout=10)
        #     response_for_df.raise_for_status()
        #     soup_for_df = BeautifulSoup(response_for_df.content, 'html.parser')
        #     all_tables_for_df = soup_for_df.find_all('table', class_='TableBase-table')
        #     if len(all_tables_for_df) >= 2:
        #         df = pd.read_html(str(all_tables_for_df[1]))[0]
        #         st.dataframe(df.head())
        # except Exception as e:
        #     st.warning(f"Could not display full table preview: {e}")

    else:
        st.warning("Could not retrieve game data. Check the error messages above.")

st.markdown("---")
st.caption("Note: Web scraping can be unreliable if the website structure changes.")
