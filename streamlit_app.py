import streamlit as st
from gnews import GNews
import pandas as pd
import logging
from datetime import datetime, timedelta
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

def scrape_google_news(query: str, start_date: datetime, end_date: datetime, max_results: int) -> pd.DataFrame:
    """
    Scrapes Google News based on the provided query and date range.

    Args:
        query (str): The search query for Google News.
        start_date (datetime): The start date for the news articles.
        end_date (datetime): The end date for the news articles.
        max_results (int): Maximum number of news results to return.

    Returns:
        pd.DataFrame: DataFrame containing the scraped news data.

    Example:
        >>> query = "Artificial Intelligence"
        >>> start_date = datetime(2023, 1, 1)
        >>> end_date = datetime(2023, 12, 31)
        >>> max_results = 10
        >>> df = scrape_google_news(query, start_date, end_date, max_results)
        >>> print(df.head())
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
        logging.info(f"Successfully scraped {len(news_df)} articles.")
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
        {'query': 'Technology', 'start_date': datetime.datetime(2022, 10, 30, 0, 0), ...}
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

def display_news_data(news_df: pd.DataFrame):
    """
    Displays the scraped news data in the Streamlit app.

    Args:
        news_df (pd.DataFrame): DataFrame containing news articles.

    Example:
        >>> display_news_data(news_df)
    """
    if news_df.empty:
        st.info("No news articles to display.")
        return
    
    st.subheader("Scraped News Articles")
    st.dataframe(news_df)

    # Optional: Allow users to download the data as CSV
    csv = news_df.to_csv(index=False)
    st.download_button(
        label="Download Data as CSV",
        data=csv,
        file_name='google_news_results.csv',
        mime='text/csv'
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
