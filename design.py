
"""HydroRelease Lab 공통 디자인 모듈"""

import streamlit as st


def apply_design():
    """모든 페이지에 공통 CSS 및 도트 폰트를 적용한다."""

    st.markdown('''
    <style>

    /* 1. 갈무리11 도트 폰트 불러오기 */
    @import url('https://cdn.jsdelivr.net/npm/galmuri/dist/galmuri.css');

    /* 2. 기본 색상 및 폰트 설정 */
    :root {
        --lab-ink: #183b40;
        --lab-accent: #087e83;
        --lab-font: 'Galmuri11', monospace;
    }

    html, body, .stApp {
        font-family: var(--lab-font) !important;
    }

    h1, h2, h3, h4, h5, h6,
    p, label, input, textarea, button,
    [data-testid="stMarkdownContainer"],
    [data-testid="stWidgetLabel"],
    [data-testid="stMetricValue"],
    [data-testid="stMetricLabel"],
    [data-testid="stCaptionContainer"],
    [data-baseweb="select"],
    [data-baseweb="input"],
    [data-baseweb="textarea"] {
        font-family: var(--lab-font) !important;
    }

    /* 3. 전체 배경 */
    .stApp {
        background: #f6f8f6;
        color: #183b40;
    }

    [data-testid="stHeader"] {
        background: #f6f8f6;
    }

    [data-testid="stAppViewContainer"] .block-container {
        max-width: 1240px;
        padding-top: 3.5rem;
        padding-bottom: 3rem;
    }

    /* 4. 사이드바 디자인 */
    [data-testid="stSidebar"] {
        background: #e8f0ed;
        border-right: 1px solid #cfdfd9;
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }

    [data-testid="stSidebar"] h1 {
        font-size: 1.45rem;
        letter-spacing: 0;
        color: #17474a;
    }

    [data-testid="stSidebar"]
    [data-testid="stMarkdownContainer"] p {
        color: #345b5d;
    }

    /* 5. 제목 디자인 */
    .stApp h1,
    .stApp h2,
    .stApp h3 {
        color: #183b40;
        letter-spacing: 0;
        font-family: var(--lab-font) !important;
    }

    .stApp h1 {
        font-size: clamp(1.8rem, 3vw, 2.65rem);
        font-weight: 700;
    }

    .stApp h2 {
        font-size: 1.45rem;
        margin-top: 1rem;
    }

    .stApp h3 {
        font-size: 1.2rem;
    }

    /* 6. 분석 결과 수치 카드 */
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #dce6e2;
        border-radius: 16px;
        padding: 18px;
        box-shadow: 0 4px 16px #183b4008;
    }

    [data-testid="stMetricLabel"] {
        color: #446366;
    }

    [data-testid="stMetricValue"] {
        color: #087e83;
        font-weight: 700;
        font-family: var(--lab-font) !important;
    }

    /* 7. 일반 버튼 및 다운로드 버튼 */
    .stButton button,
    .stDownloadButton button {
        border-radius: 10px;
        min-height: 44px;
        font-weight: 500;
        border: 1px solid #b8cfca;
        background: #ffffff;
        color: #183b40;
        font-family: var(--lab-font) !important;
        transition: background .15s, border-color .15s;
    }

    .stButton button:hover,
    .stDownloadButton button:hover {
        border-color: #087e83;
        color: #087e83;
        background: #edf7f4;
    }

    /* 8. 선택된 버튼 디자인 */
    button[kind="primary"] {
        background: #087e83 !important;
        border-color: #087e83 !important;
        color: #ffffff !important;
    }

    button[kind="primary"] p {
        color: #ffffff !important;
    }

    /* 9. 사이드바 페이지 이동 버튼 */
    [data-testid="stSidebar"] .stButton button {
        justify-content: flex-start;
        text-align: left;
        padding: .65rem .8rem;
    }

    /* 10. 동영상 및 파일 업로드 영역 */
    [data-testid="stFileUploaderDropzone"] {
        background: #ffffff;
        border: 1px dashed #81aaa5;
        border-radius: 14px;
    }

    /* 11. 데이터 표 및 그래프 */
    [data-testid="stDataFrame"],
    [data-testid="stVegaLiteChart"] {
        border-radius: 12px;
        overflow: hidden;
    }

    [data-testid="stVegaLiteChart"] svg text {
        font-family: var(--lab-font) !important;
    }

    /* 12. 알림 메시지 */
    [data-testid="stAlert"] {
        border-radius: 12px;
    }

    /* 13. 구분선 */
    hr {
        border-color: #d8e4df;
    }

    /* 14. 사이드바 프로젝트 로고 */
    .lab-brand {
        padding: 5px 0 14px;
        font-family: var(--lab-font) !important;
    }

    .lab-brand-kicker {
        font-size: .69rem;
        font-weight: 700;
        letter-spacing: .08em;
        color: #087e83;
    }

    .lab-brand-name {
        font-size: 1.48rem;
        font-weight: 700;
        color: #183b40;
        margin: .3rem 0;
    }

    .lab-brand-desc {
        font-size: .8rem;
        color: #446366;
        line-height: 1.7;
    }

    </style>
    ''', unsafe_allow_html=True)


def sidebar_brand():
    """사이드바의 프로젝트 로고 영역."""

    st.markdown('''
    <div class="lab-brand">
        <div class="lab-brand-kicker">
            BIOMATERIALS · RESEARCH LAB
        </div>

        <div class="lab-brand-name">
            HydroRelease Lab
        </div>

        <div class="lab-brand-desc">
            하이드로젤 물질 방출 분석 시스템
        </div>
    </div>
    ''', unsafe_allow_html=True)
