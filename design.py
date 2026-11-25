"""HydroRelease Lab 공통 디자인. 분석 로직과 독립적으로 수정 가능."""
import streamlit as st


def apply_design():
    """모든 페이지에 공통 CSS를 적용한다."""
    st.markdown('''<style>
    :root { --lab-ink: #183b40; --lab-accent: #087e83; }
    .stApp { background: #f6f8f6; color: #183b40; }
    [data-testid="stHeader"] { background: #f6f8f6; }
    [data-testid="stAppViewContainer"] .block-container {
        max-width: 1240px; padding-top: 3.5rem; padding-bottom: 3rem;
    }
    [data-testid="stSidebar"] { background: #e8f0ed; border-right: 1px solid #cfdfd9; }
    [data-testid="stSidebar"] .block-container { padding-top: 2rem; }
    [data-testid="stSidebar"] h1 { font-size: 1.45rem; letter-spacing: -0.04em; color: #17474a; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #345b5d; }
    .stApp h1, .stApp h2, .stApp h3 { color: #183b40; letter-spacing: -0.035em; }
    .stApp h1 { font-size: clamp(1.8rem, 3vw, 2.65rem); font-weight: 750; }
    .stApp h2 { font-size: 1.45rem; margin-top: 1rem; }
    [data-testid="stMetric"] { background: #ffffff; border: 1px solid #dce6e2; border-radius: 16px; padding: 18px; box-shadow: 0 4px 16px #183b4008; }
    [data-testid="stMetricLabel"] { color: #446366; }
    [data-testid="stMetricValue"] { color: #087e83; font-weight: 700; }
    .stButton button, .stDownloadButton button {
        border-radius: 10px; min-height: 44px; font-weight: 600;
        border: 1px solid #b8cfca; background: #fff; color: #183b40;
        transition: background .15s, border-color .15s;
    }
    .stButton button:hover, .stDownloadButton button:hover { border-color: #087e83; color: #087e83; background: #edf7f4; }
    button[kind="primary"] { background: #087e83 !important; border-color: #087e83 !important; color: white !important; }
    button[kind="primary"] p { color: white !important; }
    [data-testid="stSidebar"] .stButton button { justify-content: flex-start; text-align: left; padding: .65rem .8rem; }
    [data-testid="stFileUploaderDropzone"] { background: #fff; border: 1px dashed #81aaa5; border-radius: 14px; }
    [data-testid="stDataFrame"], [data-testid="stVegaLiteChart"] { border-radius: 12px; overflow: hidden; }
    [data-testid="stAlert"] { border-radius: 12px; }
    hr { border-color: #d8e4df; }
    .lab-brand { padding: 5px 0 14px; }
    .lab-brand-kicker { font-size: .69rem; font-weight: 700; letter-spacing: .16em; color: #087e83; }
    .lab-brand-name { font-size: 1.48rem; font-weight: 750; color: #183b40; margin: .3rem 0; }
    .lab-brand-desc { font-size: .8rem; color: #446366; line-height: 1.5; }
    </style>''', unsafe_allow_html=True)


def sidebar_brand():
    """사이드바의 프로젝트 로고 영역."""
    st.markdown('''<div class="lab-brand">
    <div class="lab-brand-kicker">BIOMATERIALS · RESEARCH LAB</div>
    <div class="lab-brand-name">HydroRelease Lab</div>
    <div class="lab-brand-desc">하이드로젤 물질 방출 분석 시스템</div>
    </div>''', unsafe_allow_html=True)
