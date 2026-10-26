import json
import streamlit as st
from google import genai
from google.genai import types

try:
    from streamlit_local_storage import LocalStorage
except Exception:
    LocalStorage = None

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeVq8d9kuNkDJTOLO0z6XncwswpTuQkhFvhsuY5-GoJUQL3VA/viewform?usp=publish-editor"
MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"]
STORE_KEY = "billing_bot_chat"
BUSY_WORDS = ["503", "unavailable", "overloaded", "high demand", "404", "not_found", "no longer available"]

st.set_page_config(page_title="Billing Helper Bot", page_icon="🩺")

CSS = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.block-container {padding-top: 2rem; padding-bottom: 6rem; max-width: 820px;}
.hero {background: linear-gradient(135deg, #0F766E 0%, #115E59 100%); padding: 26px 30px; border-radius: 16px; margin-bottom: 16px;}
.hero-title {color: #FFFFFF; font-size: 2rem; font-weight: 700; line-height: 1.2;}
.hero-sub {color: #D1FAE5; font-size: 1rem; margin-top: 6px;}
.notice {background: #F1F5F9; border-left: 4px solid #0F766E; padding: 10px 14px; border-radius: 8px; font-size: 0.9rem; color: #334155; margin-bottom: 18px;}
div.stButton > button {border-radius: 10px; border: 1px solid #CBD5E1; padding: 0.6rem 0.9rem;}
div.stButton > button:hover {border-color: #0F766E; color: #0F766E;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

HERO = """
<div class="hero">
<div class="hero-title">Billing Helper Bot</div>
<div class="hero-sub">Denial codes, appeal letters and next steps for US medical billing and RCM</div>
</div>
<div class="notice">
Do not enter patient names, DOB or claim numbers. This bot gives general guidance only, so always verify with the payer's policy.
</div>
"""

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
- If you are not sure about a code or a payer rule, say so and tell the user to check the payer's policy or the official CARC/RARC code list.
- Never ask for or use patient names, DOB, or claim numbers.
- Never give legal advice.
- If the user writes in Roman Urdu, reply in Roman Urdu mixed with English billing terms. Otherwise reply in English.
"""

EXAMPLES = [
    "What does CO-45 mean?",
    "CO-97 denial: what should I do?",
    "What is the difference between CO and PR?",
    "Write an appeal letter for a timely filing denial",
]


@st.cache_resource
def get_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


client = get_client()

localS = None
if LocalStorage is not None:
    try:
        localS = LocalStorage()
    except Exception:
        localS = None

if "msgs" not in st.session_state:
    st.session_state.msgs = []
if "pending" not in st.session_state:
    st.session_state.pending = None
if "loaded" not in st.session_state:
    st.session_state.loaded = False


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


def set_pending(text):
    st.session_state.pending = text


def clear_chat():
    st.session_state.msgs = []
    st.session_state.pending = None
    st.session_state.loaded = True
    save_chat()


def build_history(msgs):
    cleaned = []
    for r, t in msgs[-20:]:
        if not cleaned and r != "user":
            continue
        if cleaned and cleaned[-1][0] == r:
            cleaned[-1] = (r, cleaned[-1][1] + "\n" + t)
        else:
            cleaned.append((r, t))
    out = []
    for r, t in cleaned:
        role = "user" if r == "user" else "model"
        out.append(types.Content(role=role, parts=[types.Part(text=t)]))
    return out


def can_try_next(err):
    return any(w in err for w in BUSY_WORDS)


def stream_model(model_name):
    history = build_history(st.session_state.msgs)
    cfg = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
    stream = client.models.generate_content_stream(model=model_name, contents=history, config=cfg)
    for chunk in stream:
        if chunk.text:
            yield chunk.text


load_chat()

with st.sidebar:
    st.markdown("### About")
    st.write("Billing Helper Bot explains denial codes, suggests next steps, and drafts appeal letters for US medical billing.")
    st.markdown("### Need a billing expert?")
    st.write("Denial management, AR follow-up, lab billing and more.")
    st.link_button("Contact me", FORM_URL, use_container_width=True)
    st.markdown("---")
    st.button("Clear chat", on_click=clear_chat, use_container_width=True)
    st.caption("Your chat is saved only in this browser.")

st.markdown(HERO, unsafe_allow_html=True)

if not st.session_state.msgs and not st.session_state.pending:
    st.markdown("**Try one of these:**")
    cols = st.columns(2)
    for i, ex in enumerate(EXAMPLES):
        cols[i % 2].button(ex, key=f"ex{i}", on_click=set_pending, args=(ex,), use_container_width=True)

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

    reply = None
    last_error = ""
    with st.chat_message("assistant"):
        for model_name in MODELS:
            try:
                reply = st.write_stream(stream_model(model_name))
                if reply:
                    break
            except Exception as e:
                last_error = str(e).lower()
                reply = None
                if not can_try_next(last_error):
                    break

    if reply:
        st.session_state.msgs.append(("assistant", reply))
        save_chat()
    else:
        st.session_state.msgs.pop()
        if "429" in last_error or "quota" in last_error or "exhausted" in last_error:
            st.warning("The free daily limit has been reached. Please try again later.")
        elif can_try_next(last_error):
            st.warning("The AI servers are busy right now. Please try again in a minute.")
        else:
            st.error("Something went wrong. Please send your question again in a minute.")

# END OF FILE
