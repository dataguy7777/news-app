import streamlit as st
from gnews import GNews
import pandas as pd
import logging
from datetime import datetime, timedelta
import sys
import json
from io import BytesIO
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

def fetch_preview(url: str) -> str:
    """
    Fetches a preview snippet from the given URL.

    Args:
        url (str): The URL of the webpage to fetch.

    Returns:
        str: A preview snippet extracted from the webpage.
    """
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Attempt to extract the meta description
        description = soup.find('meta', attrs={'name': 'description'})
        if description and description.get('content'):
            return description.get('content')[:150] + '...'  # Truncate to 150 chars

        # Fallback to first 150 characters of visible text
        text = ' '.join(soup.stripped_strings)
        return text[:150] + '...' if len(text) > 150 else text
    except Exception as e:
        logging.error(f"Error fetching preview for URL {url}: {e}")
        return "No preview available."

def scrape_google_news(query: str, start_date: datetime, end_date: datetime, max_results: int) -> pd.DataFrame:
    """
    Scrapes Google News based on the provided query and date range.

    Args:
        query (str): The search query for Google News.
        start_date (datetime): The start date for the news articles.
        end_date (datetime): The end date for the news articles.
        max_results (int): Maximum number of news results to return.

    Returns:
        pd.DataFrame: DataFrame containing the scraped and processed news data.
    """
    logging.info(f"Starting news scrape for query: '{query}' from {start_date.date()} to {end_date.date()} with max results {max_results}")
    try:
        google_news = GNews(language='en', country='US', max_results=max_results)
        google_news.start_date = start_date
        google_news.end_date = end_date

        result = google_news.get_news(query)
        if not result:
            logging.warning("No news articles found for the given query and date range.")
            return pd.DataFrame()

        news_df = pd.DataFrame(result)

        # Parse 'published date' to datetime for accurate sorting
        if 'published date' in news_df.columns:
            news_df['published date'] = pd.to_datetime(news_df['published date'], errors='coerce')
            news_df = news_df.dropna(subset=['published date'])
            news_df = news_df.sort_values(by='published date', ascending=False)
            logging.info(f"Successfully scraped and sorted {len(news_df)} articles by published date.")
        else:
            logging.warning("'published date' column not found in the scraped data. Skipping sorting.")

        # Parse 'publisher' information
        if 'publisher' in news_df.columns:
            # Initialize new columns
            news_df['url_of_publisher'] = None
            news_df['name_of_publisher'] = None

            for index, row in news_df.iterrows():
                publisher_info = row['publisher']
                try:
                    # If publisher_info is a string, parse it as JSON
                    if isinstance(publisher_info, str):
                        publisher_dict = json.loads(publisher_info)
                    elif isinstance(publisher_info, dict):
                        publisher_dict = publisher_info
                    else:
                        raise ValueError("Unknown format for publisher information.")

                    # Extract 'href' and 'title'
                    url = publisher_dict.get('href', None)
                    name = publisher_dict.get('title', None)

                    news_df.at[index, 'url_of_publisher'] = url
                    news_df.at[index, 'name_of_publisher'] = name
                except json.JSONDecodeError as jde:
                    logging.error(f"JSON decode error for publisher info at index {index}: {jde}")
                except Exception as e:
                    logging.error(f"Unexpected error parsing publisher info at index {index}: {e}")

            # Optional: Drop the original 'publisher' column if no longer needed
            news_df = news_df.drop(columns=['publisher'])
            logging.info("Successfully parsed publisher information into separate columns.")
        else:
            logging.warning("'publisher' column not found in the scraped data. Skipping publisher parsing.")

        # Add tooltip previews for links
        if 'link' in news_df.columns:
            news_df['link_preview'] = news_df['link'].apply(fetch_preview)
        if 'url_of_publisher' in news_df.columns:
            news_df['publisher_preview'] = news_df['url_of_publisher'].apply(fetch_preview)

        return news_df
    except Exception as e:
        logging.error(f"Error scraping Google News: {e}", exc_info=True)
        st.error(f"An error occurred while scraping news: {e}")
        return pd.DataFrame()

