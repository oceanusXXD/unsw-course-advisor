import streamlit as st
import requests
import json
import os
from datetime import datetime
import time

# Configuration
API_URL = "http://127.0.0.1:8000/api/chat_multiround/"
DEFAULT_USER_ID = "test_user_v3.3_fixed"
MAX_HISTORY = 20

# Initialize session state
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

def send_chat_request(query, user_id):
    """Send request to chat API and return response with timing"""
    payload = {
        "query": query,
        "history": st.session_state.history,
        "user_id": user_id
    }
    
    start_time = time.time()
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        end_time = time.time()
        response_time = end_time - start_time
        
        if response.status_code == 200:
            data = response.json()
            data["response_time"] = response_time
            data["timestamp"] = datetime.now().isoformat()
            return data
        else:
            return {
                "error": f"API Error: {response.status_code}", 
                "answer": "Sorry, I encountered an error.",
                "response_time": response_time,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {
            "error": str(e), 
            "answer": "Sorry, I couldn't connect to the server.",
            "response_time": time.time() - start_time,
            "timestamp": datetime.now().isoformat()
        }

def display_performance_metrics(performance_data):
    """Display performance metrics in a structured way"""
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
    """Display detailed source information"""
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
    """Save conversation to session state"""
    if user_id not in st.session_state.all_conversations:
        st.session_state.all_conversations[user_id] = []
    
    st.session_state.all_conversations[user_id].append({
        "timestamp": datetime.now().isoformat(),
        "history": conversation_data.get("history", []),
        "sources": conversation_data.get("sources_brief", []),
        "performance": conversation_data.get("performance_data", {})
    })

def load_conversation_history(user_id):
    """Load conversation history for a user"""
    return st.session_state.all_conversations.get(user_id, [])

def start_new_conversation():
    """Start a new conversation"""
    st.session_state.history = []
    st.session_state.sources = []
    st.session_state.performance_data = {}
    st.session_state.conversation_start_time = datetime.now()

# Page setup
st.set_page_config(
    page_title="UNSW Course Advisor - LangGraph v3.3", 
    layout="wide",
    page_icon="🎓"
)

st.title("🎓 UNSW Course Advisor - LangGraph v3.3")
st.caption("优化版 LangGraph：v3.3 - Bug修复与路由优化")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    
    # User ID management
    new_user_id = st.text_input("User ID", value=st.session_state.user_id)
    if new_user_id != st.session_state.user_id:
        st.session_state.user_id = new_user_id
        start_new_conversation()
    
    # Environment settings (matching your test setup)
    st.subheader("Environment Settings")
    col1, col2 = st.columns(2)
    
    with col1:
        verbose_logging = st.toggle("Verbose Logging", value=True)
        grounding_check = st.toggle("Grounding Check", value=False)
    
    with col2:
        enable_suggestions = st.toggle("Suggestions", value=False)
        fast_router = st.toggle("Fast Router", value=False)
    
    # Conversation management
    st.subheader("Conversation")
    if st.button("🆕 New Conversation"):
        start_new_conversation()
        st.rerun()
    
    if st.button("🧹 Clear All History"):
        st.session_state.all_conversations = {}
        start_new_conversation()
        st.rerun()
    
    # Load previous conversations
    st.subheader("History")
    user_conversations = load_conversation_history(st.session_state.user_id)
    if user_conversations:
        for i, conv in enumerate(reversed(user_conversations[-5:])):  # Show last 5
            conv_time = datetime.fromisoformat(conv["timestamp"]).strftime("%H:%M")
            if st.button(f"📝 {conv_time} ({len(conv['history'])} turns)", key=f"conv_{i}"):
                st.session_state.history = conv["history"]
                st.session_state.sources = conv.get("sources", [])
                st.rerun()
    else:
        st.info("No previous conversations")
    
    # Performance metrics
    if st.session_state.performance_data:
        display_performance_metrics(st.session_state.performance_data)

# Main chat area
col1, col2 = st.columns([3, 1])

with col1:
    # Display conversation header
    if st.session_state.conversation_start_time:
        st.write(f"**Conversation started:** {st.session_state.conversation_start_time.strftime('%H:%M:%S')}")
        st.write(f"**Turns:** {len(st.session_state.history)}")
    
    # Display conversation history
    for i, turn in enumerate(st.session_state.history[-MAX_HISTORY:]):
        with st.chat_message("user"):
            st.markdown(turn["user"])
        
        with st.chat_message("assistant"):
            st.markdown(turn["bot"])
            
            # Show sources for the most recent response
            if i == len(st.session_state.history) - 1 and st.session_state.sources:
                st.caption("🔍 Sources used in this response:")

    # User input
    query = st.chat_input("Ask about UNSW courses...")
    if query:
        # Display user message immediately
        with st.chat_message("user"):
            st.markdown(query)
        
        # Get and display assistant response
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                response = send_chat_request(query, st.session_state.user_id)
                
                if "error" in response:
                    st.error(f"Error: {response['error']}")
                    st.markdown(response.get("answer", "No response available"))
                else:
                    st.markdown(response.get("answer", "No response available"))
                    
                    # Update session state
                    if "history" in response:
                        st.session_state.history = response["history"]
                    if "sources_brief" in response:
                        st.session_state.sources = response["sources_brief"]
                    
                    # Store performance data
                    st.session_state.performance_data = {
                        "response_time": response.get("response_time", 0),
                        "performance": response  # Store full response for detailed metrics
                    }
                    
                    # Save conversation
                    save_conversation(st.session_state.user_id, {
                        "history": st.session_state.history,
                        "sources_brief": st.session_state.sources,
                        "performance_data": st.session_state.performance_data
                    })

with col2:
    st.header("📚 Sources")
    if st.session_state.sources:
        for i, source in enumerate(st.session_state.sources):
            display_source_details(source, i)
    else:
        st.info("No sources referenced yet")
    
    # Debug information
    st.header("🔧 Debug Info")
    st.caption(f"Last update: {datetime.now().strftime('%H:%M:%S')}")
    
    if st.toggle("Show raw response"):
        if "last_response" in locals():
            st.json(response)

# Environment status display
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

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("LangGraph v3.3 - Performance Monitoring & Routing Optimization")