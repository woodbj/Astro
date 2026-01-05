import sys
from pathlib import Path

# Path manipulation before other imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st  # noqa: E402
import time  # noqa: E402
from config import api_get, api_post, FLASK_URL  # noqa: E402

camera_settings = ["iso", "aperture", "shutterspeed"]


def update():
    camera_changes = dict()
    for key, val in st.session_state["camera"].items():
        if key in st.session_state:
            old = val["Current"]
            new = st.session_state[key]
            if old != new:
                camera_changes[key] = new

    controller_changes = dict()
    for key, val in st.session_state["controller"].items():
        if key in st.session_state:
            old = val
            new = st.session_state[key]
            if old != new:
                controller_changes[key] = new

    output = {"camera": camera_changes, "controller": controller_changes}

    api_post("/api/camera/config", json=output)


def run_camera():
    api_post("/api/camera/run")


def get_current_index(data):
    current = data["Current"]
    choices = data["Choices"]
    return [i for i, v in enumerate(choices) if v == current][0]


def render_no_camera():
    st.header("Please connect camera and refresh")


def render_camera():
    # get current state
    response_data = api_get("/api/camera/config")

    if not response_data:
        render_no_camera()
        return

    camera = response_data["camera"]
    controller = response_data["controller"]
    st.session_state["camera"] = camera
    st.session_state["controller"] = controller

    active = controller['active']

    st.segmented_control(
        label="Camera Mode",
        options=controller["modes"],
        default=controller["mode"],
        key="mode",
        on_change=update,
        disabled=active
    )

    unix_time = camera['datetimeutc']['Current']
    st.write(f"Camera Time: {time.ctime(int(unix_time))}")

    for item in camera_settings:
        config = camera[item]
        st.selectbox(
            label=item,
            options=config["Choices"],
            index=get_current_index(config),
            key=item,
            on_change=update,
            disabled=active
        )

    if camera["shutterspeed"]["Current"] == "bulb":
        st.number_input(
            label="Bulb Time",
            min_value=0,
            value=controller["bulb_time"],
            key="bulb_time",
            on_change=update,
            disabled=active
        )

    if controller["mode"] == "Schedule":
        st.number_input(
            label="Download Interval",
            min_value=0,
            value=controller["download_interval"],
            key="download_interval",
            on_change=update,
            disabled=active
        )

    if controller["mode"] != "Stream":
        st.toggle(
            label="Keep capture on camera",
            value=controller["keep"],
            key="keep",
            on_change=update,
            disabled=active
        )

        st.toggle(
            label="Download to PC",
            value=controller["download"],
            key="download",
            on_change=update,
            disabled=active
        )

    label = "Stop" if controller["active"] else "Run"
    label += f" {controller['mode']}"

    st.button(label=label, on_click=run_camera)

    if controller["mode"] == "Stream" and controller["active"]:
        st.link_button(label="Open Feed", url=f"{FLASK_URL}/video_feed")

    st.json(response_data, expanded=False)


render_camera()
