import streamlit as st
import requests
import json
import re
import os
import hashlib
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


# API_BASE = os.getenv("API_BASE")
API_BASE = "http://104.197.0.144:8080"
st.set_page_config(page_title="Legal Simplifier", layout="wide")

# ---------------------------
# Helpers
# ---------------------------
def parse_response(resp):
    """Clean and parse backend response into proper JSON/dict."""
    if isinstance(resp, list) and len(resp) > 0 and isinstance(resp[0], str):
        clean = resp[0].replace("json\n", "").strip()
        clean = re.sub(r"^```(json)?", "", clean).strip()
        clean = re.sub(r"```$", "", clean).strip()
        return json.loads(clean)
    if isinstance(resp, str):
        try:
            return json.loads(resp)
        except Exception:
            return {"text": resp}
    return resp

def render_risk_assessment(risk_data):
    """Render risk assessment section in a structured way."""
    if isinstance(risk_data, dict):
        overall_score = (
            risk_data.get("Overall Risk Score")
            or risk_data.get("overall_score")
            or "N/A"
        )
        st.markdown(f"**Overall Risk Score:** {overall_score}")

        risks = risk_data.get("risks", [])
        for r in risks:
            severity = r.get("severity", "")
            sev_icon = (
                "🔴" if severity.lower() == "high"
                else "🟡" if severity.lower() == "medium"
                else "🟢"
            )
            detail_text = (
                r.get("details")
                or r.get("description")
                or r.get("explanation")
                or ""
            )
            st.markdown(f"**Risk:** {r.get('risk', '')}")
            st.markdown(f"- **Severity:** {sev_icon} {severity}")
            st.markdown(f"- **Details:** {detail_text}")
            st.markdown("---")

    elif isinstance(risk_data, list):
        for r in risk_data:
            if isinstance(r, dict):
                severity = r.get("severity", "")
                sev_icon = (
                    "🔴" if severity.lower() == "high"
                    else "🟡" if severity.lower() == "medium"
                    else "🟢"
                )
                detail_text = (
                    r.get("details")
                    or r.get("description")
                    or r.get("explanation")
                    or ""
                )
                st.markdown(f"**Risk:** {r.get('risk', '')}")
                st.markdown(f"- **Severity:** {sev_icon} {severity}")
                st.markdown(f"- **Details:** {detail_text}")
                st.markdown("---")
            else:
                st.markdown(str(r))

    elif isinstance(risk_data, str):
        st.markdown(risk_data, unsafe_allow_html=True)
    else:
        st.info("No risk assessment data available.")

def get_file_hash(file_obj):
    file_obj.seek(0)
    file_content = file_obj.read()
    file_obj.seek(0)
    return hashlib.md5(file_content).hexdigest()

# ---------------------------
# Session State
# ---------------------------
if "doc_data" not in st.session_state:
    st.session_state.doc_data = None
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []
if "doc_history" not in st.session_state:
    st.session_state.doc_history = []   # keep processed docs across runs

# ---------------------------
# Sidebar (Document History)
# ---------------------------
with st.sidebar:
    st.header("📂 Document History")
    if st.session_state.doc_history:
        for i, doc in enumerate(st.session_state.doc_history, 1):
            if st.button(f"{i}. {doc['filename']}", key=f"hist_{i}"):
                st.session_state.doc_data = doc["data"]
                st.session_state.qa_history = doc.get("qa", [])
    else:
        st.info("No history yet. Upload a doc to get started!")

# ---------------------------
# Upload & Process
# ---------------------------
st.title("⚖️ Legal Document Simplifier")
st.markdown("Upload a legal document, get a simplified summary, and ask unlimited questions.")

uploaded_file = st.file_uploader("📂 Upload Document", type=["pdf", "txt", "docx"])
doc_type = st.selectbox("Select Document Type", ["contract", "agreement", "policy", "other"])

if uploaded_file and st.button("🚀 Process Document"):
    with st.spinner("Processing..."):
        try:
            files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
            data = {"document_type": doc_type}
            response = requests.post(f"{API_BASE}/upload-document/", files=files, data=data)

            if response.status_code == 200:
                result = response.json()
                st.session_state.doc_data = result
                st.session_state.qa_history = []  # reset Q&A
                st.session_state.doc_history.append({
                    "filename": uploaded_file.name,
                    "data": result,
                    "qa": []
                })
                st.success("✅ Document processed successfully")
            else:
                st.error("❌ Upload failed")
        except Exception as e:
            st.error(f"Error: {e}")

# ---------------------------
# Show Results
# ---------------------------
# ---------------------------
# Show Results
# ---------------------------
if st.session_state.doc_data:
    simplified = st.session_state.doc_data.get("simplified_result", {})

    st.subheader("📖 Simplified Summary")
    st.markdown(simplified.get("SIMPLIFIED_SUMMARY", ""), unsafe_allow_html=True)

    st.subheader("📌 Key Clauses")
    for clause_html in simplified.get("KEY_CLAUSES", []):
        st.markdown(clause_html, unsafe_allow_html=True)

    st.subheader("⚠️ Risk Assessment")

    # 🔧 FIX: normalize so list always becomes dict
    risk_data = simplified.get("RISK_ASSESSMENT", {})
    if isinstance(risk_data, list):
        risk_data = {"risks": risk_data}

    render_risk_assessment(risk_data)

    st.subheader("📚 Important Terms")
    st.markdown(simplified.get("IMPORTANT_TERMS", ""), unsafe_allow_html=True)

    st.subheader("✅ Action Items")
    st.markdown(simplified.get("ACTION_ITEMS", ""), unsafe_allow_html=True)


    

    # ---------------------------
    # Chat Q&A Section
    # ---------------------------
    st.markdown("### 💬 Chat With Your Document")

    # Show history as chat bubbles
    for qa in st.session_state.qa_history:
        st.chat_message("user").markdown(qa["q"])
        ans = qa["a"] 
        if isinstance(ans, dict) and "text" in ans:
            st.chat_message("assistant").markdown(ans["text"], unsafe_allow_html=True)
        else:
            st.chat_message("assistant").markdown(str(ans), unsafe_allow_html=True)

    # Chat input
    if question := st.chat_input("Ask something about this document..."):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    f"{API_BASE}/ask-question/",
                    params={
                        "document_id": st.session_state.doc_data["document_id"],
                        "question": question
                    }
                )
                if response.status_code == 200:
                    answer = parse_response(response.json()["answer"])
                    entry = {
                        "q": question,
                        "a": answer,
                        "time": datetime.now().strftime("%H:%M:%S")
                    }
                    st.session_state.qa_history.append(entry)

                    if st.session_state.doc_history:
                        st.session_state.doc_history[-1]["qa"] = st.session_state.qa_history

                    st.chat_message("user").markdown(question)
                    if isinstance(answer, dict) and "text" in answer:
                        st.chat_message("assistant").markdown(answer["text"], unsafe_allow_html=True)
                    else:
                        st.chat_message("assistant").markdown(str(answer), unsafe_allow_html=True)
                else:
                    st.error("❌ Failed to get answer")
            except Exception as e:
                st.error(f"Error: {e}")
