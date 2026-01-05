"""Configuration for Streamlit GUI - Flask server connection."""

import os
import socket
import requests
from typing import Optional, Any, Dict


def get_local_ip():
    """Get the local IP address of this machine."""
    try:
        # Create a socket connection to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "localhost"


# Flask server configuration from environment or defaults
FLASK_HOST = os.environ.get("FLASK_HOST", get_local_ip())
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))

# Construct Flask server URL
FLASK_URL = f"http://{FLASK_HOST}:{FLASK_PORT}"


def get_api_url(endpoint: str) -> str:
    """Get full URL for a Flask API endpoint.

    Args:
        endpoint: API endpoint path (e.g., "/api/camera/config")

    Returns:
        Full URL to the Flask API endpoint
    """
    return f"{FLASK_URL}{endpoint}"


def api_get(
    route: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30
) -> Optional[Any]:
    """Make a GET request to the Flask API and return the data.

    Args:
        route: API endpoint path (e.g., "/api/camera/config")
        params: Optional query parameters
        timeout: Request timeout in seconds (default: 30)

    Returns:
        The data from the response if successful, None otherwise.
        Displays streamlit error messages on failure.
    """
    try:
        import streamlit as st

        response = requests.get(get_api_url(route), params=params, timeout=timeout)
        response.raise_for_status()

        result = response.json()
        if result.get("success"):
            return result.get("data")
        else:
            st.error(f"API error: {result.get('error', 'Unknown error')}")
            return None

    except requests.exceptions.Timeout:
        import streamlit as st
        st.error(f"Request timeout for {route}")
        return None
    except requests.exceptions.RequestException as e:
        import streamlit as st
        st.error(f"Network error for {route}: {e}")
        return None
    except Exception as e:
        import streamlit as st
        st.error(f"Unexpected error for {route}: {e}")
        return None


def api_post(
    route: str,
    json: Optional[Dict[str, Any]] = None,
    data: Optional[Any] = None,
    timeout: int = 30,
    return_full_response: bool = False,
    return_keys: Optional[list[str]] = None
) -> Optional[Any]:
    """Make a POST request to the Flask API and return the data.

    Args:
        route: API endpoint path (e.g., "/api/camera/config")
        json: Optional JSON data to send in request body
        data: Optional raw data to send in request body
        timeout: Request timeout in seconds (default: 30)
        return_full_response: If True, return entire response dict instead of just data field
        return_keys: If provided, return dict with only these keys from the response

    Returns:
        The data from the response if successful (or full response/selected keys based on params),
        None otherwise. Displays streamlit error messages on failure.

    Examples:
        # Return just the data field (default)
        data = api_post("/api/pipeline/build", json={...})

        # Return full response
        response = api_post("/api/pipeline/build", json={...}, return_full_response=True)
        pipeline_id = response["pipeline_id"]

        # Return specific keys
        result = api_post("/api/pipeline/execute", json={...}, return_keys=["result_id", "data"])
        result_id = result["result_id"]
    """
    try:
        import streamlit as st

        response = requests.post(get_api_url(route), json=json, data=data, timeout=timeout)
        response.raise_for_status()

        result = response.json()
        if result.get("success"):
            if return_full_response:
                return result
            elif return_keys:
                return {key: result.get(key) for key in return_keys}
            else:
                return result.get("data")
        else:
            st.error(f"API error: {result.get('error', 'Unknown error')}")
            return None

    except requests.exceptions.Timeout:
        import streamlit as st
        st.error(f"Request timeout for {route}")
        return None
    except requests.exceptions.RequestException as e:
        import streamlit as st
        st.error(f"Network error for {route}: {e}")
        return None
    except Exception as e:
        import streamlit as st
        st.error(f"Unexpected error for {route}: {e}")
        return None
