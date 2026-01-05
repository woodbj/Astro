"""Pipeline Builder - Interactive image processing pipeline creation.

This module provides a Streamlit interface for:
- Building custom image processing pipelines
- Configuring processor parameters
- Executing pipelines on images
- Viewing results with intermediate step visualizations
"""

import streamlit as st
import json
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import api_get, api_post

st.set_page_config(page_title="Pipeline Builder", layout="wide")


# ============================================================================
# SESSION STATE
# ============================================================================


def initialize_session_state():
    """Initialize all session state variables with default values.

    Session state variables:
        pipeline: List of processor configurations in the current pipeline
        selected_processor_index: Currently selected processor for editing
        available_image_files: List of scanned image files for execution
        last_execution_result: Most recent pipeline execution result
    """
    defaults = {
        "pipeline": [],
        "selected_processor_index": None,
        "available_image_files": [],
        "last_execution_result": None
    }

    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


initialize_session_state()


# ============================================================================
# API CLIENT - Server Communication
# ============================================================================

def get_available_processors():
    """Retrieve all available processor schemas from the API.

    Returns:
        dict: Processor name -> JSON schema mapping, or empty dict on error
    """
    result = api_get("/api/pipeline/processors")
    return result if result is not None else {}


def get_pipeline_templates():
    """Retrieve predefined pipeline templates from the API.

    Returns:
        dict: Template name -> pipeline schema mapping, or empty dict on error
    """
    result = api_get("/api/pipeline/templates")
    return result if result is not None else {}


def execute_pipeline_on_image(pipeline_schema, image_path, save_intermediate_steps=False):
    """Execute a pipeline on an image via the API.

    This is a two-step process:
    1. Build and save the pipeline from schema
    2. Execute the pipeline on the specified image

    Args:
        pipeline_schema: List of processor configurations
        image_path: Absolute path to the image file
        save_intermediate_steps: Whether to save images at each processing step

    Returns:
        tuple: (result_dict, error_message) where result_dict is None on error
    """
    # Step 1: Build pipeline from schema
    build_result = api_post(
        "/api/pipeline/build",
        json={"schema": pipeline_schema, "name": None},
        return_keys=["pipeline_id"]
    )

    if build_result is None:
        return None, "Pipeline build failed"

    pipeline_id = build_result["pipeline_id"]

    # Step 2: Execute the built pipeline
    execution_result = api_post(
        "/api/pipeline/execute",
        json={
            "pipeline_config": st.session_state.pipeline,
            "exposure_id": image_path,
            "save_intermediate": save_intermediate_steps,
        },
        timeout=300,  # 5 minute timeout for processing
        return_full_response=True
    )

    if execution_result is None:
        return None, "Pipeline execution failed"

    return execution_result, None


def save_pipeline_configuration(pipeline_schema, pipeline_name):
    """Save a pipeline configuration to the server.

    Args:
        pipeline_schema: List of processor configurations
        pipeline_name: Name to save the pipeline as

    Returns:
        tuple: (success_bool, error_message) where error_message is None on success
    """
    result = api_post(
        "/api/pipeline/build",
        json={"schema": pipeline_schema, "name": pipeline_name}
    )

    if result is not None:
        return True, None
    else:
        return False, "Save failed"

# ============================================================================
# PIPELINE STATE MANAGEMENT
# ============================================================================


def add_processor_to_pipeline(proc_name, params=None):
    """Add a processor to the current pipeline."""
    new_proc = {"class": proc_name, "params": params or {}}
    st.session_state.pipeline.append(new_proc)


def remove_processor_from_pipeline(idx):
    """Remove processor at index from pipeline."""
    st.session_state.pipeline.pop(idx)
    st.session_state.selected_processor_index = None


def move_processor(idx, direction):
    """Move processor up or down in the pipeline."""
    if direction == "up" and idx > 0:
        st.session_state.pipeline[idx], st.session_state.pipeline[idx - 1] = (
            st.session_state.pipeline[idx - 1],
            st.session_state.pipeline[idx],
        )
        st.session_state.selected_processor_index = idx - 1
    elif direction == "down" and idx < len(st.session_state.pipeline) - 1:
        st.session_state.pipeline[idx], st.session_state.pipeline[idx + 1] = (
            st.session_state.pipeline[idx + 1],
            st.session_state.pipeline[idx],
        )
        st.session_state.selected_processor_index = idx + 1


