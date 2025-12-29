import streamlit as st
import requests

st.set_page_config("Camera Control")


def update():
    changes = dict()
    for key, val in st.session_state["observer"].items():
        if key in st.session_state:
            old = val
            new = st.session_state[key]
            if old != new:
                changes[key] = new

    requests.post(f"http://{localhost}:5000/api/session/config", json=changes)


localhost = "192.168.86.139"
response = requests.get(f"http://{localhost}:5000/api/session/config")
data = response.json()

# st.json(data, expanded=False)
data = data["data"]
st.session_state["observer"] = data

st.header("Observer Data")
st.number_input(label="Latitude", value=data["latitude"], key="latitude", on_change=update)
st.number_input(label="Longitude", value=data["longitude"], key="longitude", on_change=update)
st.number_input(label="Pressure", value=data["pressure"], key="pressure", on_change=update)
st.number_input(label="Temperature", value=data["temperature"], key="temperature", on_change=update)
# main window shows live feed
