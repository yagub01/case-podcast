import os
import re
from datetime import datetime
from pathlib import Path

import anthropic
import streamlit as st

from pipeline import WORDS_PER_MINUTE, PipelineError, Source, check_script, make_brief, write_script
from tts import parse_script, render_audio

APP_NAME = "Personal Notebook LLM"
OUTPUTS = Path(__file__).parent / "outputs"

st.set_page_config(page_title=APP_NAME, page_icon="🎧", layout="centered")

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap');

:root {
  --ink: #1D1B18;
  --muted: #6B665E;
  --paper: #F6F4EF;
  --card: #FFFFFF;
  --line: #E2DDD2;
  --accent: #3B4FD8;
  --accent-soft: #E8EBFC;
}

html, body, [class*="css"], .stMarkdown, p, label, input, textarea, button {
  font-family: 'Inter', system-ui, sans-serif;
}
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
[data-testid="stMainBlockContainer"], .block-container {
  max-width: 820px;
  padding-top: 2.5rem;
  padding-bottom: 4rem;
}

.hero { text-align: center; padding: 1.5rem 0 1rem; }
.eyebrow {
  display: inline-block;
  font-size: 0.78rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--accent); background: var(--accent-soft);
  padding: 0.35rem 0.8rem; border-radius: 999px; margin-bottom: 1.1rem;
}
.hero h1 {
  font-family: 'Fraunces', Georgia, serif; font-weight: 600;
  font-size: clamp(2.2rem, 6vw, 3.4rem); line-height: 1.05; letter-spacing: -0.02em;
  color: var(--ink); margin: 0 0 0.9rem; padding: 0;
}
.lede {
  font-size: 1.08rem; line-height: 1.6; color: var(--muted);
  max-width: 560px; margin: 0 auto !important; display: block;
}

.steps {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.9rem;
  margin: 2rem 0 2.2rem;
}
.step {
  background: var(--card); border: 1px solid var(--line); border-radius: 14px;
  padding: 1.1rem 1.1rem 1rem;
}
.step .num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 1.7rem; height: 1.7rem; border-radius: 50%;
  background: var(--ink); color: var(--paper); font-size: 0.85rem; font-weight: 600;
  margin-bottom: 0.7rem;
}
.step h3 { font-size: 1rem; font-weight: 600; color: var(--ink); margin: 0 0 0.3rem; padding: 0; }
.step p { font-size: 0.9rem; line-height: 1.5; color: var(--muted); margin: 0; }
@media (max-width: 640px) { .steps { grid-template-columns: 1fr; } }

.section-title {
  font-family: 'Fraunces', Georgia, serif !important; font-weight: 600; font-size: 1.45rem !important;
  color: var(--ink); margin: 0.2rem 0 0.2rem;
}
.section-note { font-size: 0.92rem; color: var(--muted); margin: 0 0 0.6rem; }

[class*="st-key-card"] {
  background: var(--card); border: 1px solid var(--line) !important; border-radius: 16px !important;
  padding: 1.4rem 1.5rem !important;
  box-shadow: 0 1px 2px rgba(29, 27, 24, 0.04), 0 8px 24px rgba(29, 27, 24, 0.05);
}
.stButton button[kind="primary"] {
  height: 3rem; border-radius: 12px; font-weight: 600; font-size: 1rem;
}
.stDownloadButton button { border-radius: 10px; }
.stTabs [data-baseweb="tab-list"] { gap: 0.5rem; }

.foot { text-align: center; font-size: 0.82rem; color: var(--muted); margin-top: 3rem; }
</style>
"""

HERO = f"""
<div class="hero">
  <div class="eyebrow">Study podcasts from your own documents</div>
  <h1>{APP_NAME}</h1>
  <p class="lede">Upload a case, a reading, or any document. Get a fact-checked study brief and a
  podcast episode that walks you through what matters.</p>
</div>
"""

STEPS = """
<div class="steps">
  <div class="step"><span class="num">1</span><h3>Add a document</h3>
    <p>Upload a PDF or text file, or paste text. Add a note on what to focus on.</p></div>
  <div class="step"><span class="num">2</span><h3>Claude reads it</h3>
    <p>It works out what the document is meant to teach and writes a brief with the key facts.</p></div>
  <div class="step"><span class="num">3</span><h3>Listen</h3>
    <p>Two hosts or a single narrator take you through it, checked against the source.</p></div>
