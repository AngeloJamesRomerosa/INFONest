import streamlit as st
from PIL import Image
from newspaper import Article
import io
import re
import base64
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
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

# Module-level article text cache — survives Streamlit reruns within the same process
_article_text_cache = {}
_cache_lock = threading.Lock()
_active_prefetches = set()
_prefetch_lock = threading.Lock()


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


def _download_one(args):
    """Download and parse one article. Checks module-level cache before hitting the network."""
    news, stop_words = args
    try:
        rss_link = news.link.text
        news_link = get_actual_article_link(rss_link)
        if not news_link:
            return {"status": "no_link", "news": news}
        with _cache_lock:
            if news_link in _article_text_cache:
                cached = _article_text_cache[news_link]
                return {"status": "ok", "news": news, "news_link": news_link,
                        "top_image": cached["top_image"], "clean_txt": cached["clean_txt"]}
        news_data = Article(news_link)
        news_data.download()
        news_data.parse()
        raw_text = extract_main_content(news_data.html) or news_data.text
        clean_txt = clean_text(raw_text, stop_words)
        with _cache_lock:
            _article_text_cache[news_link] = {"top_image": news_data.top_image, "clean_txt": clean_txt}
        return {"status": "ok", "news": news, "news_link": news_link,
                "top_image": news_data.top_image, "clean_txt": clean_txt}
    except Exception as e:
        return {"status": "error", "news": news, "error": str(e)}


def _prefetch_all_worker(stop_words):
    """Background daemon thread: pre-downloads articles for all category tabs."""
    categories = ["WORLD", "NATION", "BUSINESS", "TECHNOLOGY",
                  "ENTERTAINMENT", "SPORTS", "SCIENCE", "HEALTH"]
    for topic in categories:
        try:
            news_list = fetch_category_news(topic)
            if news_list:
                with ThreadPoolExecutor(max_workers=5) as ex:
                    list(ex.map(_download_one, [(n, stop_words) for n in news_list[:5]]))
        except Exception:
            pass
    with _prefetch_lock:
        _active_prefetches.discard("all_categories")


def prefetch_all_categories(stop_words):
    """Fire-and-forget: start one background thread to pre-download all category tabs."""
    with _prefetch_lock:
        if "all_categories" in _active_prefetches:
            return
        _active_prefetches.add("all_categories")
    t = threading.Thread(target=_prefetch_all_worker, args=(stop_words,), daemon=True)
    t.start()


def _render_article(news, c, news_link, top_image, clean_txt, stop_words, bart_tokenizer, bart_model, history, displayed_titles):
    st.write(f'**({c}) {news.title.text}**')
    fetch_news_poster(top_image)
    # Use session-state summary cache — BART runs at most once per article per session
    summary_cache = st.session_state.setdefault("summary_cache", {})
    if news_link in summary_cache:
        bart_summary = summary_cache[news_link]
    else:
        num_sentences = 5
        textrank_summary = enhanced_textrank_summarize(clean_txt, num_sentences)
        bart_summary = bart_summarize(bart_tokenizer, textrank_summary, bart_model, num_sentences)
        summary_cache[news_link] = bart_summary
    with st.expander(news.title.text):
        st.markdown(f'<h6 style="text-align: justify;">{bart_summary}</h6>', unsafe_allow_html=True)
        st.markdown(f"[Read more at source]({news_link})")
        if news.title.text not in displayed_titles:
            history.append({"title": news.title.text, "summary": bart_summary})
            displayed_titles.add(news.title.text)
    st.success(f"Published Date: {news.pubDate.text}")


def display_news(list_of_news, news_quantity, stop_words, bart_tokenizer, bart_model, category, layout="📋 List"):
    history = st.session_state["history"].get(category, [])
    displayed_titles = set(article["title"] for article in history)

    # Download all articles in parallel, then summarize sequentially
    with ThreadPoolExecutor(max_workers=min(news_quantity, 5)) as executor:
        results = list(executor.map(_download_one, [(news, stop_words) for news in list_of_news[:news_quantity]]))

    articles = []
    for i, r in enumerate(results, start=1):
        if r["status"] == "no_link":
            st.warning("Could not retrieve the article link.")
        elif r["status"] == "error":
            if "403 Client Error" in r.get("error", ""):
                st.info(f"Skipping article due to download restriction: {r['news'].title.text}.")
        else:
            articles.append((i, r["news"], r["news_link"], r["top_image"], r["clean_txt"]))

    if layout == "🗂️ Grid":
        pairs = [articles[i:i+2] for i in range(0, len(articles), 2)]
        for pair in pairs:
            cols = st.columns(2)
            for col, (c, news, news_link, top_image, clean_txt) in zip(cols, pair):
                with col:
                    _render_article(news, c, news_link, top_image, clean_txt, stop_words, bart_tokenizer, bart_model, history, displayed_titles)
    else:
        for c, news, news_link, top_image, clean_txt in articles:
            _render_article(news, c, news_link, top_image, clean_txt, stop_words, bart_tokenizer, bart_model, history, displayed_titles)

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