def clear_pipeline():
    """Clear the entire pipeline."""
    st.session_state.pipeline = []
    st.session_state.selected_processor_index = None


def load_template(template_schema):
    """Load a template into the pipeline."""
    st.session_state.pipeline = template_schema
    st.session_state.selected_processor_index = None


# ============================================================================
# PARAMETER WIDGETS - Dynamic UI Generation
# ============================================================================


def render_processor_params(schema_properties, current_params, key_prefix):
    """Render dynamic Streamlit widgets based on JSON schema properties.

    Args:
        schema_properties: Dictionary of parameter schemas from JSON schema
        current_params: Dictionary of current parameter values
        key_prefix: Unique prefix for widget keys (e.g., "param_0")

    Returns:
        Dictionary of updated parameter values
    """
    updated_params = {}

    for param, spec in schema_properties.items():
        # Skip internal fields
        if param in ["processor"]:
            continue

        param_type = spec.get("type", "string")
        default = current_params.get(param, spec.get("default"))
        description = spec.get("description", "")

        # Render appropriate widget based on parameter type
        if param_type in ["number", "integer"]:
            min_val = spec.get("minimum", 0.0)
            max_val = spec.get("maximum", 100.0)

            if param_type == "number":
                data_type = float
            elif param_type == "integer":
                data_type = int

            value = st.number_input(
                param,
                min_value=data_type(min_val),
                max_value=data_type(max_val),
                value=data_type(default) if default is not None else data_type(min_val),
                help=description,
                key=f"{key_prefix}_{param}",
            )
            updated_params[param] = value

        elif param_type == "string":
            if "enum" in spec:
                # Dropdown for enums
                options = spec["enum"]
                try:
                    default_idx = options.index(default) if default in options else 0
                except (ValueError, TypeError):
                    default_idx = 0

                value = st.selectbox(
                    param,
                    options=options,
                    index=default_idx,
                    help=description,
                    key=f"{key_prefix}_{param}",
                )
                updated_params[param] = value
            else:
                # Text input
                value = st.text_input(
                    param,
                    value=str(default) if default is not None else "",
                    help=description,
                    key=f"{key_prefix}_{param}",
                )
                updated_params[param] = value

        elif param_type == "boolean":
            value = st.checkbox(
                param,
                value=bool(default) if default is not None else False,
                help=description,
                key=f"{key_prefix}_{param}",
            )
            updated_params[param] = value

    return updated_params


# ============================================================================
# UI COMPONENTS - Pipeline Display
# ============================================================================


def render_pipeline_item(idx, proc, is_selected, processors):
    """Render a single processor in the pipeline sequence with inline configuration.

    Args:
        idx: Index of the processor in the pipeline
        proc: Processor dictionary with 'class' and 'params'
        is_selected: Whether this processor is currently selected
        processors: Dictionary of processor schemas for configuration
    """
    proc_name = proc["class"]

    # Header row with controls
    col_num, col_name, col_move, col_del = st.columns([0.5, 3, 1.5, 0.5])

    with col_num:
        st.write(f"**{idx + 1}.**")

    with col_name:
        if st.button(
            proc_name,
            key=f"select_{idx}",
            use_container_width=True,
            type="primary" if is_selected else "secondary",
        ):
            st.session_state.selected_processor_index = idx if not is_selected else None
            st.rerun()

    with col_move:
        move_col1, move_col2 = st.columns(2)
        with move_col1:
            if st.button("⬆", key=f"up_{idx}", disabled=(idx == 0)):
                move_processor(idx, "up")
                st.rerun()
        with move_col2:
            if st.button(
                "⬇", key=f"down_{idx}", disabled=(idx == len(st.session_state.pipeline) - 1)
            ):
                move_processor(idx, "down")
                st.rerun()

    with col_del:
        if st.button("🗑", key=f"del_{idx}"):
            remove_processor_from_pipeline(idx)
            st.rerun()

    # Inline configuration when selected
    if is_selected and proc_name in processors:
        schema = processors[proc_name]

        with st.container():
            st.markdown("---")

            if (
                "properties" in schema
                and len([p for p in schema["properties"].keys() if p not in ["processor"]]) > 0
            ):
                # Render parameter widgets dynamically based on schema
                updated_params = render_processor_params(
                    schema["properties"], proc["params"], f"param_{idx}"
                )
                proc["params"].update(updated_params)
            else:
                st.caption("*No configurable parameters*")

            st.markdown("---")


