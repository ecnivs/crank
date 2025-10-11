from pathlib import Path
from preset import YmlHandler
from typing import Dict


class Prompt:
    """
    Handles prompt templates loaded from a YAML file and builds formatted prompts.
    """

    def __init__(self) -> None:
        """
        Initialize the Prompt handler and load template mappings from prompt.yml.
        """
        self.prompts: YmlHandler = YmlHandler(Path("prompt.yml"))

        self.output_format: Dict[str, str] = {
            "TRANSCRIPT": self.prompts.get("GET_CONTENT", ""),
            "DESCRIPTION": self.prompts.get("GET_DESCRIPTION", ""),
            "SEARCH_TERM": self.prompts.get("GET_SEARCH_TERM", ""),
            "TITLE": self.prompts.get("GET_TITLE", ""),
            "CATEGORY_ID": self.prompts.get("GET_CATEGORY_ID", ""),
        }

    def build(self, query: str) -> str:
        """
        Construct a prompt for the AI using the loaded templates.

        Args:
            query: Topic or keyword to generate content around.

        Returns:
            str: Formatted prompt including instructions for output format.
        """
        output_lines = [f"{key}: {value}" for key, value in self.output_format.items()]
        output_section = "Provide output in this format: " + " ".join(output_lines)
        return f"Topic: {query}\n\n\n{output_section}"
