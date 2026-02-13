import streamlit as st
import requests
import json
import time

# ----------------------------
# Page Config
# ----------------------------
st.set_page_config(
    page_title="TestGen AI",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ----------------------------
# Custom CSS
# ----------------------------
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    }

    /* Header styling */
    .main-header {
        text-align: center;
        padding: 2rem 0 1rem 0;
    }

    .main-header h1 {
        color: #00d4ff;
        font-size: 3rem;
        font-weight: 800;
        letter-spacing: 2px;
        margin-bottom: 0.3rem;
    }

    .main-header p {
        color: #a0aec0;
        font-size: 1.1rem;
        margin-top: 0;
    }

    /* Card styling */
    .card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 1.5rem;
        backdrop-filter: blur(10px);
    }

    /* Test case card */
    .tc-card {
        background: rgba(255, 255, 255, 0.06);
        border-left: 4px solid #00d4ff;
        border-radius: 8px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
    }

    .tc-card-negative {
        border-left-color: #ff6b6b;
    }

    .tc-card-boundary {
        border-left-color: #ffd93d;
    }

    .tc-title {
        color: #e2e8f0;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }

    .tc-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 8px;
    }

    .badge-functional { background: #00d4ff22; color: #00d4ff; border: 1px solid #00d4ff44; }
    .badge-negative { background: #ff6b6b22; color: #ff6b6b; border: 1px solid #ff6b6b44; }
    .badge-boundary { background: #ffd93d22; color: #ffd93d; border: 1px solid #ffd93d44; }
    .badge-high { background: #ff6b6b22; color: #ff6b6b; border: 1px solid #ff6b6b44; }
    .badge-medium { background: #ffd93d22; color: #ffd93d; border: 1px solid #ffd93d44; }
    .badge-low { background: #68d39122; color: #68d391; border: 1px solid #68d39144; }

    .step-row {
        color: #cbd5e0;
        padding: 6px 0;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        font-size: 0.92rem;
    }

    .step-num {
        color: #00d4ff;
        font-weight: 700;
        margin-right: 8px;
    }

    .step-expected {
        color: #68d391;
        font-style: italic;
    }

    /* Metrics */
    .metric-box {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 800;
        color: #00d4ff;
    }

    .metric-label {
        color: #a0aec0;
        font-size: 0.85rem;
        margin-top: 4px;
    }

    /* Input labels */
    .stTextArea label, .stTextInput label {
        color: #e2e8f0 !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
    }

    /* Button */
    .stButton > button {
        background: linear-gradient(90deg, #00d4ff, #7b2ff7) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.7rem 2.5rem !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        letter-spacing: 1px !important;
        transition: all 0.3s ease !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(0, 212, 255, 0.3) !important;
    }

    /* Spinner */
    .stSpinner > div {
        border-color: #00d4ff !important;
    }

    /* Hide streamlit defaults */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Divider */
    .divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0,212,255,0.3), transparent);
        margin: 2rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Header
# ----------------------------
st.markdown("""
<div class="main-header">
    <h1>🧪 TestGen AI</h1>
    <p>AI-Powered Test Case Generation from Requirements</p>
</div>
<div class="divider"></div>
""", unsafe_allow_html=True)

# ----------------------------
# API Config
# ----------------------------
API_URL = "http://localhost:8000"


def check_server():
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def get_badge_class(type_str):
    t = type_str.lower()
    if t == "negative":
        return "badge-negative"
    elif t == "boundary":
        return "badge-boundary"
    return "badge-functional"


def get_priority_class(priority_str):
    p = priority_str.lower()
    if p == "high":
        return "badge-high"
    elif p == "low":
        return "badge-low"
    return "badge-medium"


def get_card_class(type_str):
    t = type_str.lower()
    if t == "negative":
        return "tc-card tc-card-negative"
    elif t == "boundary":
        return "tc-card tc-card-boundary"
    return "tc-card"


# ----------------------------
# Server Status
# ----------------------------
server_online = check_server()

if not server_online:
    st.error("⚠️ Backend server is not running. Start it with: `uvicorn backend.main:app --reload --port 8000`")
    st.stop()

# ----------------------------
# Input Section
# ----------------------------
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown("### 📝 Requirement Details")

    description = st.text_area(
        "Description",
        placeholder="e.g., Users should be able to login with email and password",
        height=100,
    )

    user_story = st.text_area(
        "User Story (optional)",
        placeholder="e.g., As a registered user, I want to login so I can access my account",
        height=80,
    )

    ac_text = st.text_area(
        "Acceptance Criteria (one per line)",
        placeholder="Valid credentials allow login\nInvalid credentials show error\nPassword is masked",
        height=120,
    )

    st.markdown("")

    col_btn1, col_btn2, _ = st.columns([1, 1, 2])

    with col_btn1:
        generate_btn = st.button("🚀 Generate", use_container_width=True)

    with col_btn2:
        evaluate_btn = st.button("📊 Evaluate", use_container_width=True)

# ----------------------------
# Parse acceptance criteria
# ----------------------------
def parse_acceptance_criteria(text):
    lines = text.strip().split("\n")
    criteria = []
    for line in lines:
        cleaned = line.strip()
        # Remove common prefixes like "- ", "* ", "1. ", "1) "
        for prefix in ["- ", "* ", "• "]:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
        # Remove numbered prefixes
        import re
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            criteria.append(cleaned)
    return criteria


# ----------------------------
# Handle Generate
# ----------------------------
with col_right:
    if generate_btn:
        if not description.strip():
            st.warning("Please enter a requirement description.")
        elif not ac_text.strip():
            st.warning("Please enter at least one acceptance criterion.")
        else:
            acceptance_criteria = parse_acceptance_criteria(ac_text)

            with st.spinner("🤖 Generating test cases... This may take 30-60 seconds"):
                try:
                    payload = {
                        "description": description.strip(),
                        "user_story": user_story.strip(),
                        "acceptance_criteria": acceptance_criteria,
                    }

                    response = requests.post(
                        f"{API_URL}/generate",
                        json=payload,
                        timeout=120,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        test_cases = data["test_cases"]

                        st.markdown(f"### ✅ Generated {len(test_cases)} Test Cases")
                        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

                        for i, tc in enumerate(test_cases):
                            type_badge = get_badge_class(tc["type"])
                            priority_badge = get_priority_class(tc["priority"])
                            card_class = get_card_class(tc["type"])

                            steps_html = ""
                            for step in tc["steps"]:
                                expected = step.get("expected", "")
                                expected_html = f' → <span class="step-expected">{expected}</span>' if expected else ""
                                steps_html += f'''
                                <div class="step-row">
                                    <span class="step-num">Step {step["step"]}</span>
                                    {step["action"]}{expected_html}
                                </div>
                                '''

                            st.markdown(f"""
                            <div class="{card_class}">
                                <div class="tc-title">{tc["title"]}</div>
                                <span class="tc-badge {type_badge}">{tc["type"]}</span>
                                <span class="tc-badge {priority_badge}">{tc["priority"]}</span>
                                {steps_html}
                            </div>
                            """, unsafe_allow_html=True)

                        # Download button
                        st.download_button(
                            label="📥 Download as JSON",
                            data=json.dumps(test_cases, indent=2),
                            file_name="generated_test_cases.json",
                            mime="application/json",
                        )

                    else:
                        st.error(f"Server error: {response.json().get('detail', 'Unknown error')}")

                except requests.exceptions.Timeout:
                    st.error("⏱️ Request timed out. The model may be slow. Try again.")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    # ----------------------------
    # Handle Evaluate
    # ----------------------------
    elif evaluate_btn:
        if not description.strip():
            st.warning("Please enter a requirement description.")
        elif not ac_text.strip():
            st.warning("Please enter at least one acceptance criterion.")
        else:
            acceptance_criteria = parse_acceptance_criteria(ac_text)

            with st.spinner("🤖 Generating & evaluating... This may take 30-60 seconds"):
                try:
                    payload = {
                        "description": description.strip(),
                        "user_story": user_story.strip(),
                        "acceptance_criteria": acceptance_criteria,
                    }

                    response = requests.post(
                        f"{API_URL}/evaluate",
                        json=payload,
                        timeout=120,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        test_cases = data["test_cases"]

                        # Metrics
                        st.markdown("### 📊 Quality Metrics")

                        m1, m2, m3, m4 = st.columns(4)

                        with m1:
                            st.markdown(f"""
                            <div class="metric-box">
                                <div class="metric-value">{data["accov_at_05"]:.0%}</div>
                                <div class="metric-label">AC Coverage @0.5</div>
                            </div>
                            """, unsafe_allow_html=True)

                        with m2:
                            st.markdown(f"""
                            <div class="metric-box">
                                <div class="metric-value">{data["accov_at_065"]:.0%}</div>
                                <div class="metric-label">AC Coverage @0.65</div>
                            </div>
                            """, unsafe_allow_html=True)

                        with m3:
                            st.markdown(f"""
                            <div class="metric-box">
                                <div class="metric-value">{data["negative_ratio"]:.0%}</div>
                                <div class="metric-label">Negative Ratio</div>
                            </div>
                            """, unsafe_allow_html=True)

                        with m4:
                            st.markdown(f"""
                            <div class="metric-box">
                                <div class="metric-value">{data["num_test_cases"]}</div>
                                <div class="metric-label">Test Cases</div>
                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

                        st.markdown(f"### ✅ Generated {len(test_cases)} Test Cases")

                        for i, tc in enumerate(test_cases):
                            type_badge = get_badge_class(tc["type"])
                            priority_badge = get_priority_class(tc["priority"])
                            card_class = get_card_class(tc["type"])

                            steps_html = ""
                            for step in tc["steps"]:
                                expected = step.get("expected", "")
                                expected_html = f' → <span class="step-expected">{expected}</span>' if expected else ""
                                steps_html += f'''
                                <div class="step-row">
                                    <span class="step-num">Step {step["step"]}</span>
                                    {step["action"]}{expected_html}
                                </div>
                                '''

                            st.markdown(f"""
                            <div class="{card_class}">
                                <div class="tc-title">{tc["title"]}</div>
                                <span class="tc-badge {type_badge}">{tc["type"]}</span>
                                <span class="tc-badge {priority_badge}">{tc["priority"]}</span>
                                {steps_html}
                            </div>
                            """, unsafe_allow_html=True)

                        st.download_button(
                            label="📥 Download as JSON",
                            data=json.dumps(data, indent=2),
                            file_name="evaluation_results.json",
                            mime="application/json",
                        )

                    else:
                        st.error(f"Server error: {response.json().get('detail', 'Unknown error')}")

                except requests.exceptions.Timeout:
                    st.error("⏱️ Request timed out. The model may be slow. Try again.")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    else:
        # Default state — show instructions
        st.markdown("""
        <div class="card">
            <h3 style="color: #00d4ff; margin-top: 0;">👋 How to Use</h3>
            <div style="color: #cbd5e0; line-height: 1.8;">
                <p><strong>1.</strong> Enter your requirement description on the left</p>
                <p><strong>2.</strong> Add a user story (optional)</p>
                <p><strong>3.</strong> List acceptance criteria — one per line</p>
                <p><strong>4.</strong> Click <strong>🚀 Generate</strong> for test cases</p>
                <p><strong>5.</strong> Click <strong>📊 Evaluate</strong> for test cases + quality metrics</p>
            </div>
        </div>
        """, unsafe_allow_html=True)