def render_pipeline_actions():
    """Render pipeline action buttons (clear, copy)."""
    action_col1, action_col2 = st.columns(2)

    with action_col1:
        if st.button(
            "🗑 Clear All", disabled=len(st.session_state.pipeline) == 0, use_container_width=True
        ):
            clear_pipeline()
            st.rerun()

    with action_col2:
        if st.button(
            "📋 Copy JSON", disabled=len(st.session_state.pipeline) == 0, use_container_width=True
        ):
            st.code(json.dumps(st.session_state.pipeline, indent=2))


def render_save_pipeline():
    """Render save pipeline section."""

    st.subheader("💾 Save Pipeline")

    col1, col2 = st.columns([3, 1])

    with col1:
        pipeline_name = st.text_input(
            "Pipeline Name",
            placeholder="my_pipeline",
            help="Enter a name to save this pipeline configuration",
        )

    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        if st.button(
            "Save",
            disabled=len(st.session_state.pipeline) == 0 or not pipeline_name,
            use_container_width=True,
        ):
            success, error = save_pipeline_configuration(st.session_state.pipeline, pipeline_name)
            if success:
                st.success(f"✓ Saved as {pipeline_name}")
            else:
                st.error(f"Save failed: {error}")


def render_template_loader(templates):
    """Render template selection and load button.

    Args:
        templates: Dictionary of template name -> schema
    """
    st.subheader("📥 Load Template")

    if not templates:
        st.info("No templates available")
        return

    col1, col2 = st.columns([3, 1])

    with col1:
        template_names = ["-- Select Template --"] + list(templates.keys())
        selected_template = st.selectbox("Template", template_names, label_visibility="collapsed")

    with col2:
        st.write("")  # Spacing
        if st.button(
            "Load",
            disabled=(selected_template == "-- Select Template --"),
            use_container_width=True,
        ):
            load_template(templates[selected_template])
            st.rerun()


# ============================================================================
# UI COMPONENTS - Processor Selection
# ============================================================================


def render_add_processor_popup(processors):
    """Render add processor button with popup menu.

    Args:
        processors: Dictionary of processor name -> schema
    """
    # Organize processors by category
    categories = {
        "Enhancement": ["Downsample", "Normalize"],
        "Calibration": ["Flatten", "BackgroundSubtract"],
        "Detection": ["SourceDetect"],
        "Measurement": ["PSFMeasure"],
        "Output": ["StarCatalogExport"],
    }

    with st.popover("➕ Add Processor", use_container_width=True):
        st.markdown("### Select a Processor")

        for category, proc_names in categories.items():
            st.markdown(f"**{category}**")
            for proc_name in proc_names:
                if proc_name in processors:
                    schema = processors[proc_name]
                    description = schema.get("description", "")

                    # Show first line of description
                    if description:
                        first_line = description.split("\n")[0]
                        caption = first_line
                    else:
                        caption = ""

                    if st.button(
                        f"{proc_name}",
                        key=f"add_popup_{category}_{proc_name}",
                        help=caption,
                        use_container_width=True,
                    ):
                        # Get default params from schema
                        default_params = {}
                        if "properties" in schema:
                            for param, spec in schema["properties"].items():
                                if "default" in spec:
                                    default_params[param] = spec["default"]

                        add_processor_to_pipeline(proc_name, default_params)
                        st.rerun()

            st.divider()


def render_pipeline_panel(processors):
    """Render the pipeline sequence panel.

    Args:
        processors: Dictionary of processor name -> schema
    """
    st.subheader("🔗 Pipeline Sequence")

    # Display pipeline
    if len(st.session_state.pipeline) == 0:
        st.info("Click '➕ Add Processor' below to start building your pipeline.")
    else:
        for idx, proc in enumerate(st.session_state.pipeline):
            is_selected = idx == st.session_state.selected_processor_index
            render_pipeline_item(idx, proc, is_selected, processors)

    # Add processor button (popup)
    render_add_processor_popup(processors)

    # Pipeline actions
    if len(st.session_state.pipeline) > 0:
        st.divider()
        render_pipeline_actions()


