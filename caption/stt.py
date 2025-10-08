from faster_whisper import WhisperModel
import logging


class SpeechToText:
    def __init__(self, model_size):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model = WhisperModel(model_size)

    def transcribe(self, audio_path):
        return self.model.transcribe(audio_path, word_timestamps=True)
