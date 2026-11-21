import html
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError
from google.genai import types


load_dotenv(override=True)

DEFAULT_MODEL = "gemini-2.5-flash"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
SAMPLE_ARTICLES_PATH = Path(__file__).with_name("sample_articles.json")


# ---------------------------------------------------------------------------
# Core logic (unchanged behaviour)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Simplification:
    simplified_article: str
    glossary: list[dict[str, str]]


def build_prompt(article: str, target_language: str) -> str:
    return f"""You simplify health articles for general readers.

Rewrite the article below in plain, easy-to-understand {target_language}.
Preserve all facts and the author's meaning. Do not add, infer, or omit medical
claims, diagnoses, causes, risks, treatment advice, or recommendations. Keep
names, dates, quantities, units, and uncertainty accurate. If the source is
unclear, do not guess; retain that uncertainty in the rewrite.

Identify medical terms that may be unfamiliar and define each briefly in
plain {target_language}. If there are none, return an empty glossary array.
Return only a JSON object with exactly these fields:
{{
  "simplified_article": "the rewritten article",
  "glossary": [
    {{"term": "medical term", "simple_definition": "plain-language meaning"}}
  ]
}}

Article:
<article>
{article}
</article>"""


def simplify_article(
    article: str,
    target_language: str,
    client: Any,
    model: str = DEFAULT_MODEL,
) -> Simplification:
    cleaned_article = article.strip()
    cleaned_language = target_language.strip()
    if not cleaned_article:
        raise ValueError("The article cannot be empty.")
    if not cleaned_language:
        raise ValueError("The output language cannot be empty.")

    response = client.models.generate_content(
        model=model,
        contents=build_prompt(cleaned_article, cleaned_language),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    response_text = response.text
    if not response_text:
        raise ValueError("Gemini returned an empty response.")

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise ValueError("Gemini returned invalid JSON.") from error

    simplified_article = payload.get("simplified_article")
    glossary = payload.get("glossary")
    if not isinstance(simplified_article, str) or not simplified_article.strip():
        raise ValueError("Gemini's response is missing a simplified article.")
    if not isinstance(glossary, list):
        raise ValueError("Gemini's response contains an invalid glossary.")

    validated_glossary = []
    for entry in glossary:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("term"), str)
            or not entry["term"].strip()
            or not isinstance(entry.get("simple_definition"), str)
            or not entry["simple_definition"].strip()
        ):
            raise ValueError("Gemini's response contains an invalid glossary entry.")
        validated_glossary.append(
            {
                "term": entry["term"].strip(),
                "simple_definition": entry["simple_definition"].strip(),
            }
        )

    return Simplification(
        simplified_article=simplified_article.strip(),
        glossary=validated_glossary,
    )


def load_sample_articles() -> list[dict[str, Any]]:
    with SAMPLE_ARTICLES_PATH.open(encoding="utf-8") as sample_file:
        samples = json.load(sample_file)
    if not isinstance(samples, list) or not samples:
        raise ValueError("The sample articles file must contain a non-empty list.")

    for sample in samples:
        if (
            not isinstance(sample, dict)
            or not isinstance(sample.get("id"), str)
            or not isinstance(sample.get("title"), str)
            or not isinstance(sample.get("source_url"), str)
            or not isinstance(sample.get("paragraphs"), list)
            or len(sample["paragraphs"]) < 4
            or not all(
                isinstance(paragraph, str) and paragraph.strip()
                for paragraph in sample["paragraphs"]
            )
        ):
            raise ValueError(
                "Each sample must have an id, title, source URL, "
                "and at least four non-empty paragraphs."
            )
    return samples


def shuffle_sample_article(samples: list[dict[str, Any]]) -> None:
    previous_id = st.session_state.get("selected_sample_id")
    choices = [sample for sample in samples if sample["id"] != previous_id]
    sample = random.choice(choices or samples)
    st.session_state["article_text"] = "\n\n".join(sample["paragraphs"])
    st.session_state["selected_sample_id"] = sample["id"]
    st.session_state["selected_sample_title"] = sample["title"]
    st.session_state["selected_sample_url"] = sample["source_url"]


def clear_sample_attribution() -> None:
    st.session_state["selected_sample_id"] = None
    st.session_state["selected_sample_title"] = None
    st.session_state["selected_sample_url"] = None


