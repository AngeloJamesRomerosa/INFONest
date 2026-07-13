import streamlit as st
import logging
import re
from PIL import Image

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title='INFONest🇵🇭: Get the News!📰', page_icon='./Meta/newspaper1.ico')

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

    st.title("INFONest🇵🇭: Get The News!📰")
    image = Image.open('./Meta/newspaper4.png')
    st.markdown(
        '<div style="display: flex; justify-content: center;">'
        '<img src="data:image/png;base64,{}" width="400"/>'
        '</div>'.format(image_to_base64(image)),
        unsafe_allow_html=True,
    )

    if "selected_category" not in st.session_state:
        st.session_state["selected_category"] = None

    category = ['--Select--', 'Top News', 'Hot Topics', 'Search', 'Video News']
    cat_op = st.selectbox('Please Select:', category)
    st.session_state["selected_category"] = cat_op

    if cat_op in category[0:4]:
        with st.expander("INSTRUCTIONS: How to use INFONest!"):
            st.write("""
                NOTE: Some articles may not be loaded at all as not all websites allow for the scraping of data.

                1. Select a category of your choice! (i.e. Top News!, Hot Topics, Search, and Video News)

                2. If you pick Top News, Hot Topics, or Search, the application will load 5 of the recent and newest articles
                based on the category chosen.

                3. The articles loaded will have their own summaries. (NOTE: Please wait as it may take time to load the
                articles and summaries!)

                4. Use the summaries as overview for what each of the news is about!

                5. Select Video News to watch and summarize the latest Philippine news videos from YouTube.
            """)

    if cat_op == category[0]:
        st.warning('Please Select a Category!')

    elif cat_op == category[1]:
        with st.expander("PLEASE READ! : What is Top News?"):
            st.write("""
                NOTE: Please wait as the loading of the articles and summaries may take some time!

                - Top News are recent and relevant news about the Philippines gathered from different sources!

                - What it covers will be the recent developments or topics that are currently trending in the country.
            """)
        st.subheader("Here Are the Top News For You!")
        news_list = fetch_news_from_rss('https://news.google.com/news/rss?hl=en&gl=PH&ceid=PH%3Aen')
        display_news(news_list, 5, stop_words, bart_tokenizer, bart_model, "Top News")

    elif cat_op == category[2]:
        with st.expander("PLEASE READ! : What is Hot Topics?"):
            st.write("""
                NOTE: Please wait as the loading of the articles and summaries may take some time!

                - Hot Topics offers a selection of topics from which the user can choose from.

                - The topics are: WORLD, NATION, BUSINESS, TECHNOLOGY, ENTERTAINMENT, SPORTS, SCIENCE, and HEALTH.
            """)
        av_topics = ['--Please Select A Topic!--', 'WORLD', 'NATION', 'BUSINESS', 'TECHNOLOGY', 'ENTERTAINMENT', 'SPORTS', 'SCIENCE', 'HEALTH']
        chosen_topic = st.selectbox("Choose a Topic:", av_topics)
        news_list = []
        if chosen_topic == av_topics[0]:
            st.warning("Please select a valid topic to proceed.")
        else:
            news_list = fetch_category_news(chosen_topic)
        if news_list:
            st.subheader(f"Here are the {chosen_topic} News for you!")
            display_news(news_list, 5, stop_words, bart_tokenizer, bart_model, "Hot Topics")

    elif cat_op == category[3]:
        with st.expander("PLEASE READ!: Instructions for Search"):
            st.write("""
                NOTE: Please wait as the loading of the articles and summaries may take some time!

                1. Enter a topic in the search bar below to find news articles.
                2. The app will fetch up to 5 news articles related to your topic.
            """)
        user_topic = st.text_input(
            "Enter a topic to search:",
            placeholder="e.g., Sports, Technology",
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
            st.warning("Please enter a topic to search.")

    elif cat_op == category[4]:
        run_youtube_summarizer()

    st.markdown(
        """
        <style>
        .sidebar .sidebar-header { font-size: 30px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.header("History")
    st.sidebar.empty().text("\n")

    for cat in ["Top News", "Hot Topics", "Search"]:
        with st.sidebar.expander(f"{cat} History", expanded=True):
            history_data = st.session_state["history"].get(cat, [])
            if history_data:
                for i, article in enumerate(history_data[-10:], 1):
                    st.markdown(f"**{i}. {article['title']}**")
                    st.markdown(f"Summary: {article['summary']}")
                    st.markdown("---")
            else:
                st.write("No history available yet.")

    display_video_history_in_sidebar()


run()
