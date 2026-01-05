"""Processing pipeline framework for astrophotography image analysis.

This module provides a flexible pipeline system for processing astrophotography images
through a series of configurable processors. It includes:

- Base Processor class for creating custom processors
- Pipeline execution engine
- Pipeline management (save/load, templates, results)
- Automatic processor discovery
"""

from pydantic import Field
from abc import ABC, abstractmethod
import numpy as np
import inspect
import sys
# import json
# import time
# from pathlib import Path
# from typing import Dict, List
from ..core.data import AstroData, Exposure


# class DataEncoder(json.JSONEncoder):
#     """Custom JSON encoder for numpy and Path types."""

#     def default(self, obj):
#         if isinstance(obj, np.ndarray):
#             return obj.tolist()
#         if isinstance(obj, np.integer):
#             return int(obj)
#         if isinstance(obj, np.floating):
#             return float(obj)
#         if isinstance(obj, Path):
#             return str(obj)
#         return super().default(obj)


class Processor(AstroData, ABC):
    log: dict = Field(default_factory=dict)

    @abstractmethod
    def __call__(self, exposure: Exposure) -> Exposure:
        pass


class Pipeline:
    def __init__(self):
        self.output: list[dict] = None
        self.pipeline: list[Processor] = []

    def add(self, processor: Processor):
        self.pipeline.append(processor)

    def run(self, image: np.ndarray, export=False):
        """Run pipeline on image.

        Args:
            image: Input image array
            export: If True, save image and data after each step

        Returns:
            Tuple of (final_image, final_data)
            If export=True, final_data includes 'intermediate_steps' list
        """
        data = dict()
        self.output = []
        if len(self.pipeline) == 0:
            return image, data

        for i, ps in enumerate(self.pipeline):
            image, data = ps(image, data)
            if export:
                self.output.append({"process": type(ps).__name__, "image": image, "data": data})

        return image, data


def discover_processors():
    """
    Discover all Processor subclasses from current module and submodules.

    Returns:
        dict: Dictionary mapping processor class names to class objects
    """
    processor_classes = {}

    # Get processors from current module
    current_module = sys.modules[__name__]
    for name, obj in inspect.getmembers(current_module, inspect.isclass):
        if issubclass(obj, Processor) and obj is not Processor:
            processor_classes[name] = obj

    # Import from processors submodules
    try:
        from ..tools.processors import processors  # noqa: F401

        for module_name in [
            "calibration",
            "background",
            "enhancement",
            "detection",
            "measurement",
            "astrometry",
            "output",
        ]:
            try:
                module = __import__(f"Astro.tools.processors.{module_name}", fromlist=["*"])
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, Processor) and obj is not Processor:
                        processor_classes[name] = obj
            except ImportError:
                pass
    except ImportError:
        pass

    return processor_classes


def get_processors():
    """
    Find all classes that inherit from Processor and return their JSON schemas.

    Returns:
        dict: Dictionary mapping processor names to their JSON schemas
    """
    processor_classes = discover_processors()

    data = {}
    for name, obj in processor_classes.items():
        schema = obj.model_json_schema()
        data[name] = schema

    return data


def build_pipeline(schema: list[dict]) -> Pipeline:
    """Build pipeline from JSON schema.

    Args:
        schema: List of dicts with {"class": "ProcessorName", "params": {...}}

    Returns:
        Pipeline object with processors instantiated

    Example:
        >>> schema = [
        ...     {"class": "Flatten", "params": {"channel": "Green"}},
        ...     {"class": "BackgroundSubtract", "params": {"sigma": 3}}
        ... ]
        >>> pipeline = build_pipeline(schema)
    """
    pipeline = Pipeline()

    # Discover all available processor classes
    processor_classes = discover_processors()

    # Instantiate processors from schema
    for processor in schema:
        class_name = processor["class"]
        params = processor.get("params", {})

        if class_name not in processor_classes:
            raise ValueError(
                f"Unknown processor: {class_name}. Available: {list(processor_classes.keys())}"
            )

        processor = processor_classes[class_name](**params)
        pipeline.add(processor)

    return pipeline


# class PipelineManager:
#     """Manages pipeline serialization, templates, and execution results.

