from pathlib import Path
import yaml
from typing import Any, Optional, Dict


class YmlHandler:
    """
    Simple YAML-based state handler.
    """

    def __init__(self, path: Path) -> None:
        """
        Initialize handler with YAML file path.

        Args:
            path: Path to YAML file.
        """
        self.path: Path = path
        self.state: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        """
        Load the YAML file into memory.

        Returns:
            Dict[str, Any]: Dictionary representing the YAML state.
        """
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def save(self) -> None:
        """Persist current state back to YAML file."""
        with self.path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(self.state, f, default_flow_style=False)

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Get a value from the state.

        Args:
            key: Key to retrieve.
            default: Default value if key does not exist.

        Returns:
            Any: Value from the state or default.
        """
        return self.state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a value in the state and save to file.

        Args:
            key: Key to set.
            value: Value to store.
        """
        self.state[key] = value
        self.save()

    def delete(self, key: str) -> None:
        """
        Delete a key from the state if it exists and save.

        Args:
            key: Key to delete.
        """
        if key in self.state:
            del self.state[key]
            self.save()

    def update(self, new_state: Dict[str, Any]) -> None:
        """
        Update multiple keys at once and save.

        Args:
            new_state: Dictionary of key-value pairs to merge into state.
        """
        self.state.update(new_state)
        self.save()
