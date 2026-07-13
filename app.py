import streamlit as st
import logging
import re
from PIL import Image

logging.basicConfig(level=logging.INFO)

st.set_page_config(
    page_title='INFONest🇵🇭: Get the News!📰',
    page_icon='./Meta/newspaper1.ico',
    layout='wide'
)

from backend.news_fetcher import (
    fetch_news_from_rss, fetch_news_search_topic, fetch_category_news
)
from backend.news_processor import stopwords_load, punkt_load
from backend.models import load_bart_model, load_bart_tokenizer
from frontend.news_page import display_news, image_to_base64
from frontend.video_page import run_youtube_summarizer, display_video_history_in_sidebar

punkt_load()
stop_words = stopwords_load()
bart_model = load_bart_model()
bart_tokenizer = load_bart_tokenizer()


def run():
    if "history" not in st.session_state:
        st.session_state["history"] = {"Top News": [], "Hot Topics": [], "Search": []}
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = True

    stop_words = stopwords_load()

    # Sidebar: Settings + History
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.markdown("---")
        dark_mode = st.checkbox("🌙 Dark Mode", key="dark_mode")
        st.markdown("---")
        st.markdown("## 📋 History")
        for cat in ["Top News", "Hot Topics", "Search"]:
            with st.expander(f"{cat} History", expanded=False):
                history_data = st.session_state["history"].get(cat, [])
                if history_data:
                    for i, article in enumerate(history_data[-10:], 1):
                        st.markdown(f"**{i}. {article['title']}**")
                        st.markdown(f"{article['summary']}")
                        st.markdown("---")
                else:
                    st.write("No history yet.")
        display_video_history_in_sidebar()

    # Dark/light mode CSS
    if st.session_state["dark_mode"]:
        mode_css = """
        <style>
        .stApp { background-color: #1a1a2e !important; }
        .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        .stApp span, .stApp label, .stMarkdown, .stMarkdown *,
        [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] * { color: #fafafa !important; }
        section[data-testid="stSidebar"] { background-color: #16213e !important; }
        section[data-testid="stSidebar"] * { color: #fafafa !important; }
        .stImage img, [data-testid="stImage"] img, .element-container img {
            border: 2px solid rgba(255,255,255,0.35) !important; border-radius: 6px;
        }
        </style>
        """
    else:
        mode_css = """
        <style>
        .stApp { background-color: #f8f9fa !important; }
        .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        .stApp span, .stApp label, .stMarkdown, .stMarkdown *,
        [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] * { color: #1a1a2e !important; }
        section[data-testid="stSidebar"] { background-color: #ffffff !important; }
        section[data-testid="stSidebar"] * { color: #1a1a2e !important; }
        .stImage img, [data-testid="stImage"] img, .element-container img {
            border: 2px solid #1a1a2e !important; border-radius: 6px;
        }
        </style>
        """
    st.markdown(mode_css, unsafe_allow_html=True)

    st.markdown(
        """
        <style>
        /* Orange CNN-style navbar */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0px;
            background-color: #ff6600;
            padding: 0 16px;
            border-radius: 0;
            flex-wrap: nowrap;
            overflow-x: auto;
        }
        .stTabs [data-baseweb="tab"] {
            color: #ffffff;
            background-color: transparent;
            border: none;
            padding: 10px 11px;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.2px;
            white-space: nowrap;
        }
        .stTabs [aria-selected="true"] {
            background-color: rgba(255,255,255,0.2) !important;
            color: #ffffff !important;
            border-bottom: 3px solid #ffffff;
        }
        .stTabs [data-baseweb="tab-highlight"] { background-color: transparent; }
        .stTabs [data-baseweb="tab-border"] { display: none; }

        /* Side margins — ad-space gutters */
        .main .block-container {
            padding-left: 6rem !important;
            padding-right: 6rem !important;
            max-width: 100% !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("INFONest🇵🇭: Get The News!📰")
    image = Image.open('./Meta/newspaper4.png')
    st.markdown(
        '<div style="display: flex; justify-content: center;">'
        '<img src="data:image/png;base64,{}" width="200"/>'
        '</div>'.format(image_to_base64(image)),
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    (tab_top, tab_world, tab_nation, tab_business,
     tab_tech, tab_ent, tab_sports, tab_science,
     tab_health, tab_search, tab_video) = st.tabs([
        "Top News", "World", "Nation", "Business",
        "Tech", "Entertainment", "Sports",
        "Science", "Health", "Search", "Video"
    ])

    with tab_top:
        with st.expander("ℹ️ What is Top News?"):
            st.write("""
                Top News are recent and relevant news about the Philippines gathered from different sources.
                It covers the recent developments or topics that are currently trending in the country.

                NOTE: Some articles may not load as not all websites allow scraping.
                Loading the articles and summaries may take some time.
            """)
        st.subheader("Here Are the Top News For You!")
        news_list = fetch_news_from_rss('https://news.google.com/news/rss?hl=en&gl=PH&ceid=PH%3Aen')
        display_news(news_list, 5, stop_words, bart_tokenizer, bart_model, "Top News")

    for tab, topic in [
        (tab_world, "WORLD"),
        (tab_nation, "NATION"),
        (tab_business, "BUSINESS"),
        (tab_tech, "TECHNOLOGY"),
        (tab_ent, "ENTERTAINMENT"),
        (tab_sports, "SPORTS"),
        (tab_science, "SCIENCE"),
        (tab_health, "HEALTH"),
    ]:
        with tab:
            with st.expander(f"ℹ️ About {topic.capitalize()} News"):
                st.write(f"Latest {topic.capitalize()} news articles. Please wait as loading may take some time.")
            news_list = fetch_category_news(topic)
            if news_list:
                st.subheader(f"Here are the {topic.capitalize()} News for you!")
                display_news(news_list, 5, stop_words, bart_tokenizer, bart_model, "Hot Topics")
            else:
                st.warning("No articles found. Please try again later.")

    with tab_search:
        with st.expander("ℹ️ How to Search"):
            st.write("""
                Enter any topic in the search bar to find related news articles.
                The app will fetch up to 5 news articles related to your topic.

                NOTE: Please wait as loading the articles and summaries may take some time.
            """)
        user_topic = st.text_input(
            "Enter a topic to search:",
            placeholder="e.g., Sports, Technology, Politics",
            key="search_topic_input"
        )
        if user_topic:
            user_topic = re.sub(r'[^\w\s]', '', user_topic).strip()
            st.session_state["user_topic"] = user_topic
            try:
                with st.spinner("Fetching news articles..."):
                    from urllib.parse import quote_plus
                    news_list = fetch_news_search_topic(quote_plus(user_topic))
                    st.session_state["search_news_list"] = news_list
            except Exception as e:
                st.error(f"Error fetching news: {e}")
                st.session_state["search_news_list"] = []
            if st.session_state.get("search_news_list"):
                st.subheader(f"Here are some {user_topic.capitalize()} News for you!")
                display_news(st.session_state["search_news_list"], 5, stop_words, bart_tokenizer, bart_model, "Search")
            else:
                st.warning("No news articles found for this topic.")
        else:
            st.info("Enter a topic above to get started.")

    with tab_video:
        run_youtube_summarizer()


run()
