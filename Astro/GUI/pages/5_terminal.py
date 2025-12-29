"""
Interactive Python Terminal - Streamlit Page
Provides a REPL interface with access to live server camera and controller objects.
"""
import streamlit as st
import requests

# Page config
st.set_page_config(page_title="Python Terminal", layout="wide")

# Server configuration
SERVER_URL = st.session_state.get('server_url', 'http://localhost:5000')

# Initialize session state for command history and output
if 'command_history' not in st.session_state:
    st.session_state.command_history = []
if 'output_history' not in st.session_state:
    st.session_state.output_history = []
if 'server_namespace' not in st.session_state:
    st.session_state.server_namespace = {}


def execute_code(code):
    """Execute Python code on the server and get results."""
    try:
        response = requests.post(
            f"{SERVER_URL}/api/terminal/execute",
            json={"code": code},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data.get('output', ''), data.get('error')
            else:
                return '', data.get('error', 'Unknown error')
        else:
            return '', f"HTTP Error {response.status_code}: {response.text}"

    except requests.exceptions.ConnectionError:
        return '', f"Cannot connect to server at {SERVER_URL}. Is the Flask server running?"
    except Exception as e:
        return '', f"Request error: {str(e)}"


def get_namespace():
    """Get the current namespace from the server."""
    try:
        response = requests.get(
            f"{SERVER_URL}/api/terminal/namespace",
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data.get('namespace', {})

        return {}

    except Exception:
        return {}


# Title
st.title("🐍 Interactive Python Terminal")

st.markdown(f"""
This interactive terminal connects to your Flask server at `{SERVER_URL}` and provides
a Python REPL with access to **live** server objects:
- `camera` - Live Camera instance
- `camera_controller` - Live CameraController instance
- `app` - Flask application instance

All code executes on the server in the same memory space as your running Flask app.
""")

# Main layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Console")

    # Server connection status
    try:
        namespace = get_namespace()
        st.success(f"✓ Connected to server at {SERVER_URL}")
        st.session_state.server_namespace = namespace
    except Exception as e:
        st.error(f"✗ Cannot connect to server at {SERVER_URL}")
        st.info("Make sure your Flask server is running with: "
                "`python -m Astro.server`")

    # Code input
    code_input = st.text_area(
        "Enter Python code:",
        height=150,
        key="code_input",
        placeholder=("# Interact with live server objects:\n"
                     "print(camera)\n"
                     "camera.get_config()\n\n"
                     "# Or inspect available objects:\n"
                     "dir()")
    )

    # Execute button
    col_exec, col_clear = st.columns([1, 1])

    with col_exec:
        if st.button("Execute (Ctrl+Enter)", type="primary",
                     use_container_width=True):
            if code_input.strip():
                stdout, stderr = execute_code(code_input)

                # Add to history
                st.session_state.command_history.append(code_input)
                st.session_state.output_history.append({
                    'command': code_input,
                    'stdout': stdout,
                    'stderr': stderr
                })

                # Refresh namespace
                st.session_state.server_namespace = get_namespace()

                # Clear input (will happen on rerun)
                st.session_state.code_input = ""
                st.rerun()

    with col_clear:
        if st.button("Clear History", use_container_width=True):
            st.session_state.command_history = []
            st.session_state.output_history = []
            st.rerun()

    # Display output history
    st.subheader("Output History")

    if st.session_state.output_history:
        for i, entry in enumerate(
                reversed(st.session_state.output_history)):
            cmd_num = len(st.session_state.output_history) - i
            with st.expander(f"Command {cmd_num}", expanded=(i == 0)):
                st.code(entry['command'], language='python')

                if entry['stdout']:
                    st.text("Output:")
                    st.code(entry['stdout'], language='text')

                if entry['stderr']:
                    st.text("Error:")
                    st.code(entry['stderr'], language='text')
    else:
        st.info("No commands executed yet. "
                "Enter code above and click Execute.")

with col2:
    st.subheader("Quick Reference")

    # Server URL configuration
    with st.expander("Server Settings"):
        new_url = st.text_input("Server URL", value=SERVER_URL)
        if st.button("Update Server URL"):
            st.session_state.server_url = new_url
            st.rerun()

    with st.expander("Live Server Objects", expanded=True):
        namespace = st.session_state.server_namespace
        if namespace:
            for name, info in sorted(namespace.items()):
                st.markdown(f"**`{name}`** `({info['type']})`")
                if info.get('repr'):
                    st.caption(info['repr'])
        else:
            st.text("Connect to server to see objects")

    with st.expander("Useful Commands"):
        st.code("""# Interact with live camera
camera.get_config()
camera.set('exposure', 1.0)

# Check camera controller
camera_controller.get_config()

# List all variables
dir()

# Import modules on server
import numpy as np
print(np.version.version)
""", language='python')

    with st.expander("Tips"):
        st.markdown("""
- Code executes on the **live Flask server**
- Changes affect the running server state
- Variables persist across executions
- Use `dir()` to see all available objects
- Full tracebacks shown for errors
- Server must be running on port 5000
        """)

    # Namespace inspector
    with st.expander("Namespace Inspector"):
        if st.button("Refresh Namespace"):
            st.session_state.server_namespace = get_namespace()
            st.rerun()

        namespace = st.session_state.server_namespace
        if namespace:
            st.text(f"Total objects: {len(namespace)}")
            for name, info in sorted(namespace.items()):
                st.text(f"{name}: {info['type']}")
        else:
            st.text("No server connection")

# Footer
st.markdown("---")
st.caption(
    "Python Terminal - Execute code on live Flask server | "
    f"Connected to: {SERVER_URL}"
)
