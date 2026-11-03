"""Turn a script into one MP3 with the free edge-tts voices."""

import asyncio
import re

import edge_tts

from pipeline import HOST_A, HOST_B

# Each speaker has a preferred voice and a backup. List all voices with: edge-tts --list-voices
VOICES = {
    HOST_A: ("en-US-AvaMultilingualNeural", "en-US-JennyNeural"),
    HOST_B: ("en-US-AndrewMultilingualNeural", "en-US-GuyNeural"),
    "NARRATOR": ("en-US-AndrewMultilingualNeural", "en-US-GuyNeural"),
}

LABEL = re.compile(r"^([A-Za-z]+)\s*:\s*(.*)$")


def _clean(line: str) -> str:
    if line.lstrip().startswith("#"):  # Markdown headings are not read aloud
        return ""
    line = re.sub(r"\[[^\]]*\]", "", line)  # stage directions such as [laughs]
    line = line.replace("*", "").replace("#", "").strip()
    return re.sub(r"^[-•]\s+", "", line)


def parse_script(script: str, two_hosts: bool) -> list[tuple[str, str]]:
    segments: list[list[str]] = []
    if two_hosts:
        for raw in script.splitlines():
            line = _clean(raw)
            if not line:
                continue
            match = LABEL.match(line)
            if match and match.group(1).upper() in (HOST_A, HOST_B):
                segments.append([match.group(1).upper(), match.group(2).strip()])
            elif segments:
                segments[-1][1] += " " + line
            else:
                segments.append([HOST_A, line])
    else:
        for paragraph in re.split(r"\n\s*\n", script):
            text = " ".join(filter(None, (_clean(l) for l in paragraph.splitlines())))
            match = LABEL.match(text)
            if match and match.group(1).upper() == "NARRATOR":
                text = match.group(2).strip()
            segments.append(["NARRATOR", text])
    return [(speaker, text) for speaker, text in segments if text]


async def _speak(text: str, voices: tuple[str, ...], limit: asyncio.Semaphore) -> bytes:
    async with limit:
        for voice in voices:
            try:
                audio = bytearray()
                async for chunk in edge_tts.Communicate(text, voice).stream():
                    if chunk["type"] == "audio":
                        audio.extend(chunk["data"])
                if audio:
                    return bytes(audio)
            except edge_tts.exceptions.NoAudioReceived:
                continue
    raise RuntimeError(f"No audio was produced for: {text[:80]}")


def render_audio(segments: list[tuple[str, str]]) -> bytes:
    async def run() -> bytes:
        limit = asyncio.Semaphore(4)
        parts = await asyncio.gather(*(_speak(t, VOICES[s], limit) for s, t in segments))
        return b"".join(parts)  # edge-tts MP3 frames can be joined directly

    return asyncio.run(run())
