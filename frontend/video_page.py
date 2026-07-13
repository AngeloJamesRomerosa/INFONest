import streamlit as st
import xml.etree.ElementTree as ET
import time
import logging
from backend.video_processor import (
    load_whisper_model, generate_transcript,
    fetch_videos_from_playlist, fetch_youtube_feed, bart_summarize
)
from backend.models import load_bart_model, load_bart_tokenizer

logger = logging.getLogger(__name__)

bart_model = load_bart_model()
bart_tokenizer = load_bart_tokenizer()


def display_videos(feed, bart_model, bart_tokenizer, selected_channel, is_playlist=False, playlist_channel_title=None):
    user_id = st.session_state.get("user_id", "default_user")
    if "user_data" not in st.session_state:
        st.session_state["user_data"] = {}
    if user_id not in st.session_state["user_data"]:
        st.session_state["user_data"][user_id] = {}

    user_data = st.session_state["user_data"][user_id]

    if "download_count" not in user_data:
        user_data["download_count"] = 0
    if "download_reset_time" not in user_data:
        user_data["download_reset_time"] = time.time()

    current_time = time.time()
    if current_time - user_data["download_reset_time"] > 300:
        user_data["download_count"] = 0
        user_data["download_reset_time"] = current_time

    if is_playlist:
        videos = feed
        channel_title = playlist_channel_title or "Unknown Channel"
        st.markdown(f"<h3 style='font-size: 30px;'>Videos from {channel_title}:</h3>", unsafe_allow_html=True)
    else:
        root = ET.fromstring(feed)
        namespaces = {
            'ns0': 'http://www.w3.org/2005/Atom',
            'ns1': 'http://www.youtube.com/xml/schemas/2015',
            'ns2': 'http://search.yahoo.com/mrss/'
        }
        channel_title = root.find('./ns0:title', namespaces).text
        st.markdown(f"<h3 style='font-size: 30px;'>Videos from {channel_title}:</h3>", unsafe_allow_html=True)
        videos = root.findall('./ns0:entry', namespaces)

    for entry in videos:
        try:
            if is_playlist:
                video_title = entry.get('title', "Untitled Video")
                video_url = entry.get('url')
                if not video_url:
                    st.warning(f"Video URL is missing for: {video_title}")
                    continue
            else:
                video_title = entry.find('./ns0:title', namespaces).text
                video_url = entry.find('./ns0:link', namespaces).attrib['href']

            if selected_channel == "Philippine News Agency":
                if "-1" not in video_title and "- 1" not in video_title:
                    continue
            if selected_channel == "INQUIRER.NET":
                if "INQToday" not in video_title:
                    continue

            key = video_url
            if f"retry_{key}" not in user_data:
                user_data[f"retry_{key}"] = False

            st.subheader(video_title)
            st.video(video_url)
            st.markdown(f"[Go to the Original Video]({video_url})")

            if st.button(f"Generate Summary for '{video_title}'", key=f"button_{key}") or user_data[f"retry_{key}"]:
                st.info("Processing your request. If multiple users are active, this may take a moment...")
                if "last_download_time" not in user_data:
                    user_data["last_download_time"] = 0
                current_time = time.time()
                if current_time - user_data["last_download_time"] < 20:
                    st.warning("Please wait a moment before requesting another summary to avoid YouTube restrictions.")
                    continue
                if user_data["download_count"] >= 2:
                    st.error("Too many audio download requests. Please wait a few minutes and try again.")
                    continue
                try:
                    user_data[f"retry_{key}"] = False
                    with st.spinner("Please wait, loading Whisper model and summarizing video..."):
                        if user_data.get("whisper_model") is None:
                            user_data["whisper_model"] = load_whisper_model()
                        transcript = generate_transcript(video_url, user_data["whisper_model"])
                        if transcript:
                            summary = bart_summarize(bart_tokenizer, transcript, bart_model)
                            user_data[f"summary_{key}"] = summary
                            if "video_history" not in user_data:
                                user_data["video_history"] = []
                            user_data["video_history"].insert(0, {"title": video_title, "summary": summary})
                            user_data["video_history"] = user_data["video_history"][:20]
                        else:
                            user_data["download_count"] += 1
                            st.error("Could not transcribe the audio.")
                            user_data[f"retry_{key}"] = True
                except Exception as e:
                    if "Requested format is not available" in str(e) or "Sign in to confirm you're not a bot" in str(e):
                        user_data["download_count"] += 1
                        user_data["last_download_time"] = 0
                        user_data["download_count"] = 0
                        user_data["download_reset_time"] = current_time
                    st.error(f"Error generating transcript or summary: {str(e)}")
                    user_data[f"retry_{key}"] = True
                finally:
                    user_data["last_download_time"] = current_time
                    time.sleep(3)

            if user_data[f"retry_{key}"]:
                if st.button(f"Retry Generating Summary for '{video_title}'", key=f"retry_button_{key}"):
                    user_data[f"retry_{key}"] = True

            if f"summary_{key}" in user_data:
                with st.expander(f"SUMMARY for '{video_title}'"):
                    st.write("NOTE: The summary may have misspelled some words due to transcript or audio quality.")
                    st.write(user_data[f"summary_{key}"])

        except Exception as e:
            st.error(f"Error processing video: {str(e)}")


