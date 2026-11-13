import os
import time
import json
import streamlit as st
from pypdf import PdfReader
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

st.set_page_config(page_title="PropSense AI | Lease & Tenant Co-Pilot", page_icon="🏢", layout="wide")

class TenantCoPilotDecision(BaseModel):
    inquiry_type: str = Field(description="One of: Lease_Clause_Query, Maintenance_Triage, Deposit_Exit_Query, Waiver_Or_Dispute, Out_Of_Scope")
    priority_sla: str = Field(description="For maintenance: P0_2Hrs, P1_24Hrs, P2_72Hrs. For non-maintenance: Standard_24Hrs or Immediate_Escalation")
    extracted_clause_reference: str = Field(description="Exact clause from uploaded lease PDF or Bangalore SOP supporting the answer")
    escalate_to_human: bool = Field(description="True if deposit dispute >10k INR, lock-in waiver request, legal threat, out-of-scope query, or confidence < 0.85")
    confidence_score: float = Field(description="Confidence from 0.0 to 1.0 grounded strictly in provided lease/SOP")
    tenant_reply_draft: str = Field(description="Clear, polite, policy-compliant response to the tenant")
    internal_ops_action: str = Field(description="Actionable next step for the property operations team")

with open("bangalore_lease_sop.md", "r") as f:
    BASE_SOP = f.read()

def extract_pdf_text(uploaded_file) -> str:
    reader = PdfReader(uploaded_file)
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text).strip()

def run_propsense_agent(api_key: str, tenant_query: str, lease_context: str = ""):
    client = genai.Client(api_key=api_key)
    
    combined_context = f"STANDARD BANGALORE PROPERTY SOP:\n{BASE_SOP}"
    if lease_context:
        combined_context += f"\n\nSPECIFIC UPLOADED TENANT LEASE DOCUMENT (OVERRIDES DEFAULT SOP IF CONFLICTING):\n{lease_context[:15000]}"

    system_instruction = f"""
    You are PropSense AI, an intelligent Property & Lease Operations Co-Pilot for residential portfolios.
    Analyze the tenant's message (and uploaded lease document, if provided) to classify the request, assign maintenance SLAs, and draft a compliant response.

    STRICT GUARDRAILS:
    1. Rely ONLY on the provided SOP and Uploaded Lease Document. Specific clauses in the Uploaded Lease override general SOP defaults if they differ.
    2. Never approve lock-in waivers, rent discounts, or deposit deduction waivers—always set `escalate_to_human = true` and `priority_sla = "Immediate_Escalation"`.
    3. If the answer is not covered in the documents (e.g., subletting on Airbnb, pets if unmentioned), set `escalate_to_human = true`, `priority_sla = "Immediate_Escalation"`, `inquiry_type = "Out_Of_Scope"`, and `confidence_score = 0.4`.

    KNOWLEDGE CONTEXT:
    {combined_context}
    """

    start_time = time.time()
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=f"Tenant Message: {tenant_query}",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=TenantCoPilotDecision,
            temperature=0.1,
        ),
    )
    latency_ms = round((time.time() - start_time) * 1000)
    usage = response.usage_metadata
    tokens = (usage.prompt_token_count or 0) + (usage.candidates_token_count or 0)
    est_cost_usd = round((tokens / 1_000_000) * 0.15, 6)
    return json.loads(response.text), latency_ms, tokens, est_cost_usd

st.title("🏢 PropSense AI — Automated Lease & Tenant Inquiry Co-Pilot")
st.caption("AI Product Portfolio | Dual-Layer RAG for Residential Portfolio Operations")

with st.sidebar:
    st.header("Configuration & Lease Context")
    default_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", "")) if hasattr(st, "secrets") else os.getenv("GEMINI_API_KEY", "")
    api_key = st.text_input("Gemini API Key", type="password", value=default_key)
    uploaded_lease = st.file_uploader("Upload Custom Lease PDF (Overrides SOP)", type=["pdf"])
    lease_text = ""
    if uploaded_lease:
        lease_text = extract_pdf_text(uploaded_lease)
        st.success(f"Extracted {len(lease_text)} chars from `{uploaded_lease.name}`")
    st.markdown("---")
    st.markdown("**Architecture Highlights:**")
    st.markdown("- **Dual-Layer RAG:** Base SOP + Dynamic PDF Lease override\n- **SLA Triage:** Automated P0 / P1 / P2 vendor dispatch\n- **Legal Guardrails:** Blocks unauthorized waivers & hallucinations")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("1. Tenant Inquiry / Maintenance Ticket")
    scenario = st.selectbox("Select Test Ticket", [
        "P0 Emergency: Water Pipe Burst in Kitchen",
        "Lock-In Waiver & Early Exit Request",
        "Security Deposit Refund Timeline Query",
        "P2 Routine: Wardrobe Hinge & Bulb Replacement",
        "Out-of-Scope Hallucination Check (Airbnb Sublet)",
        "Custom Inquiry"
    ])

    if scenario == "P0 Emergency: Water Pipe Burst in Kitchen":
        default_msg = "Urgent! The main water pipe under the kitchen sink burst and water is flooding the living room in Flat 402."
    elif scenario == "Lock-In Waiver & Early Exit Request":
        default_msg = "I moved in 3 months ago but got transferred to Pune. Please waive my 6-month lock-in period and refund my full ₹1,50,000 deposit."
    elif scenario == "Security Deposit Refund Timeline Query":
        default_msg = "I handed over the keys yesterday after completing my 60-day notice. When will my security deposit be credited?"
    elif scenario == "P2 Routine: Wardrobe Hinge & Bulb Replacement":
        default_msg = "Two bedroom LED bulbs have fused and one wardrobe hinge is loose. Can someone fix both?"
    elif scenario == "Out-of-Scope Hallucination Check (Airbnb Sublet)":
        default_msg = "Can I list my spare bedroom on Airbnb on weekends while I travel?"
    else:
        default_msg = ""

    tenant_msg = st.text_area("Tenant Message", value=default_msg, height=130)
    submit_btn = st.button("Process Tenant Ticket", type="primary", use_container_width=True)

with col2:
    st.subheader("2. Co-Pilot Triage & Ops Routing")
    if submit_btn:
        if not api_key:
            st.error("Enter your Gemini API Key in the sidebar.")
        elif not tenant_msg.strip():
            st.warning("Please enter a tenant message.")
        else:
            with st.spinner("Analyzing lease clauses & SOP SLAs..."):
                res, latency, tokens, cost = run_propsense_agent(api_key, tenant_msg, lease_text)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Latency", f"{latency} ms")
            m2.metric("Confidence", f"{int(res['confidence_score']*100)}%")
            m3.metric("SLA Tier", res["priority_sla"])
            m4.metric("Est. Cost", f"${cost}")

            if res["escalate_to_human"] or res["confidence_score"] < 0.85:
                st.warning(f"🚨 **ESCALATED TO PROPERTY MANAGER** | Type: `{res['inquiry_type']}`")
            else:
                st.success(f"✅ **AUTO-RESOLVED BY CO-PILOT** | Type: `{res['inquiry_type']}`")

            st.markdown(f"**Internal Ops Action:** {res['internal_ops_action']}")
            st.info(f"**Draft Response to Tenant:**\n\n{res['tenant_reply_draft']}")
            st.caption(f"📄 **Grounded Citation:** {res['extracted_clause_reference']}")
