import json
import streamlit as st
from google import genai
from google.genai import types
from streamlit_local_storage import LocalStorage

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeVq8d9kuNkDJTOLO0z6XncwswpTuQkhFvhsuY5-GoJUQL3VA/viewform?usp=publish-editor"
MODEL = "gemini-3.8-flash"
STORE_KEY = "billing_bot_chat"

st.set_page_config(page_title="Billing Helper Bot", page_icon="🩺", layout="centered")

st.markdown(
    """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.block-container {padding-top: 2rem; padding-bottom: 6rem; max-width: 820px;}
.hero {
    background: linear-gradient(135deg, #0F766E 0%, #115E59 100%);
    padding: 26px 30px;
    border-radius: 16px;
    margin-bottom: 16px;
}
.hero-title {color: #FFFFFF; font-size: 2rem; font-weight: 700; line-height: 1.2;}
.hero-sub {color: #D1FAE5; font-size: 1rem; margin-top: 6px;}
.notice {
    background: #F1F5F9;
    border-left: 4px solid #0F766E;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 0.9rem;
    color: #334155;
    margin-bottom: 18px;
}
div.stButton > button {
    border-radius: 10px;
    border: 1px solid #CBD5E1;
    padding: 0.6rem 0.9rem;
}
div.stButton > button:hover {border-color: #0F766E; color: #0F766E;}
[data-testid="stChatMessage"] {border-radius: 12px;}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource
def get_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


client = get_client()

try:
    localS = LocalStorage()
except Exception:
    localS = None

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

EXAMPLES = [
    "What does CO-45 mean?",
    "CO-97 denial: what should I do?",
    "What is the difference between CO and PR?",
    "Write an appeal letter for a timely filing denial",
]

if "msgs" not in st.session_state:
    st.session_state.msgs = []
if "pending" not in st.session_state:
    st.session_state.pending = None
if "loaded" not in st.session_state:
    st.session_state.loaded = False


def set_pending(text):
    st.session_state.pending = text


def clear_chat():
    st.session_state.msgs = []
    st.session_state.pending = None
    st.session_state.loaded = True
    save_chat()


def save_chat():
    if localS is None:
        return
    try:
        data = json.dumps(st.session_state.msgs[-40:])
        localS.setItem(STORE_KEY, data, key="save_chat")
    except Exception:
        pass


def load_chat():
    if localS is None or st.session_state.loaded:
        return
    try:
        saved = localS.getItem(STORE_KEY)
        if saved:
            st.session_state.msgs = [tuple(m) for m in json.loads(saved)]
            st.session_state.loaded = True
    except Exception:
        pass


def build_history(msgs):
    cleaned = []
    for r, t in msgs[-20:]:
        if not cleaned and r != "user":
            continue
        if cleaned and cleaned[-1][0] == r:
            cleaned[-1] = (r, cleaned[-1][1] + "\n" + t)
        else:
            cleaned.append((r, t))
    return [
        types.Content(
            role="user" if r == "user" else "model",
            parts=[types.Part(text=t)],
        )
        for r, t in cleaned
    ]


load_chat()

with st.sidebar:
    st.markdown("### About")
    st.write(
        "Billing Helper Bot explains denial codes, suggests next steps, "
        "and drafts appeal letters for US medical billing."
    )
    st.markdown("### Need a billing expert?")
    st.write("Denial management, AR follow-up, lab billing and more.")
    st.link_button("Contact me", FORM_URL, use_container_width=True)
    st.markdown("---")
    st.button("Clear chat", on_click=clear_chat, use_container_width=True)
    st.caption("Your chat is saved only in this browser.")

st.markdown(
    """
<div class="hero">
  <div class="hero-title">Billing Helper Bot</div>
  <div class="hero-sub">Denial codes, appeal letters and next steps for US medical billing and RCM</div>
</div>
<div class="notice">
  Do not enter patient names, DOB or claim numbers. This bot gives general guidance
  only, so always verify with the payer's policy.
</div>
""",
    unsafe_allow_html=True,
)

if not st.session_state.msgs and not st.session_state.pending:
    st.markdown("**Try one of these:**")
    cols = st.columns(2)
    for i, ex in enumerate(EXAMPLES):
        cols[i % 2].button(
            ex,
            key=f"ex{i}",
            on_click=set_pending,
            args=(ex,),
            use_container_width=True,
        )

for role, text in st.session_state.msgs:
    with st.chat_message(role):
        st.write(text)

q = st.chat_input("Type your billing question here...")
if st.session_state.pending:
    q = st.session_state.pending
    st.session_state.pending = None

if q:
    st.session_state.loaded = True
    st.session_state.msgs.append(("user", q))
    with st.chat_message("user"):
        st.write(q)

    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=build_history(st.session_state.msgs),
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        reply = resp.text or "I could not generate an answer. Please rephrase your question."
        st.session_state.msgs.append(("assistant", reply))
        with st.chat_message("assistant"):
            st.write(reply)
        save_chat()
    except Exception as e:
        st.session_state.msgs.pop()
        msg = str(e).lower()
        if "429" in msg or "quota" in msg or "exhausted" in msg:
            st.warning("The free daily limit has been reached. Please try again later.")
        else:
                       st.error(f"Error: {e}")
