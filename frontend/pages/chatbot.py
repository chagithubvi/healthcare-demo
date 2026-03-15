"""
pages/chatbot.py — LangGraph + Groq Healthcare Intelligence Chatbot
Answers questions about dashboard data and suggests operational improvements.
"""

import streamlit as st
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

# ── LangGraph + Groq imports ─────────────────────────────────────────────────
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

from utils.charts import COLORS

# ── Groq client ───────────────────────────────────────────────────────────────
def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "").replace(" ", "")  # strip accidental spaces
    if not api_key:
        raise ValueError("GROQ_API_KEY missing from .env")
    return Groq(api_key=api_key)


# ── Pull live context from Supabase to feed into the LLM ─────────────────────
@st.cache_data(ttl=300)
def get_dashboard_context() -> str:
    """
    Builds a plain-text summary of current dashboard state.
    This is injected into every LLM prompt so the chatbot knows real numbers.
    Falls back to placeholder if DB not connected yet.
    """
    try:
        from utils.data_generator import (
            get_doctor_encounters,
            get_department_summary,
            get_supply_consumption,
            get_home_kpis,
        )

        kpis    = get_home_kpis()
        doc_df  = get_doctor_encounters()
        dept_df = get_department_summary()
        sup_df  = get_supply_consumption()

        overloaded = doc_df[doc_df["status"] == "Overloaded"][["doctor","department","pct_vs_avg"]].to_dict(orient="records")
        underutil  = doc_df[doc_df["status"] == "Underutilized"][["doctor","department","pct_vs_avg"]].to_dict(orient="records")
        critical_sup = sup_df[sup_df["risk"] == "Critical"][["supply","days_until_stockout","weekly_units"]].head(5).to_dict(orient="records")
        top_depts  = dept_df[["department","efficiency_score","revisit_rate_pct","throughput_per_day"]].head(5).to_dict(orient="records")
        worst_depts = dept_df.tail(3)[["department","efficiency_score","revisit_rate_pct"]].to_dict(orient="records")

        context = f"""
CURRENT HOSPITAL DASHBOARD DATA (live from Supabase):

=== OVERALL KPIs ===
- Total patients in dataset: {kpis['total_patients']:,}
- Active encounters today: {kpis['active_encounters_today']}
- Total providers: {kpis['total_providers']}
- Departments: {kpis['departments']}
- Overloaded providers: {kpis['overloaded_providers']}
- Critical supply items (< 7 days stock): {kpis['supply_risk_items']}
- Average patient satisfaction: {kpis['avg_satisfaction']}/5.0

=== PROVIDER WORKLOAD ===
Overloaded providers (handling >20% more than dept average):
{json.dumps(overloaded, indent=2)}

Underutilized providers (handling >20% less than dept average):
{json.dumps(underutil, indent=2)}

=== TOP PERFORMING DEPARTMENTS ===
{json.dumps(top_depts, indent=2)}

=== UNDERPERFORMING DEPARTMENTS ===
{json.dumps(worst_depts, indent=2)}

=== CRITICAL SUPPLY ALERTS ===
{json.dumps(critical_sup, indent=2)}

=== SUPPLY TOP 5 BY CONSUMPTION ===
{sup_df[['supply','monthly_units','risk']].head(5).to_string(index=False)}
"""
        return context.strip()

    except Exception as e:
        return f"""
DASHBOARD CONTEXT: Database not fully connected yet ({str(e)}).
Provide general healthcare operational intelligence advice based on best practices.
"""


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are HealthIntel AI — an intelligent operational assistant for hospital administrators and department heads.

You have access to LIVE hospital data including:
- Provider workload and utilization metrics
- Department performance benchmarks
- Medical supply consumption and stock levels
- Patient encounter statistics

Your capabilities:
1. Answer specific questions about the current dashboard data (use the numbers provided)
2. Suggest concrete operational improvements backed by the data
3. Explain what metrics mean in plain language (non-technical friendly)
4. Flag risks and recommend actions

Your tone:
- Clear and direct — no jargon unless asked
- Confident but not alarmist
- Always tie recommendations to specific data points
- Keep responses concise — 3-5 sentences max unless a detailed breakdown is asked for

When suggesting improvements, always follow this format:
🔍 Observation: [what the data shows]
⚠️ Risk: [what happens if ignored]
✅ Action: [specific recommended action]

