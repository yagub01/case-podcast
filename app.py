import os
import re
from datetime import datetime
from pathlib import Path

import anthropic
import streamlit as st

from pipeline import WORDS_PER_MINUTE, PipelineError, Source, check_script, make_brief, write_script
from tts import parse_script, render_audio

OUTPUTS = Path(__file__).parent / "outputs"

st.set_page_config(page_title="Case Podcast", page_icon="🎧")
st.title("Case Podcast")

if not os.environ.get("ANTHROPIC_API_KEY"):
    try:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        st.error("No Anthropic API key found. See README.md, step 3.")
        st.stop()

uploaded = st.file_uploader("Upload a document", type=["pdf", "txt", "md"])
pasted = st.text_area("Or paste text", height=120)
description = st.text_area(
    "Describe it (optional)",
    placeholder="For example: HBS case for my Strategy & Technology class. Focus on the bundling decision.",
    height=80,
)
two_hosts = st.radio("Format", ["Two hosts", "Single narrator"], horizontal=True) == "Two hosts"
minutes = st.slider("Episode length (minutes)", 5, 40, 20)


def get_source() -> Source | None:
    if uploaded is not None:
        name = Path(uploaded.name).stem
        if uploaded.name.lower().endswith(".pdf"):
            return Source(name, pdf_bytes=uploaded.getvalue())
        return Source(name, text=uploaded.getvalue().decode("utf-8", errors="replace"))
    if pasted.strip():
        return Source("Pasted document", text=pasted.strip())
    return None


if st.button("Generate", type="primary"):
    source = get_source()
    if source is None:
        st.warning("Upload a file or paste some text first.")
        st.stop()

    try:
        with st.status("Working…", expanded=True) as status:
            st.write("Reading the document and writing the brief…")
            brief = make_brief(source, description)
            st.write("Writing the script…")
            draft = write_script(source, brief, description, two_hosts, minutes)
            st.write("Checking the script against the fact sheet…")
            script = check_script(source, brief, draft, minutes)
            segments = parse_script(script, two_hosts)
            st.write(f"Recording audio ({len(segments)} segments)…")
            audio = render_audio(segments)
            status.update(label="Done", state="complete")
    except (PipelineError, anthropic.APIError) as e:
        st.error(f"Claude request failed: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Something went wrong: {e}")
        st.stop()

    slug = re.sub(r"[^a-z0-9]+", "-", source.name.lower()).strip("-")[:50] or "episode"
    folder = OUTPUTS / f"{datetime.now():%Y-%m-%d-%H%M}-{slug}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(brief, encoding="utf-8")
    (folder / "script.txt").write_text(script, encoding="utf-8")
    (folder / "episode.mp3").write_bytes(audio)

    st.session_state.result = {
        "brief": brief, "script": script, "audio": audio, "folder": str(folder), "slug": slug,
    }

result = st.session_state.get("result")
if result:
    words = len(result["script"].split())
    st.subheader("Episode")
    st.caption(f"About {round(words / WORDS_PER_MINUTE)} minutes. Saved to {result['folder']}")
    st.audio(result["audio"], format="audio/mp3")

    col1, col2, col3 = st.columns(3)
    col1.download_button("Download MP3", result["audio"], f"{result['slug']}.mp3", "audio/mpeg")
    col2.download_button("Download brief", result["brief"], f"{result['slug']}-brief.md")
    col3.download_button("Download script", result["script"], f"{result['slug']}-script.txt")

    brief_tab, script_tab = st.tabs(["Brief", "Script"])
    brief_tab.markdown(result["brief"])
    script_tab.text(result["script"])
