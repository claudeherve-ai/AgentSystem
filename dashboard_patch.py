import streamlit as st
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, os.getcwd())
from agents.orchestrator import Orchestrator

def render_command_center():
    st.title("🎮 Command Center")
    st.info("Direct access to the Agent Orchestrator. Issuing commands here triggers the multi-agent hive in Azure.")

    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = Orchestrator()
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Enter command (e.g., 'Run GDPR scan on /app')"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Orchestrating agents..."):
                # Bridge the async orchestrator call to the Streamlit loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                response = loop.run_until_complete(st.session_state.orchestrator.handle_user_input(prompt))
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

# This is a marker for the main dashboard script to include this page
