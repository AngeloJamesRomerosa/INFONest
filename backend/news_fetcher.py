import streamlit as st
from bs4 import BeautifulSoup as soup
from urllib.request import urlopen
from googlenewsdecoder import new_decoderv1


@st.cache_resource
def get_actual_article_link(google_news_url):
    try:
        decoded_url = new_decoderv1(google_news_url, interval=5)
        if decoded_url.get("status"):
            return decoded_url["decoded_url"]
        st.warning("Could not decode URL.")
        return None
    except Exception as e:
        st.error(f"Error occurred while retrieving the article link: {e}")
        return None


@st.cache_resource
def fetch_news_from_rss(url):
    op = urlopen(url)
    rd = op.read()
    op.close()
    return soup(rd, 'xml').find_all('item')


@st.cache_resource
def fetch_news_search_topic(topic):
    site = f'https://news.google.com/news/rss/search/section/q/{topic}?hl=en&gl=PH&ceid=PH%3Aen'
    return fetch_news_from_rss(site)


@st.cache_resource
def fetch_category_news(category):
    site = f'https://news.google.com/news/rss/headlines/section/topic/{category}?hl=en&gl=PH&ceid=PH%3Aen'
    return fetch_news_from_rss(site)
