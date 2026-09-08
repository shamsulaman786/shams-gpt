# ChatGPT-style conversational app
# Built on top of app.py, adding:
#   1. New chat
#   2. Chat history auto-saved to JSON files
#   3. Settings (dark mode, clear chat)
#   4. Summarize conversation

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
from openai import OpenAI
# from dotenv import load_dotenv
# import os

# load_dotenv("/var/www/html/learning-ai/.env", override=True)

MODEL = "openai/gpt-oss-20b"
CHATS_DIR = Path(__file__).parent / "chats"
CHATS_DIR.mkdir(exist_ok=True)

# Configure the page
st.set_page_config(page_title="My ChatBot", page_icon="🤖", layout="wide")

# Initialize the OpenAI client with OpenRouter
api_key = st.secrets.get("OPENROUTER_API_KEY")
# api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    st.error("Missing OPENROUTER_API_KEY. Add it to /var/www/html/learning-ai/.env.")
    st.stop()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
    default_headers={
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "My ChatBot",
    },
)


# ----------------------------------------------------------------------------
# Persistence: one JSON file per conversation
# ----------------------------------------------------------------------------
def chat_path(chat_id):
    return CHATS_DIR / f"{chat_id}.json"


def save_chat():
    """Write the current conversation to disk. Called after every change."""
    if not st.session_state.messages:
        return  # nothing worth saving yet
    data = {
        "id": st.session_state.chat_id,
        "title": st.session_state.title,
        "created_at": st.session_state.created_at,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": st.session_state.summary,
        "messages": st.session_state.messages,
    }
    chat_path(st.session_state.chat_id).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_chat(chat_id):
    data = json.loads(chat_path(chat_id).read_text(encoding="utf-8"))
    st.session_state.chat_id = data["id"]
    st.session_state.title = data.get("title", "New Chat")
    st.session_state.created_at = data.get("created_at", "")
    st.session_state.summary = data.get("summary", "")
    st.session_state.messages = data.get("messages", [])


def delete_chat(chat_id):
    chat_path(chat_id).unlink(missing_ok=True)
    if st.session_state.get("chat_id") == chat_id:
        new_chat()


def list_chats():
    """All saved conversations, most recently updated first."""
    chats = []
    for path in CHATS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        chats.append(
            {
                "id": data.get("id", path.stem),
                "title": data.get("title", "Untitled"),
                "updated_at": data.get("updated_at", ""),
            }
        )
    chats.sort(key=lambda c: c["updated_at"], reverse=True)
    return chats


def new_chat():
    st.session_state.chat_id = uuid.uuid4().hex[:12]
    st.session_state.title = "New Chat"
    st.session_state.created_at = datetime.now().isoformat(timespec="seconds")
    st.session_state.messages = []
    st.session_state.summary = ""


