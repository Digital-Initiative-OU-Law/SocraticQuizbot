import os
import streamlit as st
from services.openai_service import OpenAIService
from utils.auth import Auth


def run_settings():
    st.title("Settings")

    if 'user_id' not in st.session_state or not st.session_state.user_id:
        st.warning("Please log in to access settings.")
        return

    st.subheader("Model Backend")
    use_ollama = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
    backend = st.radio("Choose backend", options=["OpenAI", "Ollama"], index=1 if use_ollama else 0, horizontal=True)

    st.subheader("OpenAI API Key")
    st.caption("Your key is stored per-user and encrypted when a Fernet key is configured.")
    with st.form("key_form"):
        new_key = st.text_input("API Key", type="password", placeholder="sk-...", help="Leave blank to keep current key")
        remove_key = st.checkbox("Remove my custom API key and use system default")
        submitted = st.form_submit_button("Save Settings")

    if submitted:
        if backend == "Ollama":
            os.environ['USE_OLLAMA'] = 'true'
        else:
            os.environ['USE_OLLAMA'] = 'false'

        if remove_key:
            if Auth.update_api_key(st.session_state.user_id, None):
                st.session_state.custom_openai_key = None
                st.success("Switched to system default API key.")
            else:
                st.error("Failed to remove API key.")
        elif new_key:
            svc = OpenAIService()
            if svc.verify_api_key(new_key):
                if Auth.update_api_key(st.session_state.user_id, new_key):
                    st.session_state.custom_openai_key = new_key
                    st.success("API key updated.")
                else:
                    st.error("Failed to save API key.")
            else:
                st.error("Invalid API key provided.")


if __name__ == "__main__":
    run_settings()

