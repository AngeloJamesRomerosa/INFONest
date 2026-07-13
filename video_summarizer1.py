import streamlit as st
import spacy
import yt_dlp
import whisper
from pydub import AudioSegment
import os
import torch
#from transformers import BartForConditionalGeneration, BartTokenizer
import requests
import json
import xml.etree.ElementTree as ET
import re
import numpy as np
from scipy.signal import resample
#from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import time
from PIL import Image

# Cache Whisper model loading
@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base").to("cpu")

# Cache BART model and tokenizer loading
#@st.cache_resource
#def load_bart_modelYT():
    #return BartForConditionalGeneration.from_pretrained("sshleifer/distilbart-cnn-12-6", use_safetensors= False)
    #return AutoModelForSeq2SeqLM.from_pretrained("sshleifer/distilbart-cnn-12-6", use_safetensors= False)
    #return AutoModelForSeq2SeqLM.from_pretrained("Angel0J/distilbart-multi_news-12-6", use_safetensors = True)
    
#@st.cache_resource
#def load_bart_tokenizerYT():
    #return BartTokenizer.from_pretrained("sshleifer/distilbart-cnn-12-6")
    #return AutoTokenizer.from_pretrained("sshleifer/distilbart-cnn-12-6")
    #return AutoTokenizer.from_pretrained("Angel0J/distilbart-multi_news-12-6")

# Load the models
#loading_message = st.empty()
#progress = st.progress(0)  # Initialize progress bar
#loading_message.markdown("**Now Loading...**", unsafe_allow_html=True)
#with st.empty():
    #progress.progress(50)  # Update to 50% for BART model
    #bart_model = load_bart_modelYT()
    #progress.progress(100)  # Update to 100% for tokenizer
    #bart_tokenizer = load_bart_tokenizerYT()

# Once the models are loaded, remove the progress bar
#progress.empty()  # Remove the progress bar from the screen
#loading_message.empty()  # Remove the "Now Loading..." message
#time.sleep(1)

from models import load_bart_model, load_bart_tokenizer
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add logging to capture initialization details
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load the models with logging
logger.info("Starting to load BART model and tokenizer in video_summarizer1")
bart_model = load_bart_model()
bart_tokenizer = load_bart_tokenizer()
logger.info("BART model and tokenizer loaded successfully in video_summarizer1")

@st.cache_data(ttl=None, max_entries=80)
def download_audio(url, output_path="downloads/audio"):
    video_id = url.split('v=')[-1]
    output_path = f"{output_path}_{video_id}"
    
    ydl_opts = {
        'format': 'bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio/bestvideo+bestaudio/best',  # Fallback to video if audio fails
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': f"{output_path}.%(ext)s",
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'cookiefile': 'cookies.txt',
        'http_headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.youtube.com/',
        },
    }
    
    download_attempted = True
    try:
        if not os.path.exists('cookies.txt'):
            logger.error("cookies.txt not found. Proceeding without cookies.")
            st.warning("Cookies file not found. This may trigger YouTube bot detection.")
        else:
            logger.info("Using cookies.txt for YouTube authentication.")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = f"{output_path}.mp3"
            if not os.path.exists(downloaded_file):
                st.error("Audio download failed. File not found.")
                return None
            logger.info(f"Successfully downloaded audio for video {video_id}")
            return downloaded_file
    except Exception as e:
        st.error(f"Error downloading audio: {str(e)}")
        logger.error(f"Error downloading audio for video {video_id}: {str(e)}")
        # Log available formats for debugging
        if "Requested format is not available" in str(e):
            try:
                with yt_dlp.YoutubeDL({'listformats': True}) as ydl:
                    formats_info = ydl.extract_info(url, download=False)
                    logger.info(f"Available formats for video {video_id}: {formats_info.get('formats', [])}")
                    st.write("Available formats for this video:")
                    st.write(formats_info.get('formats', []))
            except Exception as format_error:
                st.error(f"Could not retrieve formats: {str(format_error)}")
                logger.error(f"Could not retrieve formats for video {video_id}: {str(format_error)}")
        return None
    finally:
        globals()['download_attempted'] = download_attempted
    
# Function to extract subtitles if available
def extract_subtitles(url):
    # Create a placeholder to hold the status message
    status_placeholder = st.empty()

    # Display initial checking message
    #status_placeholder.write("Checking for available subtitles...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'writesubtitles': True,  # Enable subtitle download
        'subtitleslangs': ['en'],  # Preferred subtitle language (English)
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)  # Don't download yet, just extract info
            subtitles = info.get('subtitles', {})
            if 'en' in subtitles:  # Check if English subtitles exist
                # Update the status message
                #status_placeholder.write("Subtitles found!")
                subtitle_url = subtitles['en'][0]['url']
                return subtitle_url
            else:
                # Update the status message
                #status_placeholder.write("No subtitles found.")
                return None
            
    except Exception as e:
        # Show error message
        status_placeholder.error(f"Error extracting subtitles: {str(e)}")
        return None
    finally:
        # Clear the status message after the function finishes
        time.sleep(3)
        status_placeholder.empty()
    
    