def make_title(text):
    """Derive a short conversation title from the first user message."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "New Chat"
    return text[:40] + "…" if len(text) > 40 else text


# ----------------------------------------------------------------------------
# Session state
# ----------------------------------------------------------------------------
if "chat_id" not in st.session_state:
    new_chat()
st.session_state.setdefault("dark_mode", False)  # light mode is the default

# ----------------------------------------------------------------------------
# Theme
# ----------------------------------------------------------------------------
if st.session_state.dark_mode:
    st.markdown(
        """
        <style>
        .stApp, [data-testid="stSidebar"], [data-testid="stHeader"],
        [data-testid="stBottom"], [data-testid="stBottomBlockContainer"] {
            background-color: #1b1b1d; color: #e8e8e8;
        }
        [data-testid="stSidebar"] { border-right: 1px solid #333; }
        .stApp p, .stApp li, .stApp label,
        .stApp h1, .stApp h2, .stApp h3 { color: #e8e8e8; }
        [data-testid="stChatMessage"] { background-color: #232326; border-radius: 10px; }

        /* Chat input: the box and the text typed into it */
        /* BaseWeb wraps the textarea in several divs that keep a light
           background of their own, so paint the wrappers too. */
        [data-testid="stChatInput"],
        [data-testid="stChatInput"] div,
        [data-testid="stChatInput"] [data-baseweb="textarea"],
        [data-testid="stChatInput"] [data-baseweb="base-input"] {
            background-color: #2a2a2e !important;
        }
        [data-testid="stChatInput"] { border: 1px solid #444; }
        [data-testid="stChatInputTextArea"] { color: #e8e8e8 !important; }
        [data-testid="stChatInputTextArea"]::placeholder { color: #9aa0a6 !important; }

        /* Sidebar buttons, including the disabled current-chat entry */
        [data-testid="stSidebar"] .stButton
            button:not([data-testid="stBaseButton-primary"]) {
            background-color: #2a2a2e; color: #e8e8e8; border: 1px solid #444;
        }
        [data-testid="stSidebar"] .stButton button:disabled,
        [data-testid="stSidebar"] .stButton button:disabled p {
            color: #cfcfcf !important; background-color: #35353a; opacity: 1;
        }
        [data-testid="stSidebar"] .stButton button p { color: inherit !important; }

        /* Summarize Conversation expander: header bar and body */
        [data-testid="stExpander"] details,
        [data-testid="stExpander"] summary,
        [data-testid="stExpanderDetails"] {
            background-color: #232326 !important;
            color: #e8e8e8 !important;
        }
        [data-testid="stExpander"] details { border: 1px solid #444 !important; }
        [data-testid="stExpander"] summary p,
        [data-testid="stExpander"] summary span,
        [data-testid="stExpander"] [data-testid="stIconMaterial"] {
            color: #e8e8e8 !important;
        }

        /* Buttons in the main pane, e.g. Generate summary */
        [data-testid="stMainBlockContainer"] [data-testid="stBaseButton-secondary"] {
            background-color: #2a2a2e !important;
            color: #e8e8e8 !important;
            border: 1px solid #444 !important;
        }

        /* Markdown tables in assistant replies */
        .stApp table, .stApp th, .stApp td {
            color: #e8e8e8 !important;
            border-color: #444 !important;
        }
        .stApp thead th { background-color: #2a2a2e !important; }
        .stApp tbody td { background-color: #232326 !important; }
        .stApp tbody tr:nth-child(even) td { background-color: #1f1f22 !important; }

        /* Section separators */
        [data-testid="stSidebar"] hr, .stApp hr { border-color: #55555e; }
        </style>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <style>
    .stAppDeployButton,
    button.stAppDeployButton,
    [data-testid="stAppDeployButton"],
    [data-testid="stAppDeployButton"] button { display: none !important; }
    [data-testid="stSidebar"] .stButton button { width: 100%; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Sidebar: new chat, history, settings
# ----------------------------------------------------------------------------
with st.sidebar:
    st.header("💬 Conversations")

    if st.button("➕ New Chat", type="primary", use_container_width=True):
        save_chat()
        new_chat()
        st.rerun()

    st.divider()
    st.subheader("Chat History")

    saved = list_chats()
    if not saved:
        st.caption("No saved conversations yet.")
    for chat in saved:
        col_open, col_del = st.columns([5, 1])
        is_current = chat["id"] == st.session_state.chat_id
        if col_open.button(
            chat["title"],
            key=f"open_{chat['id']}",
            use_container_width=True,
            disabled=is_current,
        ):
            save_chat()
            load_chat(chat["id"])
            st.rerun()
        if col_del.button("🗑", key=f"del_{chat['id']}", help="Delete this conversation"):
            delete_chat(chat["id"])
            st.rerun()

    st.divider()
    st.subheader("⚙️ Settings")
    st.toggle("Dark mode", key="dark_mode")

    if st.button("🧹 Clear Current Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.summary = ""
        save_chat()
        st.rerun()

# ----------------------------------------------------------------------------
# Main pane
# ----------------------------------------------------------------------------
st.title(f"💬 {st.session_state.title}")

# --- Summarize conversation -------------------------------------------------
with st.expander("📋 Summarize Conversation"):
    if not st.session_state.messages:
        st.caption("Start chatting to generate a summary.")
    else:
        if st.button("Generate summary"):
            transcript = "\n".join(
                f"{m['role']}: {m['content']}" for m in st.session_state.messages
            )
            try:
                with st.spinner("Summarizing..."):
                    result = client.chat.completions.create(
                        model=MODEL,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "Summarize the conversation in 3-5 concise "
                                    "bullet points."
                                ),
                            },
                            {"role": "user", "content": transcript},
                        ],
                    )
                st.session_state.summary = result.choices[0].message.content.strip()
                save_chat()
            except Exception as e:
                st.error(f"Could not summarize: {e}")
        if st.session_state.summary:
            st.markdown(st.session_state.summary)

# --- Chat history -----------------------------------------------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


def clean(text):
    """Strip chat-template tokens some open models leak into the output."""
    for token in ("<s>", "   <|im_start|> ", " <|im_end|> ", "<|OUT|>"):
        text = text.replace(token, "")
    return text


# --- User input -------------------------------------------------------------
if prompt := st.chat_input("What would you like to know?"):
    if not st.session_state.messages:
        st.session_state.title = make_title(prompt)

    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat()

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=st.session_state.messages,
                stream=True,
                extra_headers={
                    "HTTP-Referer": "http://localhost:8501",
                    "X-Title": "My ChatBot",
                },
                extra_body={"provider": {"data_collection": "deny"}},
            )

            response_text = ""
            response_placeholder = st.empty()

            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    response_text += clean(chunk.choices[0].delta.content)
                    response_placeholder.markdown(response_text + "▌")

            response_text = clean(response_text).strip()
            response_placeholder.markdown(response_text)

            st.session_state.messages.append(
                {"role": "assistant", "content": response_text}
            )
            save_chat()
            st.rerun()  # refresh the sidebar so the new title appears

        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.info("Please check your API key and try again.")
