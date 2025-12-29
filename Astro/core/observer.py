from dataclasses import dataclass


@dataclass
class Observer:
    latitude: float = None
    longitude: float = None
    pressure: float = None
    temperature: float = None
