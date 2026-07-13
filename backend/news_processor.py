import streamlit as st
import spacy
import pytextrank
import nltk
import re
import torch
import logging
from nltk.tokenize import sent_tokenize
from bs4 import BeautifulSoup as soup

logger = logging.getLogger(__name__)

nlp = spacy.load("en_core_web_sm")
nlp.add_pipe("textrank", last=True)


@st.cache_resource
def punkt_load():
    logger.info("Downloading NLTK punkt data")
    result = nltk.download('punkt')
    logger.info("NLTK punkt data downloaded")
    return result


@st.cache_resource
def stopwords_load():
    logger.info("Downloading NLTK stopwords data")
    nltk.download('stopwords')
    stop_words = nltk.corpus.stopwords.words("english")
    stop_words = stop_words + ['hi', 'im', 'hey']
    logger.info("NLTK stopwords data downloaded")
    return stop_words


@st.cache_data(ttl=None, max_entries=80)
def clean_text(text, stop_words):
    cleanT = re.sub(r"(@\[A-Za-z0-9]+)|(\w+:\/\/\S+)|^rt|http.+?", "", text)
    cleanT = re.sub(r'[^a-zA-Z0-9\s.,\r\n-]+', '', cleanT)
    cleanT = re.sub(r'\s+', ' ', cleanT).strip()
    sentences = sent_tokenize(cleanT)
    return ' '.join([w for w in sentences if w.lower() not in stop_words and w])


def extract_main_content(html):
    soup_obj = soup(html, 'html.parser')
    main_content = soup_obj.find('div', class_='article-content')
    return main_content.get_text(strip=True) if main_content else ""


@st.cache_data(ttl=None, max_entries=80)
def extract_entities(text):
    if text:
        doc = nlp(text)
        return [(ent.text, ent.label_) for ent in doc.ents]
    return []


def prioritize_sentences_with_entities(text, entities, top_n=5):
    sentences = sent_tokenize(text)
    sentence_scores = {}
    for sentence in sentences:
        score = sum(1 for entity, _ in entities if entity in sentence)
        sentence_scores[sentence] = score
    prioritized = sorted(sentence_scores, key=sentence_scores.get, reverse=True)
    return prioritized[:top_n]


@st.cache_data(ttl=None, max_entries=80)
def enhanced_textrank_summarize(text, num_sentences=5):
    if text:
        entities = extract_entities(text)
        prioritized = prioritize_sentences_with_entities(text, entities, top_n=num_sentences)
        doc = nlp(' '.join(prioritized))
        summary = ' '.join([str(sent) for sent in doc._.textrank.summary(limit_sentences=num_sentences)])
        return summary if summary else "Summary is Not Available..."
    return "Summary is not Available..."


def count_sentences(text):
    return len(sent_tokenize(text))


@st.cache_data(ttl=None, max_entries=80)
def bart_summarize(_bart_tokenizer, text, _bart_model, num_sentences=5):
    if text:
        text = re.sub(r"[{}:\"']", "", text)
        text = re.sub(r'\s+', ' ', text).strip()
        inputs = _bart_tokenizer([text], return_tensors='pt', truncation=True, max_length=1024)
        inputs = {k: v.to(next(_bart_model.parameters()).device) for k, v in inputs.items()}
        max_length = 30 * num_sentences
        min_length = 20 * num_sentences
        with torch.no_grad():
            summary_ids = _bart_model.generate(
                inputs['input_ids'],
                max_length=max_length,
                min_length=min_length,
                num_beams=2,
                no_repeat_ngram_size=3
            )
        decoded_summary = _bart_tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        return re.sub(r"([.!?])[^.!?]*$", r"\1", decoded_summary)
    return "Summary is Not Available..."
