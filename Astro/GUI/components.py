import streamlit as st
import requests

camera_settings = ["iso", "aperture", "shutterspeed"]


def set_camera_config():
    out = dict()
    for s in camera_settings:
        out[s] = st.session_state[s]

    print(out)
    requests.post("http://localhost:5000/api/camera/config", json=out)


def get_current_index(data):
    current = data["Current"]
    choices = data["Choices"]
    return [i for i, v in enumerate(choices) if v == current][0]


# block for camera data
def render_camera():
    # get current state
    response = requests.get("http://localhost:5000/api/camera/config")
    data = response.json()
    st.json(data, expanded=False)
    if not data["success"]:
        return

    camera = data["data"]["camera"]
    controller = data["data"]["controller"]

    st.segmented_control(
        label="Camera Mode",
        options=controller['modes'],
        default=controller['mode'],
        key="mode"
    )

    for item in camera_settings:
        config = camera[item]
        st.selectbox(
            label=item,
            options=config["Choices"],
            index=get_current_index(config),
            key=item,
            on_change=set_camera_config
        )

    st.number_input(
        label="Bulb Time",
        min_value=0,
        value=controller['bulb_time'],
        key='bulb_time'
    )

    st.number_input(
        label="Download Interval",
        min_value=0,
        value=controller['download_interval'],
        key='download_interval'
    )