def fetch_image_files(extension="CR3", base_path=".", recursive=True):
    """Fetch image files from filesystem via API.

    Args:
        extension: File extension to search for
        base_path: Base directory to search
        recursive: Whether to search recursively

    Returns:
        List of dicts with 'absolute', 'relative', and 'name' keys
    """
    result = api_get(
        f"/api/filesystem/scan/{extension}",
        params={"path": base_path, "recursive": str(recursive).lower()}
    )

    if result is not None:
        return result.get("files", [])
    else:
        return []


# ============================================================================
# UI PANELS - Main Sections
# ============================================================================


def render_execution_panel():
    """Render the pipeline execution panel."""
    st.header("▶️ Execute Pipeline")

    # # File selection mode
    # file_mode = st.radio(
    #     "Input Mode", ["Browse Files", "Manual Path"], horizontal=True, label_visibility="collapsed"
    # )

    home = api_get("/api/filesystem/cwd")
    st.write(f"**Home Directory** -- {home}")

    exposure_path = None

    file_mode = "Browse Files"
    if file_mode == "Browse Files":
        # File browser
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            base_path = st.text_input(
                "Search Directory", value=".", help="Directory to search for images"
            )

        with col2:
            extension = st.selectbox(
                "File Type",
                ["CR3", "fits", "fit", "jpg", "jpeg", "png", "tif", "tiff"],
                help="Image file extension",
            )

        with col3:
            st.write("")  # Spacing
            st.write("")  # Spacing
            if st.button("🔍 Scan", use_container_width=True):
                with st.spinner("Scanning..."):
                    files = fetch_image_files(extension, base_path, recursive=True)
                    st.session_state.available_image_files = files
                    if files:
                        st.success(f"Found {len(files)} files")
                    else:
                        st.warning("No files found")
                    st.rerun()

        # Display found files
        if "available_image_files" in st.session_state and len(st.session_state.available_image_files) > 0:
            selected_file = st.selectbox(
                f"Select Image ({len(st.session_state.available_image_files)} found)",
                st.session_state.available_image_files,
                format_func=lambda x: x["relative"],  # Show relative path in dropdown
            )
            exposure_path = selected_file["absolute"]  # Use absolute path for execution
        else:
            st.info("Click 'Scan' to search for images")

    else:
        # Manual path entry
        exposure_path = st.text_input(
            "Image Path", placeholder="/path/to/image.CR3", help="Full path to the image file"
        )

    # Execute options
    st.write("")  # Spacing
    show_intermediate = st.checkbox(
        "Save intermediate steps",
        value=True,
        help="Save and display the image after each processing step (useful for debugging)",
    )

    # Execute button
    execute_button = st.button(
        "▶️ Run Pipeline",
        disabled=(len(st.session_state.pipeline) == 0 or not exposure_path),
        use_container_width=True,
        type="primary",
    )

    if execute_button and exposure_path and len(st.session_state.pipeline) > 0:
        with st.spinner("Running pipeline... This may take a minute for large images."):
            result, error = execute_pipeline_on_image(
                st.session_state.pipeline, exposure_path, save_intermediate_steps=show_intermediate
            )

            if error:
                st.error(f"❌ Pipeline execution failed: {error}")
            else:
                st.success("✅ Pipeline completed successfully!")
                # Store results in session state
                st.session_state.last_execution_result = result


