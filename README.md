# Case Podcast

A local app that turns a document into a study brief and a podcast-style MP3.

Upload a PDF or text file, or paste text, and optionally describe what it is and what to focus on. The app works out what kind of document it is and what it is meant to teach. For a teaching case such as an HBS case, the brief covers the decision, a fact sheet, likely discussion questions, analysis, and positions. For other documents, it covers the fact sheet, main ideas, and review questions.

Episodes have two hosts or a single narrator. Before recording, a second pass checks the script against the brief's fact sheet and the source, adds missing facts, and corrects errors.

Claude (`claude-sonnet-5-5`) writes the brief and the script. The voices come from [edge-tts](https://github.com/rany2/edge-tts), which is free and needs no key, but does need an internet connection.

## Setup (Windows)

You need Python 3.13 and [Git for Windows](https://git-scm.com/download/win). Run the commands below in PowerShell. To install Python, run `winget install -e --id Python.Python.3.13`, then open a new PowerShell window. `py -3.13 --version` should print the version.

1. Clone the repository and enter it. Git asks you to sign in to GitHub the first time.

   ```powershell
   git clone https://github.com/yagub01/case-podcast.git
   cd case-podcast
   ```

2. Create a virtual environment and install the dependencies:

   ```powershell
   py -3.13 -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```

3. Add your Anthropic API key (replace `sk-ant-...` with your key):

   ```powershell
   mkdir .streamlit
   Set-Content .streamlit\secrets.toml 'ANTHROPIC_API_KEY = "sk-ant-..."'
   ```

   This file is excluded from Git.

4. Run the app:

   ```powershell
   .venv\Scripts\python -m streamlit run app.py
   ```

   It opens in your browser at http://localhost:8501. Keep the PowerShell window open while you use it.

On later runs, open PowerShell in the `case-podcast` folder and run only step 4.

To get updates after changes are pushed, run `git pull` in the same folder.

## Output

Each run saves `brief.md`, `script.txt`, and `episode.mp3` to a dated folder in `outputs/`.

## Changing voices

Edit `VOICES` in `tts.py`. To list the available voices, run `edge-tts --list-voices`.
