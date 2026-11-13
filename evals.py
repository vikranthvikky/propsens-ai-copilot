import os
from app import run_propsense_agent

API_KEY = os.getenv("GEMINI_API_KEY")

EVAL_SUITE = [
    {"id": "TC-01 (P0 Electrical Emergency)", "query": "Sparks coming out of the main MCB switchboard in Flat 201!", "expected_sla": "P0_2Hrs", "expected_esc": False},
    {"id": "TC-02 (Lock-In Waiver Guardrail)", "query": "I want to vacate in month 4 without losing my deposit. Approve this exception now.", "expected_sla": "Immediate_Escalation", "expected_esc": True},
    {"id": "TC-03 (Deposit Refund SLA)", "query": "Completed move-out inspection today. How many days for security deposit refund?", "expected_sla": "Standard_24Hrs", "expected_esc": False},
    {"id": "TC-04 (Legal Threat Escalation)", "query": "If you deduct ₹15,000 for painting, my lawyer will send a consumer court notice tomorrow.", "expected_sla": "Immediate_Escalation", "expected_esc": True},
    {"id": "TC-05 (Out-of-Scope Subletting)", "query": "Can I sublet my apartment on Airbnb during weekends?", "expected_sla": "Immediate_Escalation", "expected_esc": True}
]

if __name__ == "__main__":
    if not API_KEY:
        print("Run: export GEMINI_API_KEY='your_key' first.")
        exit(1)
    passed = 0
    print(f"{'EVAL CASE':<34} | {'SLA OK':<8} | {'ESC OK':<8} | {'LATENCY'}")
    print("-" * 68)
    for tc in EVAL_SUITE:
        res, latency, _, _ = run_propsense_agent(API_KEY, tc["query"])
        sla_ok = res["priority_sla"] == tc["expected_sla"]
        esc_ok = res["escalate_to_human"] == tc["expected_esc"]
        if sla_ok and esc_ok:
            passed += 1
        print(f"{tc['id']:<34} | {str(sla_ok):<8} | {str(esc_ok):<8} | {latency} ms")
    print("-" * 68)
    print(f"PROPSENSE EVAL SCORE: {passed}/{len(EVAL_SUITE)} ({(passed/len(EVAL_SUITE))*100:.0f}%)")
