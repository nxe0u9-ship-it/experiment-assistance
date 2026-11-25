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

# 기준 용액의 색상 강도로 상대 흡광 지표를 계산한다.
def fit_calibration(table, channel):
    c = table['농도'].to_numpy(dtype=float)
    intensity = table[channel].to_numpy(dtype=float)
    if len(c) < 3 or not np.isfinite(c).all() or not np.isfinite(intensity).all():
        raise ValueError('유효한 기준 용액 데이터를 3개 이상 입력하세요.')
    if (c < 0).any() or len(np.unique(c)) != len(c):
        raise ValueError('농도는 음수가 아니어야 하며 중복될 수 없습니다.')
    if (intensity <= 0).any() or (intensity > 255).any() or sum(c == 0) != 1:
        raise ValueError('0 농도 기준 용액 1개와 0 초과 255 이하의 색상값이 필요합니다.')
    i0 = intensity[c == 0][0]
    a = np.log10(i0 / intensity)
    slope, intercept = np.polyfit(c, a, 1)
    predicted = slope * c + intercept
    total = np.sum((a - a.mean()) ** 2)
    if slope <= 0 or total <= 1e-12:
        raise ValueError('농도 증가에 따른 흡광 지표 증가가 확인되지 않습니다. 채널과 기준값을 확인하세요.')
    r2 = 1 - np.sum((a - predicted) ** 2) / total
    return i0, slope, intercept, r2, a

# 영상 RGB 결과를 검량선의 유효 범위 안에서만 농도로 변환한다.
def estimate_concentration(result, channel, i0, slope, intercept, low, high):
    out = result.copy()
    values = out[channel].to_numpy(dtype=float)
    a = np.full(len(values), np.nan)
    valid = np.isfinite(values) & (values > 0) & (values <= 255)
    a[valid] = np.log10(i0 / values[valid])
    c = (a - intercept) / slope
    inside = np.isfinite(c) & (c >= low - 1e-9) & (c <= high + 1e-9)
    out['상대 흡광 지표'] = a
    out['추정 농도'] = np.where(inside, np.clip(c, low, high), np.nan)
    out['검량선 범위'] = np.where(inside, '범위 내', '범위 밖 또는 측정 불가')
    return out

st.title('HydroRelease Lab')
st.caption('2차 개발 버전 | 영상 분석 및 검량선 기반 농도 추정')
st.info('실제 농도 추정에는 동일한 촬영 조건에서 측정한 기준 용액 데이터가 필요합니다.')
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

# 검량선 입력 화면: 예시 데이터는 실제 실험값과 구분한다.
st.header('검량선 및 색소 농도 분석')
mode = st.radio('기준 데이터 종류', ['테스트용 가상 데이터', '실제 기준 용액 데이터'])
channel = st.selectbox('분석 색상 채널', ['R', 'G', 'B'])
if mode == '테스트용 가상 데이터':
    st.warning('가상 기준 데이터입니다. 실제 농도 또는 방출률로 해석할 수 없습니다.')
    initial = pd.DataFrame({'농도': [0., 20., 40., 60., 80., 100.],
        'R': 245 * 10 ** (-0.0065 * np.arange(0,101,20)),
        'G': 245 * 10 ** (-0.0028 * np.arange(0,101,20)),
        'B': 245 * 10 ** (-0.0004 * np.arange(0,101,20))})
    unit = '가상 상대 농도 단위'
else:
    initial = pd.DataFrame({'농도': [0., 1., 2.], 'R': [np.nan]*3, 'G': [np.nan]*3, 'B': [np.nan]*3})
    unit = st.text_input('농도 단위', 'mg/L')
table = st.data_editor(initial, num_rows='dynamic', key='cal_' + mode)
try:
    i0, slope, intercept, r2, a = fit_calibration(table, channel)
    st.write(f'A = {slope:.6f} × C + {intercept:.6f}')
    st.metric('결정계수 R²', f'{r2:.4f}')
    chart = pd.DataFrame({'농도': table['농도'], '측정 지표': a, '회귀 예측': slope * table['농도'] + intercept}).sort_values('농도')
    st.line_chart(chart.set_index('농도'))
    if r2 < 0.95:
        st.warning('선형 적합도가 낮습니다. 기준 용액과 촬영 조건을 확인하세요. R²만으로 정확성이 보장되지는 않습니다.')
    current = upload is not None and 'x1' in locals() and 'y1' in locals() and st.session_state.get('rgb_settings') == (upload.file_id, interval, x1,y1,x2,y2)
    if current:
        out = estimate_concentration(st.session_state['rgb_result'], channel, i0, slope, intercept, float(table['농도'].min()), float(table['농도'].max()))
        st.subheader(f'시간별 추정 농도 ({unit})')
        st.line_chart(out.set_index('시간(초)')['추정 농도'])
        st.dataframe(out)
        if out['추정 농도'].isna().any():
            st.warning('검량선 범위 밖의 값은 농도로 변환하지 않았습니다.')
        out['농도 단위'] = unit
        out['기준 데이터 종류'] = mode
        st.download_button('농도 분석 CSV 다운로드', out.to_csv(index=False).encode('utf-8-sig'), 'concentration_result.csv', 'text/csv')
    else:
        st.info('먼저 동영상 분석을 실행하면 농도 결과가 표시됩니다.')
except (ValueError, TypeError, np.linalg.LinAlgError) as e:
    st.info(str(e))
