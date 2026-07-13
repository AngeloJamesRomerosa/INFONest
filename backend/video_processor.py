import streamlit as st
import yt_dlp
from faster_whisper import WhisperModel
import requests
import json
import re
import os
import time
import torch
import logging
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

logger = logging.getLogger(__name__)


@st.cache_resource
def load_whisper_model():
    return WhisperModel("base", device="cpu", compute_type="int8")


@st.cache_data(ttl=None, max_entries=80)
def download_audio(url, output_path="downloads/audio"):
    video_id = url.split('v=')[-1]
    output_path = f"{output_path}_{video_id}"
    ydl_opts = {
        'format': 'bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio/bestvideo+bestaudio/best',
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
            ydl.extract_info(url, download=True)
            downloaded_file = f"{output_path}.mp3"
            if not os.path.exists(downloaded_file):
                st.error("Audio download failed. File not found.")
                return None
            logger.info(f"Successfully downloaded audio for video {video_id}")
            return downloaded_file
    except Exception as e:
        st.error(f"Error downloading audio: {str(e)}")
        logger.error(f"Error downloading audio for video {video_id}: {str(e)}")
        if "Requested format is not available" in str(e):
            try:
                with yt_dlp.YoutubeDL({'listformats': True}) as ydl:
                    formats_info = ydl.extract_info(url, download=False)
                    logger.info(f"Available formats for video {video_id}: {formats_info.get('formats', [])}")
            except Exception as format_error:
                logger.error(f"Could not retrieve formats for video {video_id}: {str(format_error)}")
        return None
    finally:
        globals()['download_attempted'] = download_attempted


def extract_subtitles(url):
    status_placeholder = st.empty()
    ydl_opts = {
        'format': 'bestaudio/best',
        'writesubtitles': True,
        'subtitleslangs': ['en'],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subtitles = info.get('subtitles', {})
            if 'en' in subtitles:
                return subtitles['en'][0]['url']
            return None
    except Exception as e:
        status_placeholder.error(f"Error extracting subtitles: {str(e)}")
        return None
    finally:
        time.sleep(3)
        status_placeholder.empty()


def clean_subtitles(subtitle_url):
    try:
        response = requests.get(subtitle_url)
        if response.status_code == 200:
            subtitle_text = response.text
            try:
                subtitle_json = json.loads(subtitle_text)
                if "events" in subtitle_json:
                    text_segments = [
                        seg["utf8"] for event in subtitle_json["events"]
                        if "segs" in event for seg in event["segs"]
                    ]
                    cleaned_text = " ".join(text_segments)
                else:
                    cleaned_text = subtitle_text
            except json.JSONDecodeError:
                cleaned_text = re.sub(r'<[^>]*>', '', subtitle_text)
                cleaned_text = re.sub(r'\d{2}:\d{2}:\d{2}.\d{2}', '', cleaned_text)
                cleaned_text = re.sub(r'\n+', ' ', cleaned_text)
            return re.sub(r'\s+', ' ', cleaned_text).strip()
        st.error("Failed to retrieve subtitle text.")
        return None
    except Exception as e:
        st.error(f"Error cleaning subtitles: {str(e)}")
        return None


@st.cache_data(ttl=None, max_entries=80)
def transcribe_audio(audio_path, _model, chunk_length_ms=20000):
    try:
        segments, _ = _model.transcribe(audio_path, language="en")
        return " ".join([seg.text for seg in segments])
    except Exception as e:
        st.error(f"Error transcribing audio: {str(e)}")
        return ""


@st.cache_data(ttl=None, max_entries=80)
def fetch_videos_from_playlist(playlist_url, limit=10):
    ydl_opts = {
        'quiet': False,
        'extract_flat': True,
        'playlistend': limit
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(playlist_url, download=False)
            if not info_dict or 'entries' not in info_dict:
                st.error("No videos found in the playlist. It might be private or empty.")
                return None
            videos = []
            for entry in info_dict['entries'][:limit]:
                if entry.get('is_live') or entry.get('duration') is None:
                    continue
                if not entry.get('url') or not entry.get('title'):
                    continue
                videos.append({
                    'title': entry.get('title', "Untitled Video"),
                    'url': f"https://www.youtube.com/watch?v={entry.get('id')}",
                })
            return videos
    except yt_dlp.utils.DownloadError as download_error:
        st.error(f"Download error: {str(download_error)}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
    return None


@st.cache_data(ttl=None, max_entries=80)
def fetch_youtube_feed(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    st.error("Failed to fetch the YouTube feed")
    return None


@st.cache_data(ttl=None, max_entries=80)
def bart_summarize(_bart_tokenizer, text, _bart_model, num_sentences=5):
    if text:
        text = re.sub(r"[{}:\"']", "", text)
        text = re.sub(r'\s+', ' ', text).strip()
        inputs = _bart_tokenizer([text], return_tensors='pt', truncation=True, max_length=1024)
        inputs = {k: v.to(next(_bart_model.parameters()).device) for k, v in inputs.items()}
        max_length = 30 * num_sentences
        min_length = 10 * num_sentences
        with torch.no_grad():
            summary_ids = _bart_model.generate(
                inputs['input_ids'],
                max_length=max_length,
                min_length=min_length,
                num_beams=3,
                no_repeat_ngram_size=3
            )
        decoded_summary = _bart_tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        return re.sub(r"([.!?])[^.!?]*$", r"\1", decoded_summary)
    return "Summary is Not Available..."


@st.cache_data(ttl=None, max_entries=80)
def generate_transcript(video_url, _model):
    try:
        video_id = video_url.split("v=")[-1].split("&")[0]
        try:
            with st.spinner("Checking for YouTube transcript..."):
                transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
                transcript = " ".join([segment['text'] for segment in transcript_data])
                logger.info(f"Transcript fetched for video {video_id} using YouTubeTranscriptApi")
                return transcript
        except (TranscriptsDisabled, NoTranscriptFound):
            logger.info(f"No transcript found for video {video_id}. Checking for subtitles...")
        subtitle_url = extract_subtitles(video_url)
        if subtitle_url:
            with st.spinner("Using subtitles for summarization..."):
                transcript = clean_subtitles(subtitle_url)
                if transcript:
                    logger.info(f"Subtitles fetched for video {video_id}")
                    return transcript
                logger.info(f"No usable subtitles for video {video_id}")
        with st.spinner("No transcript or subtitles found. Downloading audio for transcription..."):
            audio_path = download_audio(video_url)
            if audio_path:
                with st.spinner("Transcribing audio to text..."):
                    transcript = transcribe_audio(audio_path, _model=_model)
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                    logger.info(f"Audio transcribed for video {video_id}")
                    return transcript
            st.error("Unable to download audio for transcription.")
            logger.error(f"Failed to download audio for video {video_id}")
            return None
    except Exception as e:
        st.error(f"Error during transcript generation: {str(e)}")
        logger.error(f"Error generating transcript: {str(e)}")
        return None