#     The PipelineManager provides a centralized system for:
#     - Building pipelines from JSON schemas
#     - Saving/loading pipeline configurations
#     - Managing predefined templates
#     - Storing and retrieving pipeline execution results

#     Results are organized in a directory structure:
#         results/
#         ├── {exposure_name}_{pipeline_id}_{timestamp}/
#         │   ├── processed.fits  # Processed image
#         │   ├── data.json       # Full pipeline data dict
#         │   ├── star_catalog.csv  # Exported catalog (if generated)
#         │   └── pipeline.json   # Pipeline configuration used
#     """

#     def __init__(self, storage_path: Path = None, results_path: Path = None):
#         """Initialize the pipeline manager.

#         Args:
#             storage_path: Directory for storing pipeline configurations
#             results_path: Directory for storing execution results
#         """
#         self.storage_path = storage_path or Path("./pipelines")
#         self.results_path = results_path or Path("./results")

#         # Create directories if they don't exist
#         self.storage_path.mkdir(exist_ok=True, parents=True)
#         self.results_path.mkdir(exist_ok=True, parents=True)

#     def build(self, schema: List[Dict]) -> Pipeline:
#         """Build pipeline from JSON schema.

#         Args:
#             schema: List of processor configurations

#         Returns:
#             Constructed Pipeline object

#         Example:
#             >>> manager = PipelineManager()
#             >>> schema = [
#             ...     {"class": "Flatten", "params": {"channel": "Green"}},
#             ...     {"class": "SourceDetect", "params": {"min_sigma": 10}}
#             ... ]
#             >>> pipeline = manager.build(schema)
#         """
#         return build_pipeline(schema)

#     def save(self, pipeline: Pipeline, name: str = None) -> str:
#         """Save pipeline configuration to JSON file.

#         Args:
#             pipeline: Pipeline object to save
#             name: Optional name for the pipeline (auto-generated if None)

#         Returns:
#             Pipeline ID (filename without extension)
#         """
#         # Generate pipeline ID
#         pipeline_id = name or f"pipeline_{int(time.time())}"

#         # Convert pipeline to schema
#         schema = []
#         for proc in pipeline.pipeline:
#             schema.append({"class": proc.__class__.__name__, "params": proc.model_dump()})

#         # Save to JSON
#         filepath = self.storage_path / f"{pipeline_id}.json"
#         with open(filepath, "w") as f:
#             json.dump(schema, f, indent=2, cls=DataEncoder)

#         return pipeline_id

#     def load(self, pipeline_id: str) -> Pipeline:
#         """Load pipeline from JSON file.

#         Args:
#             pipeline_id: Pipeline identifier (filename without extension)

#         Returns:
#             Reconstructed Pipeline object

#         Raises:
#             FileNotFoundError: If pipeline file doesn't exist
#         """
#         filepath = self.storage_path / f"{pipeline_id}.json"

#         if not filepath.exists():
#             raise FileNotFoundError(f"Pipeline not found: {pipeline_id}")

#         with open(filepath) as f:
#             schema = json.load(f)

#         return self.build(schema)

#     def get_templates(self) -> Dict[str, List[Dict]]:
#         """Get predefined pipeline templates.

