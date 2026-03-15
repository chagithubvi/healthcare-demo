import streamlit as st

st.set_page_config(
    page_title="HealthIntel Platform",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #050D1A;
    color: #E8EDF5;
}
.stApp { background-color: #050D1A; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0A1628 0%, #071020 100%);
    border-right: 1px solid #1A2D4A;
}
[data-testid="stSidebar"] * { color: #C8D8F0 !important; }

.metric-card {
    background: linear-gradient(135deg, #0D1F38 0%, #0A1828 100%);
    border: 1px solid #1E3558;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--accent, linear-gradient(90deg, #00D4FF, #0066FF));
}
.metric-value {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.4rem;
    font-weight: 700;
    color: #FFFFFF;
    line-height: 1;
}
.metric-label {
    font-size: 0.8rem;
    font-weight: 500;
    color: #7A9AC0;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 6px;
}
.metric-delta { font-size: 0.85rem; font-weight: 600; margin-top: 8px; }
.delta-up { color: #00E5A0; }
.delta-down { color: #FF4D6A; }

.alert-card {
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 10px;
    border-left: 4px solid;
    display: flex;
    align-items: flex-start;
    gap: 12px;
}
.alert-critical { background: rgba(255,77,106,0.08);  border-color: #FF4D6A; }
.alert-warning  { background: rgba(255,181,71,0.08);  border-color: #FFB547; }
.alert-info     { background: rgba(0,212,255,0.08);   border-color: #00D4FF; }
.alert-success  { background: rgba(0,229,160,0.08);   border-color: #00E5A0; }

.section-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.35rem;
    font-weight: 600;
    color: #FFFFFF;
    margin-bottom: 4px;
}
.section-sub { font-size: 0.82rem; color: #5A7A9A; margin-bottom: 20px; }

.page-header {
    background: linear-gradient(135deg, #0D1F38 0%, #0A1828 100%);
    border: 1px solid #1E3558;
    border-radius: 20px;
    padding: 32px 36px;
    margin-bottom: 28px;
    display: flex;
    align-items: center;
    gap: 20px;
}
.page-header-icon { font-size: 3rem; line-height: 1; }
.page-header-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.9rem;
    font-weight: 700;
    color: #FFFFFF;
    margin: 0;
}
.page-header-desc { font-size: 0.9rem; color: #5A7A9A; margin-top: 4px; }
.block-container { padding-top: 2rem; padding-bottom: 2rem; }

[data-testid="stChatInput"] textarea { color: #E8EDF5 !important; }

.stButton > button {
    background: #0D1F38 !important;
    border: 1px solid #1E3558 !important;
    color: #C8D8F0 !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
    text-align: left !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background: #1A2D48 !important;
    border-color: #00D4FF !important;
    color: #FFFFFF !important;
}
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding: 8px 0 24px 0;'>
      <div style='font-family:"Space Grotesk",sans-serif; font-size:1.4rem;
                  font-weight:700; color:#FFFFFF;'>🏥 HealthIntel</div>
      <div style='font-size:0.75rem; color:#3A5A7A; margin-top:2px;'>
        AI-Powered Healthcare Intelligence
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='font-size:0.7rem; color:#3A5A7A; text-transform:uppercase;
                letter-spacing:.1em; margin-bottom:8px;'>Navigation</div>
    """, unsafe_allow_html=True)

    page = st.selectbox(
        "Go to",
        [
            "🏠  Home Overview",
            "👨‍⚕️  Doctor Utilization",
            "🏢  Department Performance",
            "📦  Supply Intelligence",
            "🤖  AI Assistant",
        ],
        label_visibility="collapsed"
    )

    st.markdown("<hr style='border-color:#1E3558; margin: 24px 0;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:0.7rem; color:#3A5A7A; text-transform:uppercase;
                letter-spacing:.1em; margin-bottom:8px;'>Data Source</div>
    """, unsafe_allow_html=True)
    st.selectbox("Source", ["Supabase Live (Synthea 10K)"], label_visibility="collapsed")

    st.markdown("<hr style='border-color:#1E3558; margin: 24px 0;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:0.72rem; color:#3A5A7A; line-height:1.6;'>
      <b style='color:#5A7A9A;'>Connected</b><br>
      Supabase · Synthea 10K<br>
      Groq LLaMA 3 · LangGraph<br>
      <span style='color:#00E5A0;'>● Live</span>
    </div>
    """, unsafe_allow_html=True)

# ─── Page routing ─────────────────────────────────────────────────────────────
if "Home" in page:
    from pages import home
    home.render()

elif "Doctor" in page:
    from pages import doctor_utilization
    doctor_utilization.render()

elif "Department" in page:
    from pages import department_performance
    department_performance.render()

elif "Supply" in page:
    from pages import supply_intelligence
    supply_intelligence.render()

elif "AI Assistant" in page:
    from pages import chatbot
    chatbot.render()

# ─── Floating chat button on all pages except chatbot ────────────────────────
if "AI Assistant" not in page:
    from pages.chatbot import render_floating_button
    render_floating_button()