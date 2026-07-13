import streamlit as st
from PIL import Image
from newspaper import Article
import io
import re
import base64
import logging
from backend.news_fetcher import (
    fetch_news_from_rss, fetch_news_search_topic,
    fetch_category_news, get_actual_article_link
)
from backend.news_processor import (
    clean_text, enhanced_textrank_summarize, bart_summarize,
    extract_main_content, stopwords_load, punkt_load
)
from backend.models import load_bart_model, load_bart_tokenizer

logger = logging.getLogger(__name__)

punkt_load()
stop_words = stopwords_load()
bart_model = load_bart_model()
bart_tokenizer = load_bart_tokenizer()


def fetch_news_poster(poster_link):
    from urllib.request import urlopen
    try:
        u = urlopen(poster_link)
        image = Image.open(io.BytesIO(u.read()))
    except Exception:
        image = Image.open('./Meta/no_image.jpg')
    st.image(image, width=260)


def image_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()


def _render_article(news, c, news_link, news_data, clean_txt, stop_words, bart_tokenizer, bart_model, history, displayed_titles):
    st.write(f'**({c}) {news.title.text}**')
    fetch_news_poster(news_data.top_image)
    with st.expander(news.title.text):
        num_sentences = 5
        textrank_summary = enhanced_textrank_summarize(clean_txt, num_sentences)
        bart_summary = bart_summarize(bart_tokenizer, textrank_summary, bart_model, num_sentences)
        st.markdown(f'<h6 style="text-align: justify;">{bart_summary}</h6>', unsafe_allow_html=True)
        st.markdown(f"[Read more at source]({news_link})")
        if news.title.text not in displayed_titles:
            history.append({"title": news.title.text, "summary": bart_summary})
            displayed_titles.add(news.title.text)
    st.success(f"Published Date: {news.pubDate.text}")


def display_news(list_of_news, news_quantity, stop_words, bart_tokenizer, bart_model, category, layout="📋 List"):
    history = st.session_state["history"].get(category, [])
    displayed_titles = set(article["title"] for article in history)

    articles = []
    for c, news in enumerate(list_of_news[:news_quantity], start=1):
        rss_link = news.link.text
        news_link = get_actual_article_link(rss_link)
        if not news_link:
            st.warning("Could not retrieve the article link.")
            continue
        news_data = Article(news_link)
        try:
            news_data.download()
            news_data.parse()
            raw_text = extract_main_content(news_data.html) or news_data.text
            clean_txt = clean_text(raw_text, stop_words)
        except Exception as e:
            if "403 Client Error" in str(e):
                st.info(f"Skipping article due to download restriction: {news.title.text}. [Read more at source.]({news_link})")
            continue
        articles.append((c, news, news_link, news_data, clean_txt))

    if layout == "🗂️ Grid":
        pairs = [articles[i:i+2] for i in range(0, len(articles), 2)]
        for pair in pairs:
            cols = st.columns(2)
            for col, (c, news, news_link, news_data, clean_txt) in zip(cols, pair):
                with col:
                    _render_article(news, c, news_link, news_data, clean_txt, stop_words, bart_tokenizer, bart_model, history, displayed_titles)
    else:
        for c, news, news_link, news_data, clean_txt in articles:
            _render_article(news, c, news_link, news_data, clean_txt, stop_words, bart_tokenizer, bart_model, history, displayed_titles)

    st.session_state["history"][category] = history[-10:]


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

    category = ['--Select--', 'Top News', 'Hot Topics', 'Search']
    cat_op = st.selectbox('Please Select:', category)
    st.session_state["selected_category"] = cat_op

    if cat_op in category[0:3]:
        with st.expander("INSTRUCTIONS: How to use INFONest!"):
            st.write("""
                NOTE: Some articles may not be loaded at all as not all websites allow for the scraping of data.

                1. Select a category of your choice! (i.e. Top News!, Hot Topics, and Search)

                2. If you pick Top News, Hot Topics, or Search, the application will load 5 of the recent and newest articles
                based on the category chosen.

                3. The articles loaded will have their own summaries. (NOTE: Please wait as it may take time to load the
                articles and summaries!)

                4. Use the summaries as overview for what each of the news is about!
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
