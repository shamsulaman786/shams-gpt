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
APP_NAME = st.secrets.get("APP_NAME", "ShamsGPT")
MODEL = "openai/gpt-oss-20b"
CHATS_DIR = Path(__file__).parent / "chats"
CHATS_DIR.mkdir(exist_ok=True)

# Configure the page
st.set_page_config(page_title=APP_NAME, page_icon="🤖", layout="wide")

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
        "X-Title": st.secrets.get("APP_NAME"),
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
styles = Path(__file__).with_name("style.css").read_text(encoding="utf-8")
dark_start = styles.index("/* DARK_MODE_START */")
dark_end = styles.index("/* DARK_MODE_END */") + len("/* DARK_MODE_END */")
if not st.session_state.dark_mode:
    styles = styles[:dark_start] + styles[dark_end:]
st.markdown(f"<style>{styles}</style>", unsafe_allow_html=True)

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

if not st.session_state.messages:
    st.markdown(
        """
        <div class="empty-state">
            <div class="empty-state-kicker">A fresh conversation</div>
            <div class="empty-state-title">Welcome to ShamsGPT</div>
            <div class="empty-state-copy">Bring a question, an idea, or a problem worth thinking through.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
with st.bottom:
    upload_col, input_col = st.columns([0.08, 0.92], vertical_alignment="bottom")
    with upload_col:
        uploaded_file = st.file_uploader(
            "+",
            type=["txt", "md", "py", "json", "csv", "html", "css", "js"],
            label_visibility="collapsed",
            help="Attach a text-based file",
        )
    with input_col:
        prompt = st.chat_input("What would you like to know?")

attachment_context = ""
if uploaded_file is not None:
    try:
        attachment_text = uploaded_file.getvalue().decode("utf-8")
        attachment_context = (
            f"\n\nAttached file: {uploaded_file.name}\n"
            "```text\n"
            f"{attachment_text[:12000]}\n"
            "```"
        )
        if len(attachment_text) > 12000:
            st.toast("Only the first 12,000 characters will be sent.")
    except UnicodeDecodeError:
        st.error("This file is not valid UTF-8 text and cannot be attached.")

if prompt:
    if not st.session_state.messages:
        st.session_state.title = make_title(prompt)

    message_content = prompt + attachment_context
    st.session_state.messages.append({"role": "user", "content": message_content})
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
                    "X-Title": st.secrets.get("APP_NAME"),
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