#         Returns:
#             Dictionary mapping template names to pipeline schemas
#         """
#         return {
#             "star_extraction_basic": [
#                 {"class": "Downsample", "params": {"factor": 2, "preserve_dtype": True}},
#                 {"class": "Flatten", "params": {"channel": "Green"}},
#                 {"class": "BackgroundSubtract", "params": {"sigma": 3.0, "n_sigma": 0.0}},
#                 {
#                     "class": "SourceDetect",
#                     "params": {
#                         "min_sigma": 5.0,
#                         "max_sigma": 20.0,
#                         "threshold": 0.01,
#                         "target_channel": "green",
#                         "max_sources": 500,
#                     },
#                 },
#                 {"class": "StarCatalogExport", "params": {"format": "csv", "include_psf": False}},
#             ],
#             "star_extraction_precise": [
#                 {"class": "Downsample", "params": {"factor": 2, "preserve_dtype": True}},
#                 {"class": "Flatten", "params": {"channel": "Green"}},
#                 {"class": "BackgroundSubtract", "params": {"sigma": 3.0, "n_sigma": 0.0}},
#                 {
#                     "class": "SourceDetect",
#                     "params": {
#                         "min_sigma": 5.0,
#                         "max_sigma": 20.0,
#                         "threshold": 0.01,
#                         "target_channel": "green",
#                         "max_sources": 500,
#                     },
#                 },
#                 {"class": "PSFMeasure", "params": {"box_size": 40, "max_sources": 100}},
#                 {"class": "StarCatalogExport", "params": {"format": "csv", "include_psf": True}},
#             ],
#             "focus_assistant": [
#                 {"class": "Downsample", "params": {"factor": 2, "preserve_dtype": True}},
#                 {"class": "Flatten", "params": {"channel": "Green"}},
#                 {
#                     "class": "SourceDetect",
#                     "params": {
#                         "min_sigma": 3.0,
#                         "max_sigma": 15.0,
#                         "threshold": 0.01,
#                         "target_channel": "green",
#                         "max_sources": 50,
#                     },
#                 },
#                 {"class": "PSFMeasure", "params": {"box_size": 40, "max_sources": 50}},
#             ],
#             "star_extraction_fullres": [
#                 {"class": "Flatten", "params": {"channel": "Green"}},
#                 {"class": "BackgroundSubtract", "params": {"sigma": 3.0, "n_sigma": 0.0}},
#                 {
#                     "class": "SourceDetect",
#                     "params": {
#                         "min_sigma": 10.0,
#                         "max_sigma": 30.0,
#                         "threshold": 0.01,
#                         "target_channel": "green",
#                         "max_sources": 1000,
#                     },
#                 },
#                 {"class": "PSFMeasure", "params": {"box_size": 40, "max_sources": 100}},
#                 {"class": "StarCatalogExport", "params": {"format": "csv", "include_psf": True}},
#             ],
#         }

#     def save_results(
#         self, exposure_id: str, pipeline_id: str, image: np.ndarray, data: dict
#     ) -> str:
#         """Save pipeline execution results to disk.

#         Args:
#             exposure_id: Identifier for the exposure (usually file path)
#             pipeline_id: Pipeline identifier
#             image: Processed image array
#             data: Pipeline data dictionary

#         Returns:
#             Result ID (directory name)
#         """
#         # Generate result ID
#         exposure_name = Path(exposure_id).stem
#         timestamp = int(time.time())
#         result_id = f"{exposure_name}_{pipeline_id}_{timestamp}"

#         # Create result directory
#         result_dir = self.results_path / result_id
#         result_dir.mkdir(exist_ok=True, parents=True)

#         # Save intermediate steps if present
#         if "intermediate_steps" in data:
#             steps_dir = result_dir / "steps"
#             steps_dir.mkdir(exist_ok=True)

#             for step_data in data["intermediate_steps"]:
#                 step_num = step_data["step"]
#                 step_image = step_data["image"]
#                 step_name = step_data["processor"]
#                 step_processor = step_data.get("processor_instance")

#                 # Save intermediate image as FITS/NPY
#                 try:
#                     from astropy.io import fits

#                     fits.writeto(
#                         steps_dir / f"step_{step_num:02d}_{step_name}.fits",
#                         step_image,
#                         overwrite=True,
#                     )
#                 except Exception:
#                     np.save(steps_dir / f"step_{step_num:02d}_{step_name}.npy", step_image)

#                 # Save JPG visualization
#                 try:
#                     output_path = steps_dir / f"step_{step_num:02d}_{step_name}"

#                     if step_processor:
#                         # Use processor's custom visualization
#                         step_processor.save_visualization(
#                             step_image, step_data.get("data", {}), output_path
#                         )
#                     else:
#                         # Use base visualization (plain JPG)
#                         from PIL import Image

