import streamlit as st
from google import genai
from google.genai import types

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeVq8d9kuNkDJTOLO0z6XncwswpTuQkhFvhsuY5-GoJUQL3VA/viewform?usp=publish-editor"
MODEL = "gemini-3.8-flash"

st.set_page_config(page_title="Billing Helper Bot")

@st.cache_resource
def get_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

client = get_client()

SYSTEM_PROMPT = """
You are Billing Helper Bot, an assistant for US medical billing and RCM.

When the user asks about a denial code (CARC/RARC), answer in this format:
1. Meaning: what the code means in one or two sentences.
2. Common causes: 2 to 4 short bullet points.
3. Next steps: numbered steps (check, correct and rebill, appeal, or write-off).
4. Tip: one practical tip.

When asked for an appeal letter, write a professional letter with placeholders
like [Patient Name], [Claim Number], [Date of Service]. Never invent real data.

Rules:
- Keep answers short and clear.
- If you are not sure about a code or a payer rule, say so and tell the user
  to check the payer's policy or the official CARC/RARC code list.
- Never ask for or use patient names, DOB, or claim numbers.
- Never give legal advice.
- If the user writes in Roman Urdu, reply in Roman Urdu mixed with English
  billing terms. Otherwise reply in English.
"""

if "msgs" not in st.session_state:
    st.session_state.msgs = []
if "pending" not in st.session_state:
    st.session_state.pending = None

st.sidebar.header("Try these")
EXAMPLES = [
    "What does CO-45 mean?",
    "CO-97 denial: what should I do?",
    "What is the difference between CO and PR?",
    "Write an appeal letter for a timely filing denial",
]
for ex in EXAMPLES:
    if st.sidebar.button(ex):
        st.session_state.pending = ex

if st.sidebar.button("Clear chat"):
    st.session_state.msgs = []
    st.session_state.pending = None
    st.rerun()

st.title("Billing Helper Bot")
st.caption("Denial codes, appeals, and billing questions answered step by step")
st.warning("Please do not enter patient names, DOB, or claim numbers here.")
st.link_button("Need billing support? Fill out this form", FORM_URL)
st.caption("This bot gives general guidance only. Always verify with the payer's policy.")

for role, text in st.session_state.msgs:
    with st.chat_message(role):
        st.write(text)

q = st.chat_input("Type your billing question here...")
if st.session_state.pending:
    q = st.session_state.pending
    st.session_state.pending = None

if q:
    st.session_state.msgs.append(("user", q))
    with st.chat_message("user"):
        st.write(q)

    recent = st.session_state.msgs[-20:]
    history = [
        types.Content(
            role="user" if r == "user" else "model",
            parts=[types.Part(text=t)],
        )
        for r, t in recent
    ]

    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=history,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        reply = resp.text
        st.session_state.msgs.append(("assistant", reply))
        with st.chat_message("assistant"):
            st.write(reply)
    except Exception as e:
        msg = str(e).lower()
        if "429" in msg or "quota" in msg or "exhausted" in msg:
            st.warning("The free daily limit has been reached. Please try again later.")
        else:
            st.error("Something went wrong. Please try again in a minute.")
