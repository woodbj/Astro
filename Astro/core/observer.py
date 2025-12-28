from dataclasses import dataclass


@dataclass
class Observer:
    working_directory: str
    latitude: float = None
    longitude: float = None
    pressure: float = None
    temperature: float = None
