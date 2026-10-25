import streamlit as st
from google import genai
from google.genai import types

@st.cache_resource
def get_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

client = get_client()

SYSTEM_PROMPT = """
You are Billing Helper Bot, an expert in US medical billing and RCM.
You explain denial codes (CARC/RARC), suggest next steps, and draft
appeal letters. Keep answers short and step-by-step.
If the user writes in Roman Urdu, reply in Roman Urdu mixed with
English billing terms. Never give legal advice.
"""

if "msgs" not in st.session_state:
    st.session_state.msgs = []

st.title("Billing Helper Bot")
st.caption("Denial codes, appeals, and billing questions answered step by step")
st.warning("Please do not enter patient names, DOB, or claim numbers here.")
st.markdown("Need billing support? [Fill out this form](PASTE_LINK_HEREhttps://docs.google.com/forms/d/e/1FAIpQLSeVq8d9kuNkDJTOLO0z6XncwswpTuQkhFvhsuY5-GoJUQL3VA/viewform?usp=publish-editor)")

for role, text in st.session_state.msgs:
    with st.chat_message(role):
        st.write(text)

q = st.chat_input("Type your billing question here...")
if q:
    st.session_state.msgs.append(("user", q))
    with st.chat_message("user"):
        st.write(q)

    history = [
        types.Content(
            role="user" if r == "user" else "model",
            parts=[types.Part(text=t)],
        )
        for r, t in st.session_state.msgs
    ]

    try:
        resp = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=history,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        reply = resp.text
        st.session_state.msgs.append(("assistant", reply))
        with st.chat_message("assistant"):
            st.write(reply)
    except Exception as e:
        st.error(f"Error: {e}")
