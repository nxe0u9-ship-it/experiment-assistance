import os
import tempfile
import cv2
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title='HydroRelease Lab', layout='wide')

# 업로드한 영상을 OpenCV에서 읽을 수 있도록 임시 저장한다.
def save_video(upload):
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
        f.write(upload.getbuffer())
        return f.name

# 첫 프레임과 영상 정보를 읽는다.
def inspect_video(path):
    cap = cv2.VideoCapture(path)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        ok, frame = cap.read()
        if not ok or not np.isfinite(fps) or fps <= 0:
            raise ValueError('영상을 읽을 수 없거나 FPS 정보가 올바르지 않습니다.')
        return frame, fps, count
    finally:
        cap.release()

# 일정한 간격의 프레임에서 관심 영역의 평균 RGB를 계산한다.
def analyze_video(path, interval, roi):
    cap = cv2.VideoCapture(path)
    rows = []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not np.isfinite(fps) or fps <= 0:
            raise ValueError('FPS 정보 오류')
        x1, y1, x2, y2 = roi
        step = max(1, round(fps * interval))
        index = 0
        while True:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            if not ok:
                break
            region = frame[y1:y2, x1:x2]
            if region.size == 0:
                raise ValueError('분석 영역이 비어 있습니다.')
            rgb = cv2.cvtColor(region, cv2.COLOR_BGR2RGB)
            r, g, b = np.mean(rgb, axis=(0, 1))
            rows.append({'시간(초)': index / fps, 'R': r, 'G': g, 'B': b})
            index += step
        if not rows:
            raise ValueError('추출된 프레임이 없습니다.')
        return pd.DataFrame(rows)
    finally:
        cap.release()

st.title('HydroRelease Lab')
st.caption('1차 개발 버전 | 동영상 프레임 추출 및 RGB 분석')
st.info('현재 결과는 RGB 색상값입니다. 검량선이 없으므로 실제 농도나 방출률로 해석하지 않습니다.')
upload = st.file_uploader('실험 동영상 업로드', type=['mp4'])
if upload is not None:
    path = save_video(upload)
    try:
        frame, fps, count = inspect_video(path)
        h, w = frame.shape[:2]
        st.write(f'영상 크기: {w} × {h} | FPS: {fps:.2f} | 예상 길이: {count/fps:.1f}초')
        interval = st.number_input('프레임 추출 간격(초)', min_value=1, value=30)
        if w < 2 or h < 2:
            raise ValueError('영상 크기가 너무 작습니다.')
        x1, x2 = st.slider('분석 영역 가로 범위', 0, w, (w//4, max(w//4+1, w*3//4)))
        y1, y2 = st.slider('분석 영역 세로 범위', 0, h, (h//4, max(h//4+1, h*3//4)))
        preview = frame.copy()
        cv2.rectangle(preview, (x1,y1), (x2-1,y2-1), (0,255,0), 2)
        st.image(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB), caption='첫 프레임 및 분석 영역')
        if st.button('영상 분석 시작', type='primary'):
            if x1 >= x2 or y1 >= y2:
                st.error('분석 영역의 가로와 세로 길이는 0보다 커야 합니다.')
            else:
                with st.spinner('프레임 분석 중'):
                    result = analyze_video(path, interval, (x1,y1,x2,y2))
                st.session_state['rgb_result'] = result
                st.session_state['rgb_settings'] = (upload.file_id, interval, x1,y1,x2,y2)
        if st.session_state.get('rgb_settings') == (upload.file_id, interval, x1,y1,x2,y2):
            result = st.session_state['rgb_result']
            st.line_chart(result.set_index('시간(초)'))
            st.dataframe(result)
            st.download_button('CSV 다운로드', result.to_csv(index=False).encode('utf-8-sig'), 'rgb_result.csv', 'text/csv')
    except (ValueError, cv2.error) as e:
        st.error(str(e))
    finally:
        os.unlink(path)
