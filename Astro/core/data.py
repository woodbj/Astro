from pathlib import Path
from pydantic import BaseModel, Field, field_serializer
import uuid
from queue import Queue
import numpy as np
from datetime import datetime
from threading import Lock
import json
import time


class AstroData(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    unique_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    def __hash__(self):
        return hash(self.unique_id)

    def __eq__(self, other):
        if not isinstance(other, AstroData):
            return False
        return self.unique_id == other.unique_id

    @field_serializer("*", when_used="json")
    def serialize_paths(self, value):
        if isinstance(value, Path):
            return str(value.absolute())
        if isinstance(value, np.ndarray):
            return value.shape
        return value

    def dump(self, filename: Path):
        data = self.model_dump_json(indent=2)
        with open(filename.with_suffix(".json"), 'w') as f:
            f.write(data)

    @classmethod
    def load(cls, input: Path | dict | str):
        if isinstance(input, Path):
            with open(input, 'r') as f:
                input = json.load(f)

        if isinstance(input, str):
            import ast
            input = ast.literal_eval(input)

        if isinstance(input, dict):
            return cls.model_validate(input)


class Star(AstroData):
    x: float | None = Field(default=None)
    y: float | None = Field(default=None)
    fwhm_x: float | None = Field(default=None)
    fwhm_y: float | None = Field(default=None)
    roundness: float | None = Field(default=None)


class Exposure(AstroData):
    path: Path
    # from EXIF data
    iso: int | None = Field(default=None)
    aperture: float | None = Field(default=None)
    shutter: int | None = Field(default=None)
    time: datetime | None = Field(default=None)
    # from sigma_clipped_stats
    mean: float | None = Field(default=None)
    median: float | None = Field(default=None)
    std: float | None = Field(default=None)
    # from source detection
    stars: list[Star] | None = Field(default=None)
    # from plate solve
    ra: float | None = Field(default=None)
    dec: float | None = Field(default=None)
    alt: float | None = Field(default=None)
    az: float | None = Field(default=None)
    # loaded by processes
    image: np.ndarray | None = Field(default=None, exclude=True)
    height: int | None = Field(default=None)
    width: int | None = Field(default=None)


class Observer(AstroData):
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)
    pressure: float | None = Field(default=None)
    temperature: float | None = Field(default=None)


class Drift(AstroData):
    e1: str | None = Field(default=None)
    e2: str | None = Field(default=None)
    time: datetime | None = Field(default=None)
    d_ra: float | None = Field(default=None)
    d_dec: float | None = Field(default=None)


class ExposureLibrary:
    def __init__(self, type):
        self.type = type
        self.data: set = set()
        self.queue: Queue = Queue()
        self.lock: Lock = Lock()

    def get_ordered_list(self, key):
        out = list(self.data)
        out.sort(key=lambda x: x.__getattribute__(key))
        return out

    def put_files(self, files: set[Path] | None):
        if files is None:
            return

        with self.lock:
            file = list(files)

            for file in files:
                try:
                    exp = self.type.load(file)
                except Exception:
                    print("Library failed to load")
                    exp = self.type(path=file)
                if exp not in self.data:
                    self.data.update({exp})
                    self.queue.put(exp)

    def available(self):
        return not self.queue.empty()

    def get_unprocessed(self, wait=False) -> Exposure | None:
        if wait:
            while not self.available():
                time.sleep(0.5)

        if self.queue.empty():
            return None
        with self.lock:
            return self.queue.get()
