from dataclasses import dataclass, asdict
import json


@dataclass
class Observer:
    home: str
    latitude: float
    longitude: float

    def save(self):
        with open(f"{type(self).__name__}.json", 'w') as f:
            json.dump(asdict(self), f)

    @classmethod
    def load(cls):
        try:
            with open(f"{type(cls).__name__}.json", 'r') as f:
                data = json.load(f)
                return cls(**data)
        except Exception:
            return cls()
