import streamlit as st
import logging

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title='INFONest🇵🇭: Get the News!📰', page_icon='./Meta/newspaper1.ico')

from frontend.news_page import run

run()
