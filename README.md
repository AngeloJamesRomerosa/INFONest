# INFONest🇵🇭: Get The News!📰

A Philippine-focused news aggregator and summarizer built with Streamlit. Fetches live articles and YouTube news videos, then generates AI-powered summaries so you can stay informed at a glance.

---

## Features

### 📰 News Mode
- **Top News** — pulls the latest Philippines headlines via Google News RSS
- **9 Category Tabs** — World, Nation, Business, Tech, Entertainment, Sports, Science, Health; displayed in a persistent CNN-style orange horizontal navbar
- **Search** — search any topic and get up to 5 relevant articles with summaries
- **AI Summaries** — each article is summarized using a TextRank + DistilBART pipeline (extractive then abstractive)
- **History** — last 10 summarized articles per category saved in the sidebar

### 📺 Video Mode
- Fetches the latest videos from selected Philippine and international YouTube news channels:
  - Philippine News Agency, INQUIRER.NET, PTV Philippines, ANC 24/7, Rappler, Al Jazeera English
- Transcribes audio using OpenAI Whisper, then summarizes with DistilBART
- Video history saved in sidebar

### ⚙️ Settings Sidebar
| Setting | Options |
|---|---|
| Mode | 📰 News / 📺 Video |
| Layout | 📋 List / 🗂️ Grid |
| Theme | ☀️ Light / 🌙 Dark |

- **Grid layout** renders articles two per row
- **Dark theme** — deep navy (`#1a1a2e`) background, default on
- **Light theme** — off-white (`#f8f9fa`) background

### UI Details
- Orange CNN-style tab navbar (`#ff6600`) that sticks to the top when scrolling via JavaScript DOM injection
- Centered title and logo
- News article images scaled to 260px width with visible borders in both themes
- Side gutters on the main content area

---

## Tech Stack

| Layer | Library / Model |
|---|---|
| Frontend | [Streamlit](https://streamlit.io) |
| Summarization | [sshleifer/distilbart-cnn-12-6](https://huggingface.co/sshleifer/distilbart-cnn-12-6) |
| Extractive ranking | spaCy + [pytextrank](https://github.com/DerwenAI/pytextrank) |
| Transcription | [OpenAI Whisper](https://github.com/openai/whisper) |
| Text processing | NLTK (punkt, stopwords) |
| Article parsing | [newspaper3k](https://github.com/codelucas/newspaper) |
| HTML parsing | BeautifulSoup4 |
| Deep learning | PyTorch (CPU inference) |

---

## Project Structure

```
INFONest/
├── app.py                  # Local entry point
├── news_summarizer1.py     # Streamlit Cloud entry point (locked at deploy)
├── backend/
│   ├── models.py           # BART model + tokenizer loader
│   ├── news_fetcher.py     # RSS fetch, search, category fetch
│   ├── news_processor.py   # Text cleaning, TextRank, BART summarize
│   └── video_processor.py  # Whisper transcription, playlist fetch
├── frontend/
│   ├── news_page.py        # Article display (List + Grid layouts)
│   └── video_page.py       # YouTube video display + summary UI
├── Meta/                   # Icons and images
└── .streamlit/
    └── config.toml         # Theme config
```

---

## Running Locally

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
streamlit run app.py --server.port 8000
```

Then open your browser and go to:

```
http://localhost:8000
```

---

## Deployment

Deployed on [Streamlit Community Cloud](https://streamlit.io/cloud) using `news_summarizer1.py` as the entry point (set at initial deploy and cannot be changed without redeploying).