You are NOT a medical diagnosis tool. You only handle operational/administrative intelligence.
"""


# ── LangGraph-style graph (state machine for multi-turn conversation) ─────────
class ChatState:
    """Simple state container — LangGraph pattern without full dependency."""
    def __init__(self):
        self.messages: list = []
        self.context: str = ""
        self.last_intent: str = ""

    def add_user(self, msg: str):
        self.messages.append({"role": "user", "content": msg})

    def add_assistant(self, msg: str):
        self.messages.append({"role": "assistant", "content": msg})

    def to_groq_messages(self) -> list:
        """Format messages for Groq API with context injected into system."""
        system_with_context = SYSTEM_PROMPT + f"\n\n{self.context}"
        return [{"role": "system", "content": system_with_context}] + self.messages


def classify_intent(message: str) -> str:
    """Simple intent router — determines which node to activate."""
    msg = message.lower()
    if any(w in msg for w in ["overload", "burnout", "workload", "doctor", "provider", "utiliz"]):
        return "workload_node"
    elif any(w in msg for w in ["department", "dept", "performance", "efficiency", "revisit", "throughput"]):
        return "department_node"
    elif any(w in msg for w in ["supply", "stock", "shortage", "glove", "syringe", "forecast", "procurement"]):
        return "supply_node"
    elif any(w in msg for w in ["improve", "suggest", "recommend", "optimize", "better", "fix", "action"]):
        return "improvement_node"
    else:
        return "general_node"


def route_to_node(intent: str, user_message: str, context: str) -> str:
    """
    LangGraph-style node routing — each node adds specialized instruction
    to guide the LLM response for that intent type.
    """
    node_prompts = {
        "workload_node": "Focus your answer specifically on provider workload data. Quote specific doctors and percentages from the data.",
        "department_node": "Focus on department efficiency scores, revisit rates, and throughput. Compare departments using the data provided.",
        "supply_node": "Focus on supply consumption, stock levels, and forecasting. Highlight any critical shortage risks from the data.",
        "improvement_node": "Provide 2-3 specific, actionable improvements using the 🔍 Observation / ⚠️ Risk / ✅ Action format. Base each on real data.",
        "general_node": "Give a helpful overview answer. Reference specific metrics from the data where relevant.",
    }
    return node_prompts.get(intent, node_prompts["general_node"])


def run_chat_graph(user_message: str, chat_history: list, context: str) -> str:
    """
    Main LangGraph-style execution:
    Input → Intent Classification → Node Routing → LLM → Output
    """
    if not GROQ_AVAILABLE:
        return "⚠️ Groq package not installed. Run: `pip install groq`"

    client = get_groq_client()

    # Node 1: Classify intent
    intent = classify_intent(user_message)

    # Node 2: Get node-specific instruction
    node_instruction = route_to_node(intent, user_message, context)

    # Node 3: Build messages with full history + context
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f"\n\n{context}\n\nFor this response: {node_instruction}"}
    ]
    # Include last 6 turns of history for context
    messages += chat_history[-12:]
    messages.append({"role": "user", "content": user_message})

    # Node 4: Call Groq
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.4,
        max_tokens=400,
    )

    return response.choices[0].message.content


# ── Suggested questions ───────────────────────────────────────────────────────
SUGGESTED_QUESTIONS = [
    "Which doctors are overloaded right now?",
    "Which department has the highest revisit rate?",
    "What supplies are at critical stock levels?",
    "How can we reduce provider burnout?",
    "Which department is performing best and why?",
    "What operational improvements do you recommend?",
    "Forecast supply needs for next month",
    "Which department should we prioritize for review?",
]


# ── Main render function ──────────────────────────────────────────────────────
def render():
    # ── Page Header ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="page-header" style="
        background: linear-gradient(135deg, #0D2030 0%, #071520 100%);
        border-color: #1A3850;">
      <div class="page-header-icon">🤖</div>
      <div>
        <div class="page-header-title">HealthIntel AI Assistant</div>
        <div class="page-header-desc">
          Ask anything about your hospital data · Powered by Groq LLaMA 3 · LangGraph routing
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Load context once ─────────────────────────────────────────────────────
    with st.spinner("Loading live dashboard context..."):
        context = get_dashboard_context()

    # ── Initialize session state ──────────────────────────────────────────────
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "groq_messages" not in st.session_state:
        st.session_state.groq_messages = []

    # ── Layout: chat on left, suggestions on right ────────────────────────────
    col_chat, col_side = st.columns([1.8, 1])

    with col_side:
        st.markdown(f"""
        <div style="background:#0D1F38; border:1px solid #1E3558; border-radius:14px; padding:20px; margin-bottom:16px;">
          <div style="font-family:'Space Grotesk',sans-serif; font-size:0.95rem; font-weight:600; color:#FFFFFF; margin-bottom:12px;">
            💡 Suggested Questions
          </div>
        """, unsafe_allow_html=True)

        for q in SUGGESTED_QUESTIONS:
            if st.button(q, key=f"sq_{q}", use_container_width=True):
                st.session_state.pending_question = q

        st.markdown("</div>", unsafe_allow_html=True)

        # Context status card
        db_connected = "Database not fully connected" not in context
        status_color = COLORS["green"] if db_connected else COLORS["amber"]
        status_text  = "Live Data Connected" if db_connected else "Using Fallback Mode"
        status_icon  = "🟢" if db_connected else "🟡"

        st.markdown(f"""
        <div style="background:#0D1F38; border:1px solid {status_color}30;
                    border-left:4px solid {status_color}; border-radius:12px; padding:16px;">
          <div style="font-size:0.82rem; color:{COLORS['text']}; font-weight:600;">
            {status_icon} {status_text}
          </div>
          <div style="font-size:0.75rem; color:{COLORS['muted']}; margin-top:6px;">
            Context refreshes every 5 minutes.<br>
            Chatbot answers are based on your real Supabase data.
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Clear chat button
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.groq_messages = []
            st.rerun()

    with col_chat:
        # ── Chat history display ──────────────────────────────────────────────
        chat_container = st.container()

        with chat_container:
            if not st.session_state.chat_history:
                st.markdown(f"""
                <div style="background:#0D1F38; border:1px solid #1E3558; border-radius:16px;
                            padding:32px; text-align:center; margin-bottom:20px;">
                  <div style="font-size:2.5rem; margin-bottom:12px;">🏥</div>
                  <div style="font-family:'Space Grotesk',sans-serif; font-size:1.1rem;
                              font-weight:600; color:#FFFFFF; margin-bottom:8px;">
                    Hello! I'm HealthIntel AI
                  </div>
                  <div style="font-size:0.85rem; color:{COLORS['muted']}; line-height:1.6;">
                    I have access to your live hospital data — provider workload,<br>
                    department performance, and supply levels.<br><br>
                    Ask me anything or pick a suggested question →
                  </div>
                </div>
                """, unsafe_allow_html=True)

            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f"""
                    <div style="display:flex; justify-content:flex-end; margin-bottom:12px;">
                      <div style="background:#0066FF; color:#FFFFFF; border-radius:16px 16px 4px 16px;
                                  padding:12px 16px; max-width:80%; font-size:0.88rem; line-height:1.5;">
                        {msg['content']}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="display:flex; justify-content:flex-start; margin-bottom:12px; gap:10px;">
                      <div style="background:#0D1F38; border:1px solid #1E3558;
                                  border-radius:16px 16px 16px 4px;
                                  padding:12px 16px; max-width:85%; font-size:0.88rem;
                                  line-height:1.6; color:{COLORS['text']};">
                        {msg['content'].replace(chr(10), '<br>')}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

        # ── Handle suggested question click ───────────────────────────────────
        if "pending_question" in st.session_state:
            user_input = st.session_state.pending_question
            del st.session_state.pending_question

            st.session_state.chat_history.append({"role": "user", "content": user_input})

            with st.spinner("Thinking..."):
                try:
                    reply = run_chat_graph(
                        user_input,
                        st.session_state.groq_messages,
                        context,
                    )
                except Exception as e:
                    reply = f"⚠️ Error: {str(e)}\n\nCheck your GROQ_API_KEY in .env"

            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            st.session_state.groq_messages.append({"role": "user",      "content": user_input})
            st.session_state.groq_messages.append({"role": "assistant", "content": reply})
            st.rerun()

        # ── Chat input ────────────────────────────────────────────────────────
        user_input = st.chat_input("Ask about provider workload, department performance, supplies...")

        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})

            with st.spinner("Thinking..."):
                try:
                    reply = run_chat_graph(
                        user_input,
                        st.session_state.groq_messages,
                        context,
                    )
                except Exception as e:
                    reply = f"⚠️ Error: {str(e)}\n\nCheck your GROQ_API_KEY in .env"

            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            st.session_state.groq_messages.append({"role": "user",      "content": user_input})
            st.session_state.groq_messages.append({"role": "assistant", "content": reply})
            st.rerun()


# ── Floating button renderer (called from app.py on every page) ───────────────
def render_floating_button():
    """
    Injects a floating chat button in the bottom-right corner.
    Clicking it sets session state to navigate to chatbot page.
    """
    st.markdown("""
    <style>
    .floating-chat-btn {
        position: fixed;
        bottom: 28px;
        right: 28px;
        width: 56px;
        height: 56px;
        background: linear-gradient(135deg, #0066FF, #00D4FF);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.4rem;
        cursor: pointer;
        box-shadow: 0 4px 20px rgba(0,102,255,0.4);
        z-index: 9999;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        text-decoration: none;
    }
    .floating-chat-btn:hover {
        transform: scale(1.1);
        box-shadow: 0 6px 28px rgba(0,102,255,0.6);
    }
    .floating-chat-tooltip {
        position: fixed;
        bottom: 92px;
        right: 24px;
        background: #0D1F38;
        border: 1px solid #1E3558;
        color: #E8EDF5;
        padding: 6px 12px;
        border-radius: 8px;
        font-size: 0.78rem;
        white-space: nowrap;
        z-index: 9999;
        opacity: 0;
        transition: opacity 0.2s ease;
        pointer-events: none;
    }
    </style>
    <div class="floating-chat-btn" title="Ask HealthIntel AI">🤖</div>
    """, unsafe_allow_html=True)