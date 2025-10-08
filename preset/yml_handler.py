import yaml


class YmlHandler:
    def __init__(self, path):
        self.path = path
        self.state = self._load()

    def _load(self):
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def save(self):
        with self.path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(self.state, f, default_flow_style=False)

    def get(self, key, default=None):
        return self.state.get(key, default)

    def set(self, key, value):
        self.state[key] = value
        self.save()

    def delete(self, key):
        if key in self.state:
            del self.state[key]
            self.save()

    def update(self, new_state: dict):
        self.state.update(new_state)
        self.save()
