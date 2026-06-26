
import streamlit as st
def get_ai_context():
    return st.session_state.get("ai_context", {}) if hasattr(st,"session_state") else {}