LANGUAGES = [
    "English",
    "Hindi",
    "Marathi",
    "Gujarati",
    "Tamil",
    "Telugu",
    "Bengali",
    "Kannada",
    "Spanish",
    "French",
    "German",
]


# ---------------------------------------------------------------------------
# UI: iOS-style glass design
# ---------------------------------------------------------------------------
GLASS_CSS = """
<style>
:root {
  --blue: #0A84FF;
  --indigo: #5E5CE6;
  --teal: #30D5C8;
  --green: #30D158;
  --pink: #FF375F;
  --orange: #FF9F0A;
  --ink: #1C1C1E;
  --ink-2: #636366;
  --glass: rgba(255, 255, 255, 0.55);
  --glass-strong: rgba(255, 255, 255, 0.72);
  --glass-border: rgba(255, 255, 255, 0.75);
  --shadow: 0 8px 32px rgba(31, 38, 135, 0.14), 0 1px 0 rgba(255, 255, 255, 0.6) inset;
}

html, body, .stApp, [class*="css"] {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text",
               "Inter", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
  color: var(--ink);
}

/* Chrome removal */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.block-container { max-width: 760px; padding-top: 1.6rem; padding-bottom: 3rem; }

/* Soft aurora background that the glass blurs against */
.stApp {
  background:
    radial-gradient(60rem 40rem at 8% -10%, #BFD9FF 0%, transparent 55%),
    radial-gradient(50rem 36rem at 100% 0%, #E4D4FF 0%, transparent 55%),
    radial-gradient(48rem 40rem at 50% 105%, #C8F5EE 0%, transparent 55%),
    linear-gradient(180deg, #F4F7FD 0%, #EEF1FA 100%);
  background-attachment: fixed;
}

/* ---------- Hero ---------- */
.hero { text-align: center; padding: 0.6rem 0 1.2rem; }
.app-icon {
  width: 78px; height: 78px; margin: 0 auto 14px; border-radius: 22px;
  display: flex; align-items: center; justify-content: center; font-size: 40px;
  background: linear-gradient(145deg, #5AC8FA 0%, #0A84FF 55%, #5E5CE6 100%);
  box-shadow: 0 12px 28px rgba(10, 132, 255, 0.35), 0 1px 0 rgba(255,255,255,.6) inset;
}
.hero h1 { font-size: 2.1rem; font-weight: 800; letter-spacing: -0.03em; margin: 0; padding: 0; }
.hero p { color: var(--ink-2); font-size: 1.02rem; margin: 6px 0 0; }

/* ---------- Glass cards (st.container with key="card_*") ---------- */
[class*="st-key-card_"] {
  background: var(--glass);
  -webkit-backdrop-filter: blur(26px) saturate(180%);
  backdrop-filter: blur(26px) saturate(180%);
  border: 1px solid var(--glass-border);
  border-radius: 26px;
  box-shadow: var(--shadow);
  padding: 1.15rem 1.25rem 1.3rem;
  margin-bottom: 0.9rem;
}

/* Notice card */
.notice {
  display: flex; gap: 12px; align-items: flex-start;
  background: rgba(255, 159, 10, 0.14);
  -webkit-backdrop-filter: blur(20px); backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: 20px; padding: 12px 16px; margin-bottom: 0.9rem;
  box-shadow: var(--shadow); font-size: 0.9rem; line-height: 1.4; color: #6B4A00;
}
.notice .ico { font-size: 1.25rem; line-height: 1.2; }

/* ---------- Section headers with app-icon tiles ---------- */
.sec { display: flex; align-items: center; gap: 12px; margin: 0 0 0.85rem; }
.tile {
  width: 38px; height: 38px; border-radius: 11px; flex: 0 0 38px;
  display: flex; align-items: center; justify-content: center; font-size: 20px;
  box-shadow: 0 6px 14px rgba(0,0,0,.14), 0 1px 0 rgba(255,255,255,.55) inset;
}
.tile.blue   { background: linear-gradient(145deg, #64D2FF, #0A84FF); }
.tile.purple { background: linear-gradient(145deg, #BF5AF2, #5E5CE6); }
.tile.green  { background: linear-gradient(145deg, #63E6A0, #30D158); }
.tile.orange { background: linear-gradient(145deg, #FFD60A, #FF9F0A); }
.sec .t { font-weight: 700; font-size: 1.08rem; letter-spacing: -0.01em; line-height: 1.2; }
.sec .s { color: var(--ink-2); font-size: 0.84rem; margin-top: 1px; }

/* ---------- Inputs ---------- */
div[data-testid="stTextArea"] textarea {
  background: var(--glass-strong) !important;
  border: 1px solid rgba(255,255,255,.85) !important;
  border-radius: 18px !important;
  padding: 14px 16px !important;
  font-size: 0.98rem; line-height: 1.55; color: var(--ink);
  box-shadow: 0 1px 0 rgba(255,255,255,.7) inset, 0 2px 10px rgba(0,0,0,.05);
}
div[data-testid="stTextArea"] textarea:focus {
  border-color: var(--blue) !important;
  box-shadow: 0 0 0 4px rgba(10,132,255,.18) !important;
}
div[data-testid="stTextArea"] label, div[data-testid="stSelectbox"] label { display: none; }
div[data-baseweb="select"] > div {
  background: var(--glass-strong) !important;
  border: 1px solid rgba(255,255,255,.85) !important;
  border-radius: 16px !important; min-height: 48px;
  box-shadow: 0 2px 10px rgba(0,0,0,.05);
}

/* ---------- Buttons (iOS pills) ---------- */
div[data-testid="stButton"] button {
  border-radius: 999px; font-weight: 600; font-size: 0.98rem;
  padding: 0.6rem 1.3rem; transition: transform .12s ease, box-shadow .12s ease;
  border: 1px solid rgba(255,255,255,.85);
  background: var(--glass-strong); color: var(--blue);
  box-shadow: 0 4px 14px rgba(0,0,0,.08);
}
div[data-testid="stButton"] button:hover { transform: translateY(-1px); border-color: var(--blue); color: var(--blue); }
div[data-testid="stButton"] button:active { transform: scale(0.97); }
div[data-testid="stButton"] button[kind="primary"] {
  width: 100%; height: 3.1rem; font-size: 1.05rem; color: #fff; border: none;
  background: linear-gradient(135deg, #0A84FF 0%, #5E5CE6 100%);
  box-shadow: 0 10px 24px rgba(10,132,255,.38), 0 1px 0 rgba(255,255,255,.35) inset;
}
div[data-testid="stButton"] button[kind="primary"]:hover { color: #fff; filter: brightness(1.06); }

/* ---------- Result pieces ---------- */
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 0.8rem; }
.chip {
  background: rgba(10,132,255,.12); color: #0060D1; border-radius: 999px;
  padding: 4px 12px; font-size: 0.8rem; font-weight: 600;
}
.chip.g { background: rgba(48,209,88,.15); color: #1B7F3A; }
.chip.p { background: rgba(94,92,230,.14); color: #3C3AB8; }
.article-body { font-size: 1.02rem; line-height: 1.7; color: var(--ink); white-space: pre-wrap; }

.gloss-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(215px, 1fr)); gap: 12px; }
.gloss-card {
  background: var(--glass-strong); border: 1px solid rgba(255,255,255,.9);
  border-radius: 18px; padding: 13px 15px;
  box-shadow: 0 4px 14px rgba(0,0,0,.06);
}
.gloss-card .term { font-weight: 700; color: var(--indigo); font-size: 0.98rem; margin-bottom: 4px; }
.gloss-card .def { font-size: 0.9rem; color: #3A3A3C; line-height: 1.45; }
.empty { color: var(--ink-2); font-size: 0.95rem; }

.source { font-size: 0.82rem; color: var(--ink-2); margin: 0.5rem 0 0 4px; }
.source a { color: var(--blue); text-decoration: none; }
.foot { text-align: center; color: var(--ink-2); font-size: 0.78rem; margin-top: 1.4rem; }

/* Native alerts to glass */
div[data-testid="stAlert"] {
  border-radius: 18px; border: 1px solid rgba(255,255,255,.8);
  -webkit-backdrop-filter: blur(18px); backdrop-filter: blur(18px);
}

/* Phone-size tweaks */
@media (max-width: 640px) {
  .block-container { padding-left: 0.9rem; padding-right: 0.9rem; }
  .hero h1 { font-size: 1.7rem; }
  [class*="st-key-card_"] { border-radius: 22px; padding: 1rem; }
}
</style>
"""


