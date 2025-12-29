from pydantic import BaseModel, Field
from typing import Literal  # , get_args
from abc import ABC, abstractmethod
import numpy as np
from astropy.stats import sigma_clipped_stats
import inspect
import sys


class Processor(BaseModel, ABC):
    @abstractmethod
    def __call__(self, image: np.ndarray, data: dict):
        pass

    def log_self(self, data):
        if "processor" not in data:
            data["processor"] = []

        data["processor"].append(self.model_json_schema())

class Pipeline:
    pipeline: list[Processor] = []

    def add(self, processor: Processor):
        self.pipeline.append(processor)
    
    def run(self, image: np.ndarray):
        data = dict()
        for ps in self.pipeline:
            image, data = ps(image, data)
        return image, data

class Flatten(Processor):
    channel: Literal["Red", "Green", "Blue"] = "Green"

    def __call__(self, image, data):
        map = {
            "Red": 0,
            "Green": 1,
            "Blue": 2
        }
        return image[:, :, map[self.channel]], data


class BackgroundSubtract(Processor):
    sigma: float = Field(default=3, ge=0, lt=10)
    n_sigma: float = Field(default=0, ge=0, lt=10)

    def __call__(self, image: np.ndarray, data: dict):
        mean, median, std = sigma_clipped_stats(image, sigma=self.sigma)
        image = image - median
        data["mean"] = mean
        data["median"] = median
        data["std"] = std
        self.log_self(data)
        return image, data


def get_processors():
    """
    Find all classes that inherit from Processor in the current module.

    Returns:
        list: A list of class objects that inherit from Processor
    """
    current_module = sys.modules[__name__]
    # processor_subclasses = []

    data = dict()
    for name, obj in inspect.getmembers(current_module, inspect.isclass):
        if issubclass(obj, Processor) and obj is not Processor:
            schema = obj.model_json_schema()
            data[obj.__name__] = schema

    return data

def build_pipeline(schema):
    # return assembled pipeline of processors from schema
    
