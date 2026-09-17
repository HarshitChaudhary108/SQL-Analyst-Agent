import requests
import streamlit as st

st.set_page_config(page_title="SQL Analyst Agent", page_icon="🗄️", layout="wide")

# Point this to wherever your FastAPI server is running
API_URL = "http://localhost:8000/query"

st.title("🗄️ SQL Analyst Agent")
st.caption("Ask natural language questions about your database and get safe, read-only SQL answers.")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for entry in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(entry["question"])
    with st.chat_message("assistant"):
        st.markdown(entry["final_answer"])
        if entry.get("generated_sql_query"):
            with st.expander("Generated SQL Query"):
                st.code(entry["generated_sql_query"], language="sql")
        if entry.get("is_safe"):
            safe = entry["is_safe"].lower() == "yes"
            st.markdown(f"**Safety check:** {'✅ Safe' if safe else '⛔ Blocked'}")
            if entry.get("comments"):
                st.caption(entry["comments"])

user_question = st.chat_input("Ask a question about your data...")

if user_question:
    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    API_URL,
                    json={"question": user_question},
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                st.error(f"Failed to reach the agent API: {e}")
                data = None

        if data:
            final_answer = data.get("final_answer", "")
            generated_sql_query = data.get("generated_sql_query", "")
            is_safe = data.get("is_safe", "")
            comments = data.get("comments", "")

            st.markdown(final_answer)

            if generated_sql_query:
                with st.expander("Generated SQL Query"):
                    st.code(generated_sql_query, language="sql")

            if is_safe:
                safe = is_safe.lower() == "yes"
                st.markdown(f"**Safety check:** {'✅ Safe' if safe else '⛔ Blocked'}")
                if comments:
                    st.caption(comments)

            st.session_state.chat_history.append({
                "question": user_question,
                "final_answer": final_answer,
                "generated_sql_query": generated_sql_query,
                "is_safe": is_safe,
                "comments": comments,
            })

with st.sidebar:
    st.header("Options")
    if st.button("🗑️ Clear chat history"):
        st.session_state.chat_history = []
        st.rerun()