def section_header(icon: str, color: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="sec"><div class="tile {color}">{icon}</div>'
        f'<div><div class="t">{html.escape(title)}</div>'
        f'<div class="s">{html.escape(subtitle)}</div></div></div>',
        unsafe_allow_html=True,
    )


def render_result(result: Simplification, language: str) -> None:
    word_count = len(result.simplified_article.split())
    st.markdown(
        '<div class="chips">'
        f'<span class="chip">🌐 {html.escape(language)}</span>'
        f'<span class="chip g">📝 {word_count} words</span>'
        f'<span class="chip p">📖 {len(result.glossary)} terms</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    with st.container(key="card_result"):
        section_header("✨", "green", "Simplified article", "Plain language, same facts")
        st.markdown(
            f'<div class="article-body">{html.escape(result.simplified_article)}</div>',
            unsafe_allow_html=True,
        )

    with st.container(key="card_glossary"):
        section_header("📖", "orange", "Medical terms glossary", "Tap-free quick definitions")
        if result.glossary:
            cards = "".join(
                '<div class="gloss-card">'
                f'<div class="term">{html.escape(entry["term"])}</div>'
                f'<div class="def">{html.escape(entry["simple_definition"])}</div>'
                "</div>"
                for entry in result.glossary
            )
            st.markdown(f'<div class="gloss-grid">{cards}</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="empty">No medical terms needed a separate explanation.</div>',
                unsafe_allow_html=True,
            )


st.set_page_config(
    page_title="Health Article Simplifier",
    page_icon="🩺",
    layout="centered",
    initial_sidebar_state="collapsed",
)
st.markdown(GLASS_CSS, unsafe_allow_html=True)

# --- Hero -------------------------------------------------------------------
st.markdown(
    '<div class="hero"><div class="app-icon">🩺</div>'
    "<h1>Health Article Simplifier by Yash Paraskar</h1>"
    "<p>Turn complex health writing into clearer language, with a glossary.</p></div>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="notice"><span class="ico">⚕️</span><span>'
    "This tool explains text; it does not provide medical advice or replace "
    "a conversation with a qualified health professional.</span></div>",
    unsafe_allow_html=True,
)

try:
    sample_articles = load_sample_articles()
except (OSError, json.JSONDecodeError, ValueError) as error:
    sample_articles = []
    st.error(f"Could not load sample articles: {error}")

# --- Step 1: article --------------------------------------------------------
with st.container(key="card_input"):
    section_header("📄", "blue", "1 · Your article", "Paste text or try a sample")
    st.button(
        "🔀  Shuffle sample article",
        disabled=not sample_articles,
        on_click=shuffle_sample_article,
        args=(sample_articles,),
    )
    article = st.text_area(
        "Paste a health article",
        height=260,
        placeholder="Paste the article or the passage you want to understand...",
        key="article_text",
        on_change=clear_sample_attribution,
    )
    if st.session_state.get("selected_sample_url"):
        st.markdown(
            '<div class="source">📎 Sample source: '
            f'<a href="{html.escape(st.session_state["selected_sample_url"], quote=True)}" '
            'target="_blank" rel="noopener">'
            f'{html.escape(st.session_state["selected_sample_title"])}</a></div>',
            unsafe_allow_html=True,
        )

# --- Step 2: language -------------------------------------------------------
with st.container(key="card_language"):
    section_header("🌍", "purple", "2 · Output language", "Choose how you want to read it")
    target_language = st.selectbox("Output language", LANGUAGES)

# --- Action -----------------------------------------------------------------
simplify_clicked = st.button("✨  Simplify article", type="primary")

if simplify_clicked:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not article.strip():
        st.warning("Paste an article before asking for a simplification.")
    elif not api_key:
        st.error(
            "Gemini API key not found. Add GEMINI_API_KEY to a .env file "
            "(see .env.example), then restart the app."
        )
    else:
        try:
            with st.spinner("Simplifying your article..."):
                result = simplify_article(
                    article=article,
                    target_language=target_language,
                    client=genai.Client(api_key=api_key),
                    model=GEMINI_MODEL,
                )
        except (APIError, ValueError) as error:
            st.error(f"Could not simplify the article: {error}")
        else:
            render_result(result, target_language)

st.markdown(
    f'<div class="foot">Powered by Gemini · {html.escape(GEMINI_MODEL)}</div>',
    unsafe_allow_html=True,
)