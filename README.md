# Case Podcast

A local app that turns an HBS case, or any document, into a study brief and a podcast-style MP3.

- **Case prep:** upload a case. The app matches it to one of your courses and sessions, writes a prep brief (fact sheet, likely discussion questions, analysis, positions), and records an episode.
- **Any document:** upload or paste any text and get a brief and an episode.

Both modes offer two hosts or a single narrator. Before recording, a second pass checks the script against the brief's fact sheet and the source, adds missing facts, and corrects errors.

Claude (`claude-opus-5-5`) writes the brief and the script. The voices come from [edge-tts](https://github.com/rany2/edge-tts), which is free and needs no key, but does need an internet connection.

## Setup (macOS)

1. Clone the repository and enter it:

   ```bash
   git clone https://github.com/yagub01/case-podcast.git
   cd case-podcast
   ```

2. Create a virtual environment and install the dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Add your Anthropic API key. Create `.streamlit/secrets.toml` containing:

   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```

   This file is excluded from Git. Exporting `ANTHROPIC_API_KEY` in your shell also works.

4. Run the app:

   ```bash
   streamlit run app.py
   ```

   It opens in your browser at http://localhost:8501.

On later runs, only `source .venv/bin/activate` and `streamlit run app.py` are needed.

## Course profiles

Course profiles live in `courses/`, one Markdown file per course. `courses/README.md` contains the prompt that generates a profile from your existing Claude chats.

## Output

Each run saves `brief.md`, `script.txt`, and `episode.mp3` to a dated folder in `outputs/`.

## Changing voices

Edit `VOICES` in `tts.py`. To list the available voices, run `edge-tts --list-voices`.
