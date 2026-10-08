import uuid

import streamlit as st

from contracts.schemas import WorkflowRequest
from lextrace.orchestrator.factory import build_system

st.set_page_config(page_title="LexTrace", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

@st.cache_resource
def get_system():
    return build_system("config")

system = get_system()
graph = system.compile()

with st.sidebar:
    st.header("LexTrace")
    st.write("Upload PDFs and Ingest")
    uploaded_files = st.file_uploader("Upload Case Documents", accept_multiple_files=True, type=['pdf'])
    if st.button("Ingest"):
        st.success("Ingested!")
        
    st.write("Choose Documents")
    doc_ids = st.multiselect("Active Documents", ["case_bundle_001", "judgment_2", "statute_2"])

tab_review, tab_draft, tab_research, tab_chat = st.tabs(["Review", "Draft", "Research", "Chat"])

def render_output(out):
    if not out:
        return
        
    st.markdown("---")
    st.info("⚠️ Not legal advice")

    blocked = [c for c in getattr(out, 'trace', []) if c.get("event") == "dropped_unverified"]
    n_shown = len(out.claims)
    m_blocked = len(blocked)
    st.success(f"Verification passed: {n_shown} claims shown, {m_blocked} claims blocked")

    st.metric("Confidence", f"{out.confidence:.0%}")
    st.markdown(out.rendered_markdown)
    
    with st.expander("Evidence"):
        for claim in out.claims:
            for ev in claim.evidence:
                st.markdown(f"**Document**: {ev.chunk_id}")
                st.markdown(f"> {ev.quote}")
                
    if out.claims:
        st.write("### Claims")
        claims_data = [{"ID": c.claim_id, "Text": c.text, "Status": c.status} for c in out.claims]
        st.dataframe(claims_data)
        
    if getattr(out, 'missing_info', None):
        st.write("### Missing Info")
        for m in out.missing_info:
            st.warning(f"{m.slot}: {m.why_needed} (Status: {m.status})")
            
    if getattr(out, 'contradictions', None):
        st.write("### Contradictions")
        for c in out.contradictions:
            st.error(f"{c.explanation}")

def run_workflow(workflow_name: str, query: str):
    req = WorkflowRequest(
        workflow=workflow_name, 
        query=query, 
        session_id=st.session_state.session_id,
        case_doc_ids=doc_ids
    )
    res = graph.invoke({"request": req})
    return res.get("output")

with tab_review:
    if st.button("Run Review"):
        with st.spinner("Running review..."):
            out = run_workflow("review", "Review all documents")
            render_output(out)

with tab_draft:
    draft_q = st.text_input("Draft requirements")
    if st.button("Run Draft"):
        with st.spinner("Running draft..."):
            out = run_workflow("draft", draft_q)
            render_output(out)
            
with tab_research:
    res_q = st.text_input("Research question")
    if st.button("Run Research"):
        with st.spinner("Running research..."):
            out = run_workflow("research", res_q)
            render_output(out)

with tab_chat:
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                out = run_workflow("chat", prompt)
                st.session_state.messages.append({"role": "assistant", "content": out.rendered_markdown if out else "Error"})
                render_output(out)
