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

    stop_words = stopwords_load()

    st.markdown(
        """
        <style>
        /* Tab bar styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0px;
            background-color: #cc0000;
            padding: 0 16px;
            border-radius: 0;
        }
        .stTabs [data-baseweb="tab"] {
            color: #ffffff;
            background-color: transparent;
            border: none;
            padding: 12px 20px;
            font-size: 15px;
            font-weight: 600;
            letter-spacing: 0.3px;
        }
        .stTabs [aria-selected="true"] {
            background-color: rgba(255,255,255,0.2) !important;
            color: #ffffff !important;
            border-bottom: 3px solid #ffffff;
        }
        .stTabs [data-baseweb="tab-highlight"] {
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab-border"] {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("INFONest🇵🇭: Get The News!📰")
    image = Image.open('./Meta/newspaper4.png')
    st.markdown(
        '<div style="display: flex; justify-content: center;">'
        '<img src="data:image/png;base64,{}" width="300"/>'
        '</div>'.format(image_to_base64(image)),
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📰 Top News", "🔥 Hot Topics", "🔍 Search", "📺 Video News"])

    with tab1:
        with st.expander("ℹ️ What is Top News?"):
            st.write("""
                Top News are recent and relevant news about the Philippines gathered from different sources.
                It covers the recent developments or topics that are currently trending in the country.

                NOTE: Some articles may not load as not all websites allow scraping. Please wait as
                loading the articles and summaries may take some time.
            """)
        st.subheader("Here Are the Top News For You!")
        news_list = fetch_news_from_rss('https://news.google.com/news/rss?hl=en&gl=PH&ceid=PH%3Aen')
        display_news(news_list, 5, stop_words, bart_tokenizer, bart_model, "Top News")

    with tab2:
        with st.expander("ℹ️ What is Hot Topics?"):
            st.write("""
                Hot Topics offers a selection of topics from which you can choose.
                Topics include: WORLD, NATION, BUSINESS, TECHNOLOGY, ENTERTAINMENT, SPORTS, SCIENCE, and HEALTH.

                NOTE: Please wait as loading the articles and summaries may take some time.
            """)
        av_topics = ['--Please Select A Topic!--', 'WORLD', 'NATION', 'BUSINESS', 'TECHNOLOGY', 'ENTERTAINMENT', 'SPORTS', 'SCIENCE', 'HEALTH']
        chosen_topic = st.selectbox("Choose a Topic:", av_topics)
        news_list = []
        if chosen_topic == av_topics[0]:
            st.warning("Please select a topic to proceed.")
        else:
            news_list = fetch_category_news(chosen_topic)
        if news_list:
            st.subheader(f"Here are the {chosen_topic} News for you!")
            display_news(news_list, 5, stop_words, bart_tokenizer, bart_model, "Hot Topics")

    with tab3:
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

    with tab4:
        run_youtube_summarizer()

    st.sidebar.header("📋 History")
    st.sidebar.markdown("---")

    for cat in ["Top News", "Hot Topics", "Search"]:
        with st.sidebar.expander(f"{cat} History", expanded=False):
            history_data = st.session_state["history"].get(cat, [])
            if history_data:
                for i, article in enumerate(history_data[-10:], 1):
                    st.markdown(f"**{i}. {article['title']}**")
                    st.markdown(f"{article['summary']}")
                    st.markdown("---")
            else:
                st.write("No history yet.")

    display_video_history_in_sidebar()


run()