# Function to clean and preprocess subtitle text
def clean_subtitles(subtitle_url):
    #st.write("Cleaning subtitle text...") 
    try:
        response = requests.get(subtitle_url)
        if response.status_code == 200:
            subtitle_text = response.text
            try:
                # If the subtitle is in JSON format
                subtitle_json = json.loads(subtitle_text)
                if "events" in subtitle_json:
                    text_segments = [
                        seg["utf8"] for event in subtitle_json["events"] if "segs" in event for seg in event["segs"]
                    ]
                    cleaned_text = " ".join(text_segments)
                else:
                    cleaned_text = subtitle_text  # Fallback
            except json.JSONDecodeError:
                # Handle non-JSON subtitle formats
                cleaned_text = re.sub(r'<[^>]*>', '', subtitle_text)  # Remove HTML tags
                cleaned_text = re.sub(r'\d{2}:\d{2}:\d{2}.\d{2}', '', cleaned_text)  # Remove timestamps
                cleaned_text = re.sub(r'\n+', ' ', cleaned_text)  # Replace newlines with spaces

            cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()  # Normalize spaces
            return cleaned_text
        else:
            st.error("Failed to retrieve subtitle text.")
            return None
    except Exception as e:
        st.error(f"Error cleaning subtitles: {str(e)}")
        return None


# Cache transcribing audio
@st.cache_data(ttl=None, max_entries=80)
def transcribe_audio(audio_path, _model, chunk_length_ms=20000):
    #st.write("Transcribing audio in chunks...")
    audio = AudioSegment.from_mp3(audio_path)
    transcriptions = []
    for start_ms in range(0, len(audio), chunk_length_ms):
        end_ms = min(start_ms + chunk_length_ms, len(audio))
        chunk = audio[start_ms:end_ms]
        chunk_samples = np.array(chunk.get_array_of_samples())
        chunk_samples = chunk_samples.astype(np.float32) / np.iinfo(chunk_samples.dtype).max
        chunk_samples = chunk_samples.reshape(-1, chunk.channels).mean(axis=1)
        original_sample_rate = chunk.frame_rate
        target_sample_rate = 16000
        num_samples = int(len(chunk_samples) * target_sample_rate / original_sample_rate)
        resampled_chunk = resample(chunk_samples, num_samples)
        resampled_chunk = torch.tensor(resampled_chunk).to("cpu")
        try:
            with torch.no_grad():
                result = _model.transcribe(audio=resampled_chunk, language="en", fp16=torch.cuda.is_available())
                transcription_text = result.get("text", "")
                if transcription_text:
                    transcriptions.append(transcription_text)
        except Exception as e:
            st.error(f"Error transcribing chunk: {str(e)}")
        finally:
            torch.cuda.empty_cache()
    return " ".join(transcriptions)
# Function to fetch videos from a YouTube playlists
@st.cache_data(ttl=None, max_entries=80)
def fetch_videos_from_playlist(playlist_url, limit=10):
    # yt_dlp options
    ydl_opts = {
        'quiet': False,  # Enable verbose output for debugging
        'extract_flat': True,  # Extract metadata without downloading
        'playlistend': limit  # Stop processing after 'limit' videos
    }

    try:
        # Initialize yt_dlp with the specified options
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract playlist information
            info_dict = ydl.extract_info(playlist_url, download=False)

            # Ensure the playlist contains 'entries'
            if not info_dict or 'entries' not in info_dict:
                st.error("No videos found in the playlist. It might be private or empty.")
                return None

            # Extract videos
            videos = []
            for entry in info_dict['entries'][:limit]:
                # Check if the video is private or unavailable
                if entry.get('is_live') or entry.get('duration') is None:
                    continue  # Skip live or unavailable videos
                
                # Some videos marked as private have no 'url' or 'title'
                if not entry.get('url') or not entry.get('title'):
                    continue  # Skip private or inaccessible videos

                video_title = entry.get('title', "Untitled Video")
                video_url = f"https://www.youtube.com/watch?v={entry.get('id')}"  # Construct full URL
                #thumbnail_url = (
                    #entry['thumbnails'][-1]['url'] if 'thumbnails' in entry and entry['thumbnails'] else None
                #)
                videos.append({
                    'title': video_title,
                    'url': video_url,
                    #'thumbnail': thumbnail_url,
                })

            return videos
    except yt_dlp.utils.DownloadError as download_error:
        st.error(f"Download error: {str(download_error)}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")

    return None