</div>
"""

st.markdown(STYLE, unsafe_allow_html=True)
st.markdown(HERO, unsafe_allow_html=True)

if not os.environ.get("ANTHROPIC_API_KEY"):
    try:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        st.error("No Anthropic API key found. See README.md, step 3.")
        st.stop()

try:
    password = st.secrets.get("APP_PASSWORD")
except Exception:
    password = None
if password and not st.session_state.get("signed_in"):
    with st.container(key="card1"):
        st.markdown('<p class="section-title">Sign in</p>', unsafe_allow_html=True)
        entered = st.text_input("Password", type="password")
        if entered == password:
            st.session_state.signed_in = True
            st.rerun()
        if entered:
            st.error("Wrong password.")
    st.stop()

st.markdown(STEPS, unsafe_allow_html=True)

with st.container(key="card2"):
    st.markdown('<p class="section-title">Create an episode</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-note">A 20-minute episode takes a few minutes to generate.</p>',
        unsafe_allow_html=True,
    )
    upload_tab, paste_tab = st.tabs(["Upload a file", "Paste text"])
    with upload_tab:
        uploaded = st.file_uploader("Document", type=["pdf", "txt", "md"], label_visibility="collapsed")
    with paste_tab:
        pasted = st.text_area("Text", height=160, label_visibility="collapsed",
                              placeholder="Paste the text of an article, notes, or a chapter.")
    description = st.text_area(
        "What is it, and what should the episode focus on? (optional)",
        placeholder="For example: a case for my strategy class. Focus on the pricing decision.",
        height=80,
    )
    left, right = st.columns([1, 1.4], gap="large")
    with left:
        fmt = st.segmented_control("Format", ["Two hosts", "Single narrator"], default="Two hosts")
    with right:
        minutes = st.slider("Length (minutes)", 5, 40, 20)
    two_hosts = fmt != "Single narrator"
    generate = st.button("Generate episode", type="primary", width="stretch")


def get_source() -> Source | None:
    if uploaded is not None:
        name = Path(uploaded.name).stem
        if uploaded.name.lower().endswith(".pdf"):
            return Source(name, pdf_bytes=uploaded.getvalue())
        return Source(name, text=uploaded.getvalue().decode("utf-8", errors="replace"))
    if pasted.strip():
        return Source("Pasted document", text=pasted.strip())
    return None


if generate:
    source = get_source()
    if source is None:
        st.warning("Upload a file or paste some text first.")
        st.stop()

    try:
        with st.status("Working on your episode…", expanded=True) as status:
            st.write("Reading the document and writing the brief…")
            brief = make_brief(source, description)
            st.write("Writing the script…")
            draft = write_script(source, brief, description, two_hosts, minutes)
            st.write("Checking the script against the source…")
            script = check_script(source, brief, draft, minutes)
            segments = parse_script(script, two_hosts)
            st.write(f"Recording audio ({len(segments)} segments)…")
            audio = render_audio(segments)
            status.update(label="Your episode is ready", state="complete", expanded=False)
    except (PipelineError, anthropic.APIError) as e:
        st.error(f"Claude request failed: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Something went wrong: {e}")
        st.stop()

    slug = re.sub(r"[^a-z0-9]+", "-", source.name.lower()).strip("-")[:50] or "episode"
    folder = OUTPUTS / f"{datetime.now():%Y-%m-%d-%H%M}-{slug}"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "brief.md").write_text(brief, encoding="utf-8")
        (folder / "script.txt").write_text(script, encoding="utf-8")
        (folder / "episode.mp3").write_bytes(audio)
    except OSError:
        pass  # saving a copy is optional; the downloads below still work

    st.session_state.result = {
        "brief": brief, "script": script, "audio": audio, "slug": slug, "title": source.name,
    }

result = st.session_state.get("result")
if result:
    words = len(result["script"].split())
    with st.container(key="card3"):
        st.markdown(f'<p class="section-title">{result["title"]}</p>', unsafe_allow_html=True)
        st.markdown(
            f'<p class="section-note">About {round(words / WORDS_PER_MINUTE)} minutes</p>',
            unsafe_allow_html=True,
        )
        st.audio(result["audio"], format="audio/mp3")
        col1, col2, col3 = st.columns(3)
        col1.download_button("Download MP3", result["audio"], f"{result['slug']}.mp3",
                             "audio/mpeg", width="stretch")
        col2.download_button("Download brief", result["brief"], f"{result['slug']}-brief.md",
                             width="stretch")
        col3.download_button("Download script", result["script"], f"{result['slug']}-script.txt",
                             width="stretch")

    with st.container(key="card4"):
        brief_tab, script_tab = st.tabs(["Study brief", "Script"])
        brief_tab.markdown(result["brief"])
        script_tab.text(result["script"])

st.markdown('<p class="foot">Written by Claude · Voiced with free text-to-speech</p>',
            unsafe_allow_html=True)
