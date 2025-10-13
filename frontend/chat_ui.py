import streamlit as st
import requests
import json
import os
from datetime import datetime
import time

# ===========================
# Configuration
# ===========================
API_URL = "http://127.0.0.1:8000/api/chat_multiround/"
DEFAULT_USER_ID = "test_user_v3.3_fixed"
MAX_HISTORY = 20

# ===========================
# Session State Initialization
# ===========================
if "history" not in st.session_state:
    st.session_state.history = []
if "user_id" not in st.session_state:
    st.session_state.user_id = DEFAULT_USER_ID
if "sources" not in st.session_state:
    st.session_state.sources = []
if "performance_data" not in st.session_state:
    st.session_state.performance_data = {}
if "conversation_start_time" not in st.session_state:
    st.session_state.conversation_start_time = None
if "all_conversations" not in st.session_state:
    st.session_state.all_conversations = {}

# ===========================
# Streaming Request Function
# ===========================
def send_chat_request_stream(query, user_id):
    """Send chat request and yield tokens as they arrive (streaming)"""
    payload = {
        "query": query,
        "history": st.session_state.history,
        "user_id": user_id
    }

    start_time = time.time()
    try:
        with requests.post(API_URL, json=payload, stream=True, timeout=120) as response:
            if response.status_code != 200:
                yield {"type": "error", "data": f"API Error: {response.status_code}"}
                return

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data:"):
                    try:
                        content = line[5:].strip()
                        if content == "[DONE]":
                            break
                        data = json.loads(content)
                        if data.get("event") == "stream_end":
                            break
                        yield data
                    except json.JSONDecodeError:
                        continue

    except requests.exceptions.RequestException as e:
        yield {"type": "error", "data": f"Request failed: {e}"}
    finally:
        response.close()
        elapsed = time.time() - start_time
        yield {"type": "end", "data": f"Elapsed: {elapsed:.2f}s"}


# ===========================
# Helper Functions
# ===========================
def display_performance_metrics(performance_data):
    if not performance_data:
        return
    st.subheader("⏱️ Performance Metrics")

    if "response_time" in performance_data:
        st.metric("Response Time", f"{performance_data['response_time']:.2f}s")

    if "performance" in performance_data:
        perf = performance_data["performance"]
        col1, col2, col3 = st.columns(3)
        with col1:
            if "total_time" in perf:
                st.metric("Total Time", f"{perf['total_time']:.2f}s")
        with col2:
            if "llm_calls" in perf:
                st.metric("LLM Calls", perf["llm_calls"])
        with col3:
            if "tokens_used" in perf:
                st.metric("Tokens Used", perf["tokens_used"])

def display_source_details(source, index):
    with st.expander(f"📄 {source.get('course_code', 'Unknown')} - Score: {source.get('score', 0):.3f}"):
        col1, col2 = st.columns([1, 3])
        with col1:
            st.write("**File:**")
            st.code(source.get('source_file', 'Unknown'))
            if source.get('score'):
                st.progress(min(source['score'], 1.0))
        with col2:
            st.write("**Preview:**")
            st.text(source.get("preview", "No preview available"))

def save_conversation(user_id, conversation_data):
    if user_id not in st.session_state.all_conversations:
        st.session_state.all_conversations[user_id] = []
    st.session_state.all_conversations[user_id].append({
        "timestamp": datetime.now().isoformat(),
        "history": conversation_data.get("history", []),
        "sources": conversation_data.get("sources_brief", []),
        "performance": conversation_data.get("performance_data", {})
    })

def load_conversation_history(user_id):
    return st.session_state.all_conversations.get(user_id, [])

def start_new_conversation():
    st.session_state.history = []
    st.session_state.sources = []
    st.session_state.performance_data = {}
    st.session_state.conversation_start_time = datetime.now()

# ===========================
# Page Setup
# ===========================
st.set_page_config(
    page_title="UNSW Course Advisor - LangGraph v3.3",
    layout="wide",
    page_icon="🎓"
)

st.title("🎓 UNSW Course Advisor - LangGraph v3.3")
st.caption("优化版 LangGraph：v3.3 - 支持 Qwen 流式输出 🚀")