def render_results_panel():
    """Render the pipeline results panel."""
    if "last_execution_result" not in st.session_state:
        return

    st.header("📊 Results")

    result = st.session_state.last_execution_result

    # New API format: data is a list of image file paths
    image_paths = result.get("data", [])

    if not image_paths:
        st.info("No results to display")
        return

    # Display all intermediate step images in tabs
    if len(image_paths) > 1:
        st.subheader("Processing Steps")

        # Create tabs for each step
        tab_labels = [f"Step {i}" for i in range(len(image_paths))]
        tabs = st.tabs(tab_labels)

        for idx, (tab, img_path) in enumerate(zip(tabs, image_paths)):
            with tab:
                img_path_obj = Path(img_path)

                # Display the JPEG image
                if img_path_obj.exists():
                    try:
                        from PIL import Image
                        import numpy as np

                        img = Image.open(img_path_obj)
                        st.image(
                            np.array(img),
                            caption=f"Step {idx}: {img_path_obj.stem}",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"Could not load image: {e}")
                else:
                    st.warning(f"Image not found: {img_path}")

                # Try to load and display corresponding JSON data
                json_path = img_path_obj.with_suffix(".json")
                if json_path.exists():
                    try:
                        with open(json_path, "r") as f:
                            step_data = json.load(f)

                        with st.expander("Step Data", expanded=True):
                            # Display metrics in a cleaner format
                            metrics_col1, metrics_col2 = st.columns(2)

                            with metrics_col1:
                                if "num_sources" in step_data:
                                    st.metric("Sources Detected", step_data["num_sources"])
                                if "median_fwhm" in step_data:
                                    st.metric("Median FWHM", f"{step_data['median_fwhm']:.2f} px")
                                if "downsample_factor" in step_data:
                                    st.metric("Downsample Factor", f"{step_data['downsample_factor']}x")

                            with metrics_col2:
                                if "mean_fwhm" in step_data:
                                    st.metric("Mean FWHM", f"{step_data['mean_fwhm']:.2f} px")
                                if "median" in step_data:
                                    st.metric("Background Median", f"{step_data['median']:.1f}")

                            # Show full JSON data
                            with st.expander("Full JSON Data"):
                                st.json(step_data)

                            # Show star catalog if available
                            if "star_catalog" in step_data and step_data["star_catalog"]:
                                st.subheader("Star Catalog")
                                df = pd.DataFrame(step_data["star_catalog"])
                                st.dataframe(df, use_container_width=True, height=300)

                                # Download button
                                csv = df.to_csv(index=False)
                                st.download_button(
                                    "⬇️ Download CSV",
                                    data=csv,
                                    file_name=f"star_catalog_step_{idx}.csv",
                                    mime="text/csv"
                                )
                    except Exception as e:
                        st.warning(f"Could not load JSON data: {e}")

        st.divider()

    # Display final image if only one result or as summary
    st.subheader("Final Result" if len(image_paths) > 1 else "Processed Image")

    final_img_path = Path(image_paths[-1])
    if final_img_path.exists():
        try:
            from PIL import Image
            import numpy as np

            img = Image.open(final_img_path)
            st.image(
                np.array(img),
                caption=f"Final Result: {final_img_path.stem}",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Could not load final image: {e}")

    # Display final JSON data
    final_json_path = final_img_path.with_suffix(".json")
    if final_json_path.exists():
        try:
            with open(final_json_path, "r") as f:
                final_data = json.load(f)

            st.subheader("Final Metrics")

            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)

            with metrics_col1:
                if "num_sources" in final_data:
                    st.metric("Sources Detected", final_data["num_sources"])

            with metrics_col2:
                if "median_fwhm" in final_data:
                    st.metric("Median FWHM", f"{final_data['median_fwhm']:.2f} px")

            with metrics_col3:
                if "mean_fwhm" in final_data:
                    st.metric("Mean FWHM", f"{final_data['mean_fwhm']:.2f} px")
        except Exception as e:
            st.warning(f"Could not load final JSON data: {e}")

    # Show result path
    st.caption(f"Results saved in: `{final_img_path.parent}`")


# ============================================================================
# MAIN LAYOUT
# ============================================================================


def main():
    """Main application layout and orchestration."""
    st.title("🔬 Image Processing Pipeline Builder")

    # Fetch data
    processors = get_available_processors()
    st.json(processors, expanded=False)
    templates = get_pipeline_templates()

    # Single column responsive layout
    # 1. Load Template
    render_template_loader(templates)

    st.divider()

    # 2. Pipeline Sequence (with inline configuration and add button)
    render_pipeline_panel(processors)

    st.divider()

    # 3. Save Pipeline
    if len(st.session_state.pipeline) > 0:
        render_save_pipeline()
        st.divider()

    # 4. Execute Pipeline
    render_execution_panel()

    st.divider()

    # 5. Results
    render_results_panel()

    st.divider()
    st.json(st.session_state.pipeline, expanded=False)


# Run the application
if __name__ == "__main__":
    main()
