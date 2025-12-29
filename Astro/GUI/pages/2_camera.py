import streamlit as st
import requests

camera_settings = ["iso", "aperture", "shutterspeed"]


def update():
    camera_changes = dict()
    for key, val in st.session_state['camera'].items():
        if key in st.session_state:
            old = val['Current']
            new = st.session_state[key]
            if old != new:
                camera_changes[key] = new

    controller_changes = dict()
    for key, val in st.session_state['controller'].items():
        if key in st.session_state:
            old = val
            new = st.session_state[key]
            if old != new:
                controller_changes[key] = new

    output = {'camera': camera_changes,
              'controller': controller_changes}

    requests.post("http://localhost:5000/api/camera/config", json=output)


def run_camera():
    update()
    requests.post("http://localhost:5000/api/camera/run")


def get_current_index(data):
    current = data["Current"]
    choices = data["Choices"]
    return [i for i, v in enumerate(choices) if v == current][0]


# block for camera data
def render_camera():
    # get current state
    response = requests.get("http://localhost:5000/api/camera/config")
    data = response.json()
    # st.json(data, expanded=False)
    if not data["success"]:
        return

    camera = data["data"]["camera"]
    controller = data["data"]["controller"]
    st.session_state['camera'] = camera
    st.session_state['controller'] = controller

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
            key=item
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

    st.toggle(
        label="Keep capture on camera",
        value=controller['keep'],
        key="keep"
    )

    st.toggle(
        label="Download to PC",
        value=controller['download'],
        key="download"
    )

    st.button(
        label="Update Configuration",
        on_click=update
    )

    label = "Stop" if controller['active'] else "Run"
    label += f" {controller['mode']}"

    st.button(
        label=label,
        on_click=run_camera
    )

    st.json(data, expanded=False)


render_camera()