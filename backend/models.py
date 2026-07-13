import streamlit as st
from transformers.models.bart import BartForConditionalGeneration, BartTokenizer


@st.cache_resource
def load_bart_model():
    return BartForConditionalGeneration.from_pretrained(
        "sshleifer/distilbart-cnn-12-6",
        use_safetensors=False
    ).to("cpu")


@st.cache_resource
def load_bart_tokenizer():
    return BartTokenizer.from_pretrained("sshleifer/distilbart-cnn-12-6")
