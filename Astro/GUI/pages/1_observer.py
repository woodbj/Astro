import sys
from pathlib import Path

# Path manipulation before other imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st  # noqa: E402
from config import api_get, api_post  # noqa: E402

st.set_page_config("Observer Configuration")


def update():
    changes = dict()
    for key, val in st.session_state["observer"].items():
        if key in st.session_state:
            old = val
            new = st.session_state[key]
            if old != new:
                changes[key] = new

    api_post("/api/session/config", json=changes)


data = api_get("/api/session/config")

if data:
    st.session_state["observer"] = data
else:
    st.error("Failed to load observer configuration")
    st.stop()

st.header("Observer Data")
st.number_input(label="Latitude", value=data["latitude"], key="latitude", on_change=update)
st.number_input(label="Longitude", value=data["longitude"], key="longitude", on_change=update)
st.number_input(label="Pressure", value=data["pressure"], key="pressure", on_change=update)
st.number_input(label="Temperature", value=data["temperature"], key="temperature", on_change=update)
# main window shows live feed