def configure_sidebar() -> dict:
    """
    Configures the Streamlit sidebar for user inputs.

    Returns:
        dict: A dictionary containing all user inputs.

    Example:
        >>> user_inputs = configure_sidebar()
        >>> print(user_inputs)
        {'query': 'Technology', 'start_date': datetime.datetime(2022, 10, 31, 0, 0), ...}
    """
    st.sidebar.header("Google News Scraper Configuration")

    query = st.sidebar.text_input("Search Query", value="Artificial Intelligence")
    
    # Calculate tomorrow's date
    today = datetime.today()
    tomorrow = today + timedelta(days=1)
    # Calculate start date as one year before tomorrow
    one_year = timedelta(days=365)
    start_date_default = tomorrow - one_year

    st.sidebar.subheader("Date Range")
    # Use date_input for better user experience
    start_date = st.sidebar.date_input(
        "Start Date",
        value=start_date_default.date(),
        min_value=datetime(2000, 1, 1).date(),
        max_value=tomorrow.date()
    )
    
    end_date = st.sidebar.date_input(
        "End Date",
        value=tomorrow.date(),
        min_value=start_date,
        max_value=tomorrow.date()
    )

    max_results = st.sidebar.slider("Maximum Results", min_value=1, max_value=100, value=10, step=1)

    # Convert date inputs to datetime objects
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    return {
        "query": query,
        "start_date": start_datetime,
        "end_date": end_datetime,
        "max_results": max_results
    }

def generate_excel_download(df: pd.DataFrame) -> bytes:
    """
    Generates an Excel file from the DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame to export.

    Returns:
        bytes: The Excel file in bytes.
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='GoogleNews')
    processed_data = output.getvalue()
    return processed_data

def display_news_data(news_df: pd.DataFrame):
    """
    Displays the scraped news data in the Streamlit app with enhanced features.

    Args:
        news_df (pd.DataFrame): DataFrame containing news articles.

    Example:
        >>> display_news_data(news_df)
    """
    if news_df.empty:
        st.info("No news articles to display.")
        return
    
    st.subheader("Scraped News Articles")

    # Prepare DataFrame for AgGrid
    grid_df = news_df.copy()

    # Replace 'link' and 'url_of_publisher' with clickable links and add tooltips
    if 'link' in grid_df.columns:
        grid_df['link'] = grid_df.apply(
            lambda row: f'<a href="{row["link"]}" target="_blank" title="{row["link_preview"]}">Link</a>', axis=1
        )
    if 'url_of_publisher' in grid_df.columns:
        grid_df['url_of_publisher'] = grid_df.apply(
            lambda row: f'<a href="{row["url_of_publisher"]}" target="_blank" title="{row["publisher_preview"]}">Publisher URL</a>', axis=1
        )

    # Define AgGrid options
    gb = GridOptionsBuilder.from_dataframe(grid_df)
    gb.configure_column("link", header="Article Link", escape=False)
    gb.configure_column("url_of_publisher", header="Publisher URL", escape=False)
    gb.configure_pagination(paginationAutoPageSize=True)  # Add pagination
    gb.configure_side_bar()  # Add a sidebar
    gb.configure_default_column(editable=False, sortable=True, filter=True)
    gridOptions = gb.build()

    # Display AgGrid
    AgGrid(
        grid_df,
        gridOptions=gridOptions,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.NO_UPDATE,
        fit_columns_on_grid_load=True,
        enable_enterprise_modules=False,
        height=600,
        width='100%',
        allow_unsafe_jscode=True,  # Required to render HTML
    )

    # Download buttons
    st.markdown("### Download Data")
    col1, col2 = st.columns(2)
    with col1:
        csv = news_df.to_csv(index=False)
        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name='google_news_results.csv',
            mime='text/csv'
        )
    with col2:
        excel_data = generate_excel_download(news_df)
        st.download_button(
            label="Download as Excel",
            data=excel_data,
            file_name='google_news_results.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

def main():
    """
    The main function to run the Streamlit app.
    """
    st.set_page_config(page_title="Google News Scraper", layout="wide")
    st.title("📰 Google News Scraper")

    user_inputs = configure_sidebar()

    if st.button("Scrape News"):
        with st.spinner("Scraping news articles..."):
            news_df = scrape_google_news(
                query=user_inputs["query"],
                start_date=user_inputs["start_date"],
                end_date=user_inputs["end_date"],
                max_results=user_inputs["max_results"]
            )
        
        display_news_data(news_df)

        # Optionally, save to SQLite or CSV
        # Uncomment the following lines to enable saving
        # import sqlite3
        # conn = sqlite3.connect('google_news.db')
        # news_df.to_sql('src_google_news', conn, if_exists='append', index=False)
        # conn.close()
        # st.success("Data saved to SQLite database.")

if __name__ == "__main__":
    main()
