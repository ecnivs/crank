from pathlib import Path
from preset import YmlHandler


class Prompt:
    def __init__(self):
        self.prompts = YmlHandler(Path("prompt.yml"))

        self.output_format = {
            "TRANSCRIPT": self.prompts.get("GET_CONTENT"),
            "DESCRIPTION": self.prompts.get("GET_DESCRIPTION"),
            "SEARCH_TERM": self.prompts.get("GET_SEARCH_TERM"),
            "TITLE": self.prompts.get("GET_TITLE"),
            "CATEGORY_ID": self.prompts.get("GET_CATEGORY_ID"),
        }

    def build(self, query):
        output_lines = [f"{key}: {value}" for key, value in self.output_format.items()]
        output_section = "Provide output in this format: " + " ".join(output_lines)
        return f"Topic: {query}\n\n\n{output_section}"
