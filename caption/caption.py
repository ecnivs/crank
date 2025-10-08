import logging
import spacy
from .stt import SpeechToText


class Handler:
    def __init__(self, workspace, model_size, font):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.workspace = workspace
        self.stt = SpeechToText(model_size)

        self.font = font
        self.nlp = spacy.load("en_core_web_md", disable=["ner", "lemmatizer"])

        self.header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dynamic, {self.font}, 48, &H00FFFFFF, &H000000FF, &H00000000, &H80000000, 1, 0, 0, 0, 100, 100, 0, 0, 1, 2, 0, 5, 50, 50, 20, 1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _format_timestamp(self, ts):
        h = int(ts // 3600)
        m = int((ts % 3600) // 60)
        s = int(ts % 60)
        cs = int((ts - int(ts)) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _apply_pos_coloring(self, words):
        text = " ".join(words)
        doc = self.nlp(text)

        colored_words = []
        for token in doc:
            if token.pos_ == "VERB":
                colored_words.append(r"{\c&HD8BFD8&}" + token.text)
            elif token.pos_ == "PRON":
                colored_words.append(r"{\c&FFDAB9&}" + token.text)
            else:
                colored_words.append(token.text)

        return colored_words

    def get_captions(self, audio_path):
        result = self.stt.transcribe(audio_path)
        path = self.workspace / "captions.ass"

        with open(path, "w", encoding="utf-8") as f:
            f.write(self.header)

            for segment in result.get("segments", []):
                words_data = segment.get("words", [])

                if not words_data:
                    start = self._format_timestamp(segment["start"])
                    end = self._format_timestamp(segment["end"])
                    text = segment["text"].strip()
                    f.write(f"Dialogue: 0,{start},{end},Dynamic,,0,0,0,,{text}\n")
                    continue

                i = 0
                while i < len(words_data):
                    current_word = words_data[i]["word"].strip()
                    if len(current_word) > 8:
                        chunk_size = 1
                    else:
                        chunk_size = 1
                        total_chars = len(current_word)

                        for j in range(i + 1, min(i + 2, len(words_data))):
                            next_word = words_data[j]["word"].strip()
                            if total_chars + len(next_word) + 1 > 20:
                                break
                            if len(next_word) > 8:
                                break

                            chunk_size += 1
                            total_chars += len(next_word) + 1
                            if chunk_size >= 3:
                                break

                    word_chunk = words_data[i : i + chunk_size]
                    start_time = word_chunk[0]["start"]
                    end_time = word_chunk[-1]["end"]

                    words_text = [word["word"].strip() for word in word_chunk]
                    colored_words = self._apply_pos_coloring(words_text)
                    formatted_text = " ".join(colored_words)

                    start = self._format_timestamp(start_time)
                    end = self._format_timestamp(end_time)
                    f.write(
                        f"Dialogue: 0,{start},{end},Dynamic,,0,0,0,,{formatted_text}\n"
                    )
                    i += chunk_size

        self.logger.info(f"ASS saved to {path}")
        return path