#                         # Normalize for display
#                         if step_image.dtype in [np.uint16, np.int16]:
#                             vis = (step_image.astype(float) / 65535.0 * 255).astype(np.uint8)
#                         elif step_image.dtype in [np.float32, np.float64]:
#                             img_min, img_max = step_image.min(), step_image.max()
#                             if img_max > img_min:
#                                 vis = ((step_image - img_min) / (img_max - img_min) * 255).astype(
#                                     np.uint8
#                                 )
#                             else:
#                                 vis = np.zeros_like(step_image, dtype=np.uint8)
#                         else:
#                             vis = step_image.astype(np.uint8)

#                         Image.fromarray(vis).save(str(output_path.with_suffix(".jpg")), quality=95)
#                 except Exception as e:
#                     print(f"Warning: Could not save visualization for step {step_num}: {e}")
#                     import traceback

#                     traceback.print_exc()

#             # Remove intermediate images from data before saving JSON (too large)
#             data_copy = data.copy()
#             steps_metadata = []
#             for step in data_copy["intermediate_steps"]:
#                 steps_metadata.append(
#                     {
#                         "step": step["step"],
#                         "processor": step["processor"],
#                         "data": step.get("data", {}),
#                     }
#                 )
#             data_copy["intermediate_steps"] = steps_metadata
#         else:
#             data_copy = data

#         # Save processed image as FITS
#         try:
#             from astropy.io import fits

#             fits.writeto(result_dir / "processed.fits", image, overwrite=True)
#         except Exception as e:
#             print(f"Warning: Could not save FITS image: {e}")
#             # Fall back to numpy format
#             np.save(result_dir / "processed.npy", image)

#         # Save pipeline data as JSON
#         with open(result_dir / "data.json", "w") as f:
#             json.dump(data_copy, f, indent=2, cls=DataEncoder)

#         # Export star catalog if present
#         if "star_catalog" in data:
#             catalog_format = data.get("catalog_format", "csv")

#             if catalog_format == "csv":
#                 import pandas as pd

#                 df = pd.DataFrame(data["star_catalog"])
#                 df.to_csv(result_dir / "star_catalog.csv", index=False)
#             elif catalog_format == "json":
#                 with open(result_dir / "star_catalog.json", "w") as f:
#                     json.dump(data["star_catalog"], f, indent=2, cls=DataEncoder)

#         # Save pipeline configuration used
#         try:
#             pipeline = self.load(pipeline_id)
#             schema = []
#             for proc in pipeline.pipeline:
#                 schema.append({"class": proc.__class__.__name__, "params": proc.model_dump()})
#             with open(result_dir / "pipeline.json", "w") as f:
#                 json.dump(schema, f, indent=2, cls=DataEncoder)
#         except Exception:
#             pass  # Pipeline config save is optional

#         return result_id

#     def get_results(self, result_id: str) -> Dict:
#         """Retrieve pipeline execution results.

#         Args:
#             result_id: Result identifier (directory name)

#         Returns:
#             Dictionary containing result data and file paths

#         Raises:
#             FileNotFoundError: If result directory doesn't exist
#         """
#         result_dir = self.results_path / result_id

#         if not result_dir.exists():
#             raise FileNotFoundError(f"Results not found: {result_id}")

#         # Load data JSON
#         with open(result_dir / "data.json") as f:
#             data = json.load(f)

#         # Find image file
#         image_path = None
#         if (result_dir / "processed.fits").exists():
#             image_path = str(result_dir / "processed.fits")
#         elif (result_dir / "processed.npy").exists():
#             image_path = str(result_dir / "processed.npy")

#         # Find catalog file
#         catalog_path = None
#         if (result_dir / "star_catalog.csv").exists():
#             catalog_path = str(result_dir / "star_catalog.csv")
#         elif (result_dir / "star_catalog.json").exists():
#             catalog_path = str(result_dir / "star_catalog.json")

#         return {
#             "data": data,
#             "image_path": image_path,
#             "catalog_path": catalog_path,
#             "result_dir": str(result_dir),
#         }

#     def list_pipelines(self) -> List[str]:
#         """List all saved pipeline IDs.

#         Returns:
#             List of pipeline identifiers
#         """
#         return [p.stem for p in self.storage_path.glob("*.json")]

#     def list_results(self) -> List[str]:
#         """List all result IDs.

#         Returns:
#             List of result identifiers
#         """
#         return [r.name for r in self.results_path.iterdir() if r.is_dir()]