# ===========================
# Sidebar
# ===========================
with st.sidebar:
    st.header("⚙️ Settings")

    new_user_id = st.text_input("User ID", value=st.session_state.user_id)
    if new_user_id != st.session_state.user_id:
        st.session_state.user_id = new_user_id
        start_new_conversation()

    st.subheader("Environment Settings")
    col1, col2 = st.columns(2)
    with col1:
        verbose_logging = st.toggle("Verbose Logging", value=True)
        grounding_check = st.toggle("Grounding Check", value=False)
    with col2:
        enable_suggestions = st.toggle("Suggestions", value=False)
        fast_router = st.toggle("Fast Router", value=False)

    st.subheader("Conversation")
    if st.button("🆕 New Conversation"):
        start_new_conversation()
        st.rerun()

    if st.button("🧹 Clear All History"):
        st.session_state.all_conversations = {}
        start_new_conversation()
        st.rerun()

    st.subheader("History")
    user_conversations = load_conversation_history(st.session_state.user_id)
    if user_conversations:
        for i, conv in enumerate(reversed(user_conversations[-5:])):
            conv_time = datetime.fromisoformat(conv["timestamp"]).strftime("%H:%M")
            if st.button(f"📝 {conv_time} ({len(conv['history'])} turns)", key=f"conv_{i}"):
                st.session_state.history = conv["history"]
                st.session_state.sources = conv.get("sources", [])
                st.rerun()
    else:
        st.info("No previous conversations")

    if st.session_state.performance_data:
        display_performance_metrics(st.session_state.performance_data)

# ===========================
# Main Chat Area
# ===========================
col1, col2 = st.columns([3, 1])

with col1:
    if st.session_state.conversation_start_time:
        st.write(f"**Conversation started:** {st.session_state.conversation_start_time.strftime('%H:%M:%S')}")
        st.write(f"**Turns:** {len(st.session_state.history)}")

    # Display conversation history
    for i, turn in enumerate(st.session_state.history[-MAX_HISTORY:]):
        with st.chat_message("user"):
            st.markdown(turn["user"])
        with st.chat_message("assistant"):
            st.markdown(turn["bot"])
            if i == len(st.session_state.history) - 1 and st.session_state.sources:
                st.caption("🔍 Sources used in this response:")

    # ===========================
    # Streaming Chat Input
    # ===========================
    query = st.chat_input("Ask about UNSW courses...")
    if query:
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            start_time = time.time()

            # Stream response tokens
            for event in send_chat_request_stream(query, st.session_state.user_id):
                if event["type"] == "token":
                    full_response += event["data"]
                    message_placeholder.markdown(full_response)
                elif event["type"] == "sources":
                    st.session_state.sources = event["data"]
                elif event["type"] == "error":
                    st.error(event["data"])
                elif event["type"] == "end":
                    response_time = time.time() - start_time
                    st.session_state.performance_data = {"response_time": response_time}
                    st.caption(f"⏱️ Response time: {response_time:.2f}s")

            # Update history after stream ends
            st.session_state.history.append({"user": query, "bot": full_response})
            save_conversation(
                st.session_state.user_id,
                {"history": st.session_state.history, "sources_brief": st.session_state.sources}
            )

# ===========================
# Right Column: Sources & Debug
# ===========================
with col2:
    st.header("📚 Sources")
    if st.session_state.sources:
        for i, source in enumerate(st.session_state.sources):
            display_source_details(source, i)
    else:
        st.info("No sources referenced yet")

    st.header("🔧 Debug Info")
    st.caption(f"Last update: {datetime.now().strftime('%H:%M:%S')}")

# ===========================
# Sidebar Footer
# ===========================
st.sidebar.markdown("---")
st.sidebar.subheader("🌍 Environment Status")
env_status = {
    "ENABLE_VERBOSE_LOGGING": verbose_logging,
    "ENABLE_GROUNDING_CHECK": grounding_check,
    "ENABLE_SUGGESTIONS": enable_suggestions,
    "USE_FAST_ROUTER": fast_router
}
for key, value in env_status.items():
    status = "🟢" if value else "⚪"
    st.sidebar.text(f"{status} {key}: {value}")

st.sidebar.markdown("---")
st.sidebar.caption("LangGraph v3.3 - Stream Adapted for Qwen 🚀")