# Cache fetching YouTube RSS feed
@st.cache_data(ttl=None, max_entries=80)
def fetch_youtube_feed(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        st.error("Failed to fetch the YouTube feed")
        return None

@st.cache_data(ttl=None, max_entries=80)   
def bart_summarize(_bart_tokenizer, text, _bart_model, num_sentences = 5):
    if text:
        # Pre-clean the input text
        text = re.sub(r"[{}:\"']", "", text)  # Remove unnecessary punctuation
        text = re.sub(r'\s+', ' ', text).strip()  # Normalize spaces
        
        inputs = _bart_tokenizer([text], return_tensors='pt', truncation=True, max_length=1024)
        inputs = {k: v.to(next(_bart_model.parameters()).device) for k, v in inputs.items()}

        # Define max_length and min_length 
        max_length = 30 * num_sentences  # Adjust max length for summary (orig is 50)
        min_length = 10 * num_sentences  # Adjust min length for summary (orig is 20)

        with torch.no_grad():
            summary_ids = _bart_model.generate(
                inputs['input_ids'],
                max_length=max_length,
                min_length=min_length,
                num_beams=3,
                no_repeat_ngram_size=3
            )

        decoded_summary = _bart_tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        final_summary = re.sub(r"([.!?])[^.!?]*$", r"\1", decoded_summary)  # Ensure it ends on a full sentence
        return final_summary
    return "Summary is Not Available..."

    
# Function to generate transcript from YouTube video URL
@st.cache_data(ttl=None, max_entries=80)
def generate_transcript(video_url, _model):
    try:
        video_id = video_url.split("v=")[-1].split("&")[0]
        
        # Try YouTube transcript first
        try:
            with st.spinner("Checking for YouTube transcript..."):
                transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
                transcript = " ".join([segment['text'] for segment in transcript_data])
                logger.info(f"Transcript fetched for video {video_id} using YouTubeTranscriptApi")
                return transcript
        except (TranscriptsDisabled, NoTranscriptFound):
            logger.info(f"No transcript found for video {video_id}. Checking for subtitles...")
        
        # Try subtitles next
        subtitle_url = extract_subtitles(video_url)
        if subtitle_url:
            with st.spinner("Using subtitles for summarization..."):
                transcript = clean_subtitles(subtitle_url)
                if transcript:
                    logger.info(f"Subtitles fetched for video {video_id}")
                    return transcript
                else:
                    logger.info(f"No usable subtitles for video {video_id}")
        
        # Only attempt audio download if both transcript and subtitles fail
        with st.spinner("No transcript or subtitles found. Downloading audio for transcription..."):
            audio_path = download_audio(video_url)
            if audio_path:
                with st.spinner("Transcribing audio to text..."):
                    transcript = transcribe_audio(audio_path, _model=_model)
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                    logger.info(f"Audio transcribed for video {video_id}")
                    return transcript
            else:
                st.error("Unable to download audio for transcription.")
                logger.error(f"Failed to download audio for video {video_id}")
                return None
    except Exception as e:
        st.error(f"Error during transcript generation: {str(e)}")
        logger.error(f"Error generating transcript for video {video_id}: {str(e)}")
        return None

    
# Function to display video details from the RSS feed
def display_videos(feed, bart_model, bart_tokenizer, selected_channel, is_playlist=False, playlist_channel_title=None):
    user_id = st.session_state.get("user_id", "default_user")
    if "user_data" not in st.session_state:
        st.session_state["user_data"] = {}
    if user_id not in st.session_state["user_data"]:
        st.session_state["user_data"][user_id] = {}

    user_data = st.session_state["user_data"][user_id]

    # Initialize rate-limiting counters
    if "download_count" not in user_data:
        user_data["download_count"] = 0
    if "download_reset_time" not in user_data:
        user_data["download_reset_time"] = time.time()

    # Reset download count after 5 minutes
    current_time = time.time()
    if current_time - user_data["download_reset_time"] > 300:
        user_data["download_count"] = 0
        user_data["download_reset_time"] = current_time

    if is_playlist:
        videos = feed
        channel_title = playlist_channel_title if playlist_channel_title else "Unknown Channel"
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
                if current_time - user_data["last_download_time"] < 20:  # 20-second delay between requests
                    st.warning("Please wait a moment before requesting another summary to avoid YouTube restrictions.")
                    continue

                if user_data["download_count"] >= 2:
                    st.error("Too many audio download requests. Please wait a few minutes and try again to avoid YouTube restrictions.")
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
                            if "download_attempted" in globals() and globals()['download_attempted']:
                                user_data["download_count"] += 1
                            st.error("Could not transcribe the audio.")
                            user_data[f"retry_{key}"] = True
                except Exception as e:
                    if "Requested format is not available" in str(e) or "Sign in to confirm you’re not a bot" in str(e):
                        user_data["download_count"] += 1
                        # Reset session to avoid persistent failures
                        user_data["last_download_time"] = 0
                        user_data["download_count"] = 0
                        user_data["download_reset_time"] = current_time
                    st.error(f"Error generating transcript or summary: {str(e)}")
                    user_data[f"retry_{key}"] = True
                finally:
                    user_data["last_download_time"] = current_time
                    time.sleep(3)  # 3-second delay after each request

            if user_data[f"retry_{key}"]:
                if st.button(f"Retry Generating Summary for '{video_title}'", key=f"retry_button_{key}"):
                    user_data[f"retry_{key}"] = True

            if f"summary_{key}" in user_data:
                with st.expander(f"SUMMARY for '{video_title}'"):
                    st.write("NOTE: The summary may have misspelled some words due to transcript or audio quality.")
                    st.write(user_data[f"summary_{key}"])

        except Exception as e:
            st.error(f"Error processing video: {str(e)}")



# Display video history in the sidebar in an `st.expander`
def display_video_history_in_sidebar():
    # Create the expander for the video news history
    with st.sidebar.expander("Video News History"):
        # Check if there is video history data
        if "video_history" in st.session_state and st.session_state["video_history"]:
            # If there is history, display the videos
            for video in st.session_state["video_history"]:
                st.markdown(f"**{video['title']}**")
                st.write(f"Summary:{video['summary']}")
                st.markdown("---")  # Separator for each video
        else:
            # If no history, display the message
            st.write("No history available yet.")
            
# Main function
def run_youtube_summarizer():
    st.subheader("Video News!")
    st.write("Fetches The Latest English Philippine News Videos from Selected YouTube News Channels and Provides a Summary.")
    
    # Initialize user-specific state
    user_id = st.session_state.get("user_id", "default_user")
    if "user_data" not in st.session_state:
        st.session_state["user_data"] = {}
    if user_id not in st.session_state["user_data"]:
        st.session_state["user_data"][user_id] = {"whisper_model": None}

    # Define the list of YouTube channel RSS feeds
    channel_options = {
        "Philippine News Agency": "https://www.youtube.com/feeds/videos.xml?channel_id=UC_PzHuZxnyVh4jRQjpfbXUg",  
        "INQUIRER.NET": "https://www.youtube.com/playlist?list=PLz3YOVDOo1Uu5zFXpf0TUxb-oFrHPvSqe",
        "PTV Philippines": "https://www.youtube.com/playlist?list=PLogMBc7vOosHmhdxdu8HVEdYUmCM5y8zv",
        "ANC 24/7": "https://www.youtube.com/playlist?list=PLm34qRgqWBU7Ip7lnkR0rXhSmhBe9u9DW",
        "Rappler": "https://www.youtube.com/playlist?list=PLxIGRNqt1BBipyUGDSrOkvMCtwjmgBqhw",
        "Al Jazeera English": "https://www.youtube.com/playlist?list=PLzGHKb8i9vTwxHRKLZ9LMCBoSLtna7vCk"
    }

    placeholder = "--Please Select a YouTube News Channel!--"
    all_options = [placeholder] + list(channel_options.keys())

    selected_channel = st.selectbox("Select A Youtube News Channel!", options=all_options)
    with st.expander("INSTRUCTIONS: How to Use Video News!"):
        st.write("""
            1. Select a YouTube news channel from the dropdown list.
            2. Each of the YouTube news channel will have videos and has a Generate Summary button.
            3. Press the button in order to generate the summary. (NOTE: Please wait as it may take some time especially if the video's audio is used for summarization!)
            4. Read the summaries to get an overview of the news.
        """)

    feed = None
    if selected_channel != placeholder:
        feed_url = channel_options[selected_channel]
        if "playlist?list=" in feed_url:
            feed = fetch_videos_from_playlist(feed_url, limit=10)
            display_videos(feed, bart_model, bart_tokenizer, selected_channel, is_playlist=True, playlist_channel_title=selected_channel)
        else:
            feed = fetch_youtube_feed(feed_url)
            display_videos(feed, bart_model, bart_tokenizer, selected_channel)
                               
if __name__ == "__main__":
    run_youtube_summarizer()

#streamlit video_summarizer.py