def display_video_history_in_sidebar():
    with st.sidebar.expander("Video News History"):
        if "video_history" in st.session_state and st.session_state["video_history"]:
            for video in st.session_state["video_history"]:
                st.markdown(f"**{video['title']}**")
                st.write(f"Summary: {video['summary']}")
                st.markdown("---")
        else:
            st.write("No history available yet.")


def run_youtube_summarizer():
    st.subheader("Video News!")
    st.write("Fetches The Latest English Philippine News Videos from Selected YouTube News Channels and Provides a Summary.")

    user_id = st.session_state.get("user_id", "default_user")
    if "user_data" not in st.session_state:
        st.session_state["user_data"] = {}
    if user_id not in st.session_state["user_data"]:
        st.session_state["user_data"][user_id] = {"whisper_model": None}

    channel_options = {
        "Philippine News Agency": "https://www.youtube.com/feeds/videos.xml?channel_id=UC_PzHuZxnyVh4jRQjpfbXUg",
        "INQUIRER.NET": "https://www.youtube.com/playlist?list=PLz3YOVDOo1Uu5zFXpf0TUxb-oFrHPvSqe",
        "PTV Philippines": "https://www.youtube.com/playlist?list=PLogMBc7vOosHmhdxdu8HVEdYUmCM5y8zv",
        "ANC 24/7": "https://www.youtube.com/playlist?list=PLm34qRgqWBU7Ip7lnkR0rXhSmhBe9u9DW",
        "Rappler": "https://www.youtube.com/playlist?list=PLxIGRNqt1BBipyUGDSrOkvMCtwjmgBqhw",
        "Al Jazeera English": "https://www.youtube.com/playlist?list=PLzGHKb8i9vTwxHRKLZ9LMCBoSLtna7vCk"
    }

    placeholder = "--Please Select a YouTube News Channel!--"
    selected_channel = st.selectbox("Select A Youtube News Channel!", options=[placeholder] + list(channel_options.keys()))

    with st.expander("INSTRUCTIONS: How to Use Video News!"):
        st.write("""
            1. Select a YouTube news channel from the dropdown list.
            2. Each of the YouTube news channel will have videos and has a Generate Summary button.
            3. Press the button in order to generate the summary.
            4. Read the summaries to get an overview of the news.
        """)

    if selected_channel != placeholder:
        feed_url = channel_options[selected_channel]
        if "playlist?list=" in feed_url:
            feed = fetch_videos_from_playlist(feed_url, limit=10)
            display_videos(feed, bart_model, bart_tokenizer, selected_channel, is_playlist=True, playlist_channel_title=selected_channel)
        else:
            feed = fetch_youtube_feed(feed_url)
            display_videos(feed, bart_model, bart_tokenizer, selected_channel)
