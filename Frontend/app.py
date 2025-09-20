import streamlit as st
import requests
import json
import re

import os
#API_BASE = os.getenv("API_BASE", "http://backend:8089")
API_BASE = "http://localhost:8089"

st.set_page_config(page_title="Legal Document Simplifier", layout="wide")

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
        # Handle both key formats
        overall_score = (
            risk_data.get("Overall Risk Score")
            or risk_data.get("overall_score")
            or "N/A"
        )
        st.markdown(f"**Overall Risk Score:** {overall_score}")

        # Risks list
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


# ---------------------------
# Sidebar
# ---------------------------
st.sidebar.header("📂 Document Manager")

# State: keep track of uploaded documents
if "documents" not in st.session_state:
    st.session_state.documents = {}

# Upload document
uploaded_file = st.sidebar.file_uploader("Upload a document", type=["pdf", "txt", "docx"])
doc_type = st.sidebar.selectbox("Document Type", ["contract", "agreement", "policy", "other"])

if uploaded_file is not None:
    with st.spinner("Processing document..."):
        files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
        data = {"document_type": doc_type}
        response = requests.post(f"{API_BASE}/upload-document/", files=files, data=data)

        if response.status_code == 200:
            doc_data = response.json()
            # sanitize simplified_result
            doc_data["simplified_result"] = parse_response(doc_data.get("simplified_result", {}))
            st.session_state.documents[doc_data["document_id"]] = doc_data
            st.sidebar.success(f"Uploaded: {uploaded_file.name}")
        else:
            st.sidebar.error("Upload failed")

# Sidebar document selector
if st.session_state.documents:
    selected_doc_id = st.sidebar.selectbox(
        "Select a document", 
        options=list(st.session_state.documents.keys()),
        format_func=lambda x: st.session_state.documents[x]["filename"]
    )
else:
    selected_doc_id = None

# ---------------------------
# Main Area
# ---------------------------
st.title("⚖️ Legal Document Simplifier")

if selected_doc_id:
    doc_data = st.session_state.documents[selected_doc_id]
    simplified = doc_data["simplified_result"]

    # Show structured summary
    st.subheader("📖 Simplified Summary")
    st.markdown(simplified.get("SIMPLIFIED_SUMMARY", ""), unsafe_allow_html=True)

    st.subheader("📌 Key Clauses")
    for clause_html in simplified.get("KEY_CLAUSES", []):
        st.markdown(clause_html, unsafe_allow_html=True)

    st.subheader("⚠️ Risk Assessment")
    render_risk_assessment(simplified.get("RISK_ASSESSMENT", {}))

    st.subheader("📚 Important Terms")
    st.markdown(simplified.get("IMPORTANT_TERMS", ""), unsafe_allow_html=True)

    st.subheader("✅ Action Items")
    st.markdown(simplified.get("ACTION_ITEMS", ""), unsafe_allow_html=True)

    with st.expander("📜 Full Document with Highlights"):
        st.markdown(simplified.get("highlighted_document", ""), unsafe_allow_html=True)

    # Q&A Section
    st.subheader("💬 Ask a Question")
    user_question = st.text_input("Enter your question:")
    if st.button("Ask"):
        with st.spinner("Fetching answer..."):
            response = requests.post(
                f"{API_BASE}/ask-question/",
                params={"document_id": selected_doc_id, "question": user_question}
            )
            if response.status_code == 200:
                raw_answer = response.json()["answer"]
                answer = parse_response(raw_answer)
                if isinstance(answer, dict):
                    st.markdown(answer.get("text", ""), unsafe_allow_html=True)
                else:
                    st.markdown(str(answer), unsafe_allow_html=True)
            else:
                st.error("Failed to get answer")
else:
    st.info("Upload and select a document from the sidebar to begin.")
