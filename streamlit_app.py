import streamlit as st
from gnews import GNews
import pandas as pd
import logging
from datetime import datetime, timedelta
import sys
from io import BytesIO

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
        pd.DataFrame: DataFrame containing the scraped and processed news data.

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
                        publisher_dict = pd.io.json.loads(publisher_info)
                    elif isinstance(publisher_info, dict):
                        publisher_dict = publisher_info
                    else:
                        raise ValueError("Unknown format for publisher information.")

                    # Extract 'href' and 'title'
                    url = publisher_dict.get('href', None)
                    name = publisher_dict.get('title', None)

                    news_df.at[index, 'url_of_publisher'] = url
                    news_df.at[index, 'name_of_publisher'] = name
                except Exception as e:
                    logging.error(f"Error parsing publisher info at index {index}: {e}")

            # Optional: Drop the original 'publisher' column if no longer needed
            news_df = news_df.drop(columns=['publisher'])
            logging.info("Successfully parsed publisher information into separate columns.")
        else:
            logging.warning("'publisher' column not found in the scraped data. Skipping publisher parsing.")

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

def make_clickable(val):
    """
    Converts a URL into a clickable HTML link.

    Args:
        val (str): The URL to convert.

    Returns:
        str: HTML anchor tag with the URL.
    """
    return f'<a href="{val}" target="_blank">{val}</a>' if val else ''

def make_name_clickable(name, url):
    """
    Creates a clickable publisher name that links to the publisher's URL.

    Args:
        name (str): The name of the publisher.
        url (str): The URL of the publisher.

    Returns:
        str: HTML anchor tag with the publisher's name linking to their URL.
    """
    if name and url:
        return f'<a href="{url}" target="_blank">{name}</a>'
    elif name:
        return name
    else:
        return ''

def convert_df_to_excel(df: pd.DataFrame) -> BytesIO:
    """
    Converts a DataFrame to an Excel file in memory.

    Args:
        df (pd.DataFrame): The DataFrame to convert.

    Returns:
        BytesIO: The in-memory Excel file.
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Google News')
    processed_data = output.getvalue()
    return processed_data

def display_news_data(news_df: pd.DataFrame):
    """
    Displays the scraped news data in the Streamlit app with clickable links.

    Args:
        news_df (pd.DataFrame): DataFrame containing news articles.

    Example:
        >>> display_news_data(news_df)
    """
    if news_df.empty:
        st.info("No news articles to display.")
        return
    
    # Create clickable links
    if 'link' in news_df.columns:
        news_df['link'] = news_df['link'].apply(make_clickable)
    if 'url_of_publisher' in news_df.columns and 'name_of_publisher' in news_df.columns:
        news_df['name_of_publisher'] = news_df.apply(
            lambda row: make_name_clickable(row['name_of_publisher'], row['url_of_publisher']),
            axis=1
        )

    # Select columns to display
    display_columns = ['published date', 'title', 'description', 'link', 'name_of_publisher']

    # Convert DataFrame to HTML
    html_df = news_df[display_columns].to_html(escape=False, index=False)

    st.markdown("### Scraped News Articles", unsafe_allow_html=True)
    st.markdown(html_df, unsafe_allow_html=True)

    # Download as CSV
    csv = news_df.to_csv(index=False)
    st.download_button(
        label="Download Data as CSV",
        data=csv,
        file_name='google_news_results.csv',
        mime='text/csv'
    )

    # Download as Excel
    excel_data = convert_df_to_excel(news_df)
    st.download_button(
        label="Download Data as Excel",
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
