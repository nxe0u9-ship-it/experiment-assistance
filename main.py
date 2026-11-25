import pandas as pd
import streamlit as st

# pages 폴더의 Python 파일은 Streamlit이 자동으로 사이드바에 연결한다.
st.set_page_config(
    page_title='HydroRelease Lab',
    layout='wide',
    initial_sidebar_state='expanded'
)
from pathlib import Path

# 기본 페이지 이동 메뉴 아래에 프로젝트 안내를 표시한다.
with st.sidebar:
    st.divider()
    st.caption('HydroRelease Lab')
    st.caption('하이드로젤 물질 방출 분석 시스템')
st.set_page_config(page_title='HydroRelease Lab', layout='wide', initial_sidebar_state='expanded')

# 업로드한 영상을 OpenCV에서 읽을 수 있도록 임시 저장한다.
def save_video(upload):
@@ -178,148 +169,6 @@ def show_release(data, unit, mode):
st.download_button('방출 분석 CSV 다운로드', result.to_csv(index=False).encode('utf-8-sig'), 'release_result.csv', 'text/csv')


st.session_state.pop('latest_release', None)
st.title('HydroRelease Lab')
st.caption('5차 개발 버전 | 영상·농도·방출·크기 비교·확산 모형')
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
        show_release(out, unit, mode)
    else:
        st.info('먼저 동영상 분석을 실행하면 농도 결과가 표시됩니다.')
except (ValueError, TypeError, np.linalg.LinAlgError) as e:
    st.info(str(e))

# 코드 4: 실험군별 방출 결과 저장 및 비교
st.divider()
st.header('크기별 실험군 비교')
st.caption('실험군마다 영상 분석, 검량선 및 방출 분석을 완료한 뒤 저장하세요. 같은 이름은 덮어씁니다. 실제 실험과 가상 테스트는 분리하여 비교합니다.')
if 'release_groups' not in st.session_state:
    st.session_state['release_groups'] = {}
groups = st.session_state['release_groups']
group_name = st.text_input('실험군 이름', '소형 비드')
diameter = st.number_input('실험군 평균 지름 (mm)', min_value=0.01, value=2.0, step=0.5)
bead_count = st.number_input('실험군 비드 개수', min_value=1, value=1, step=1)
if st.button('현재 방출 결과를 실험군에 저장'):
    latest = st.session_state.get('latest_release')
    if latest is None or not group_name.strip():
        st.error('유효한 방출 분석 결과와 실험군 이름이 필요합니다.')
    elif not latest['누적 방출량(mg)'].notna().any():
        st.error('유효한 방출량 데이터가 없습니다.')
    else:
        groups[group_name.strip()] = (diameter, bead_count, latest.copy())
        st.success('실험군을 저장했습니다.')
if groups:
    remove = st.selectbox('삭제할 실험군', list(groups))
    if st.button('선택 실험군 삭제'):
        del groups[remove]
        st.rerun()
    selected = st.multiselect('비교할 실험군', list(groups), default=list(groups))
    if selected:
        kinds = {groups[n][2]['방출 분석 구분'].iloc[0] for n in selected}
        if len(kinds) > 1:
            st.warning('실험 추정값과 가상 테스트를 함께 비교할 수 없습니다.')
        else:
            st.caption(' / '.join(kinds))
            tables, summaries = [], []
            for name in selected:
                d, n, df = groups[name]
                temp = df.assign(실험군=name, 지름_mm=d, 비드_개수=n)
                tables.append(temp)
                summaries.append({'실험군':name, '지름(mm)':d, '비드 개수':n,
                    '총부피(mm³)':n*np.pi*d**3/6, '총표면적(mm²)':n*np.pi*d**2,
                    '표면적/부피(mm⁻¹)':6/d,
                    '첫 구간 속도(mg/min)':df['평균 방출 속도(mg/min)'].iloc[1] if len(df)>1 else np.nan})
            combined = pd.concat(tables, ignore_index=True)
            st.dataframe(pd.DataFrame(summaries))
            for metric in ['누적 방출량(mg)', '누적 방출률(%)', '평균 방출 속도(mg/min)']:
                if metric in combined and combined[metric].notna().any():
                    st.subheader(metric)
                    st.line_chart(combined.pivot(index='시간(분)', columns='실험군', values=metric))
            st.caption('측정 시간이 다른 실험군은 실제 측정 시점으로 표시합니다. 공정한 비교를 위해 총 초기 색소량, 용액 부피, 가교 조건 등을 통제하세요.')
            st.download_button('실험군 비교 CSV 다운로드', combined.to_csv(index=False).encode('utf-8-sig'), 'group_comparison.csv','text/csv')
else:
    st.info('저장한 실험군이 없습니다. 실험군은 현재 브라우저 세션에만 보관됩니다.')

# 코드 5: 구형 비드 구조 및 이상적인 확산 모형
st.divider()
st.header('하이드로젤 물리적 구조 분석')
d = st.number_input('구형 비드 지름 (mm)', min_value=0.01, value=4.0, step=0.5)
n = st.number_input('구형 비드 개수', min_value=1, value=27, step=1)
area = np.pi*d**2
volume = np.pi*d**3/6
cols = st.columns(3)
cols[0].metric('비드 1개 표면적', f'{area:.3f} mm²')
cols[1].metric('비드 1개 부피', f'{volume:.3f} mm³')
cols[2].metric('표면적/부피', f'{6/d:.3f} mm⁻¹')
st.write(f'총 표면적: {area*n:.3f} mm² | 총 부피: {volume*n:.3f} mm³')
st.caption('완전한 구형이며 비드가 서로 겹치지 않는다는 가정입니다.')

# 일정한 확산계수, 초기 균일 농도, 완전 흡수 경계의 구형 확산 해.
def sphere_release(time_s, diameter_mm, diffusivity):
t = np.asarray(time_s, dtype=float)
@@ -336,30 +185,210 @@ def sphere_release(time_s, diameter_mm, diffusivity):
result[other] = 1-6/np.pi**2*np.sum(np.exp(-np.pi**2*tau[other,None]*k**2)/k**2, axis=1)
return np.clip(result, 0, 1)*100

st.header('확산 기반 이론적 방출 모형')
st.info('이상적인 구형 확산 모형입니다. 확산계수 일정, 초기 색소 균일 분포, 표면 농도 0(완전 흡수 경계), 팽윤·분해 없음 등을 가정합니다. 실제 실험에서 이 가정은 성립하지 않을 수 있습니다.')
D = st.number_input('가정한 유효 확산계수 (mm²/s)', min_value=0.00000001, value=0.0001, format='%.8f', step=0.00001)
end_min = st.number_input('모형 분석 시간 (분)', min_value=0.1, value=30.0, step=5.0)
model_sizes = st.multiselect('비교할 모형 지름 (mm)', [2., 4., 6.], default=[2.,4.,6.])
times = np.linspace(0, end_min, 301)
model = pd.DataFrame({'시간(분)':times})
for size in model_sizes:
    model[f'{size:g} mm 이론 방출률(%)'] = sphere_release(times*60, size, D)
if model_sizes:
    st.line_chart(model.set_index('시간(분)'))
if groups:
    target = st.selectbox('이론과 비교할 저장 실험군', ['선택 안 함'] + list(groups))
    if target != '선택 안 함':
        size, _, df = groups[target]
        if '누적 방출률(%)' not in df or not df['누적 방출률(%)'].notna().any():
            st.warning('초기 색소량을 알고 있는 실험군만 방출률을 비교할 수 있습니다.')


def video_page():
    st.session_state.pop('latest_release', None)
    st.title('영상·농도·방출 분석')
    st.caption('5차 개발 버전 | 영상·농도·방출·크기 비교·확산 모형')
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
            show_release(out, unit, mode)
else:
            comparison = df[['시간(분)', '누적 방출률(%)']].copy()
            comparison['이론 방출률(%)'] = sphere_release(comparison['시간(분)'].to_numpy()*60, size, D)
            comparison['잔차(%p)'] = comparison['누적 방출률(%)']-comparison['이론 방출률(%)']
            st.caption(f"{target} | {df['방출 분석 구분'].iloc[0]} | 지름 {size:g} mm")
            st.line_chart(comparison.set_index('시간(분)')[['누적 방출률(%)','이론 방출률(%)']])
            st.metric('RMSE (%p)', f"{np.sqrt(np.nanmean(comparison['잔차(%p)']**2)):.3f}")
            st.dataframe(comparison)
            st.download_button('이론·실험 비교 CSV 다운로드', comparison.to_csv(index=False).encode('utf-8-sig'), 'model_comparison.csv','text/csv')
st.caption('확산계수는 직접 설정한 가정값이며 자동 추정된 실험 물성값이 아닙니다. 모형 일치만으로 실제 약물의 방출이나 치료 효과를 입증할 수 없습니다.')
            st.info('먼저 동영상 분석을 실행하면 농도 결과가 표시됩니다.')
    except (ValueError, TypeError, np.linalg.LinAlgError) as e:
        st.info(str(e))



def compare_page():
    st.title("크기별 실험군 비교")
    # 코드 4: 실험군별 방출 결과 저장 및 비교
    st.caption('영상·농도·방출 분석 페이지에서 분석을 완료한 뒤 이 페이지로 이동하세요. 실험군마다 영상 분석, 검량선 및 방출 분석을 완료한 뒤 저장하세요. 같은 이름은 덮어씁니다. 실제 실험과 가상 테스트는 분리하여 비교합니다.')
    if 'release_groups' not in st.session_state:
        st.session_state['release_groups'] = {}
    groups = st.session_state['release_groups']
    group_name = st.text_input('실험군 이름', '소형 비드')
    diameter = st.number_input('실험군 평균 지름 (mm)', min_value=0.01, value=2.0, step=0.5)
    bead_count = st.number_input('실험군 비드 개수', min_value=1, value=1, step=1)
    if st.button('현재 방출 결과를 실험군에 저장'):
        latest = st.session_state.get('latest_release')
        if latest is None or not group_name.strip():
            st.error('유효한 방출 분석 결과와 실험군 이름이 필요합니다.')
        elif not latest['누적 방출량(mg)'].notna().any():
            st.error('유효한 방출량 데이터가 없습니다.')
        else:
            groups[group_name.strip()] = (diameter, bead_count, latest.copy())
            st.success('실험군을 저장했습니다.')
    if groups:
        remove = st.selectbox('삭제할 실험군', list(groups))
        if st.button('선택 실험군 삭제'):
            del groups[remove]
            st.rerun()
        selected = st.multiselect('비교할 실험군', list(groups), default=list(groups))
        if selected:
            kinds = {groups[n][2]['방출 분석 구분'].iloc[0] for n in selected}
            if len(kinds) > 1:
                st.warning('실험 추정값과 가상 테스트를 함께 비교할 수 없습니다.')
            else:
                st.caption(' / '.join(kinds))
                tables, summaries = [], []
                for name in selected:
                    d, n, df = groups[name]
                    temp = df.assign(실험군=name, 지름_mm=d, 비드_개수=n)
                    tables.append(temp)
                    summaries.append({'실험군':name, '지름(mm)':d, '비드 개수':n,
                        '총부피(mm³)':n*np.pi*d**3/6, '총표면적(mm²)':n*np.pi*d**2,
                        '표면적/부피(mm⁻¹)':6/d,
                        '첫 구간 속도(mg/min)':df['평균 방출 속도(mg/min)'].iloc[1] if len(df)>1 else np.nan})
                combined = pd.concat(tables, ignore_index=True)
                st.dataframe(pd.DataFrame(summaries))
                for metric in ['누적 방출량(mg)', '누적 방출률(%)', '평균 방출 속도(mg/min)']:
                    if metric in combined and combined[metric].notna().any():
                        st.subheader(metric)
                        st.line_chart(combined.pivot(index='시간(분)', columns='실험군', values=metric))
                st.caption('측정 시간이 다른 실험군은 실제 측정 시점으로 표시합니다. 공정한 비교를 위해 총 초기 색소량, 용액 부피, 가교 조건 등을 통제하세요.')
                st.download_button('실험군 비교 CSV 다운로드', combined.to_csv(index=False).encode('utf-8-sig'), 'group_comparison.csv','text/csv')
    else:
        st.info('저장한 실험군이 없습니다. 실험군은 현재 브라우저 세션에만 보관됩니다.')



def model_page():
    groups = st.session_state.get("release_groups", {})
    # 코드 5: 구형 비드 구조 및 이상적인 확산 모형
    st.title('물리적 구조 및 확산 모형')
    st.header('하이드로젤 물리적 구조 분석')
    d = st.number_input('구형 비드 지름 (mm)', min_value=0.01, value=4.0, step=0.5)
    n = st.number_input('구형 비드 개수', min_value=1, value=27, step=1)
    area = np.pi*d**2
    volume = np.pi*d**3/6
    cols = st.columns(3)
    cols[0].metric('비드 1개 표면적', f'{area:.3f} mm²')
    cols[1].metric('비드 1개 부피', f'{volume:.3f} mm³')
    cols[2].metric('표면적/부피', f'{6/d:.3f} mm⁻¹')
    st.write(f'총 표면적: {area*n:.3f} mm² | 총 부피: {volume*n:.3f} mm³')
    st.caption('완전한 구형이며 비드가 서로 겹치지 않는다는 가정입니다.')

    st.header('확산 기반 이론적 방출 모형')
    st.info('이상적인 구형 확산 모형입니다. 확산계수 일정, 초기 색소 균일 분포, 표면 농도 0(완전 흡수 경계), 팽윤·분해 없음 등을 가정합니다. 실제 실험에서 이 가정은 성립하지 않을 수 있습니다.')
    D = st.number_input('가정한 유효 확산계수 (mm²/s)', min_value=0.00000001, value=0.0001, format='%.8f', step=0.00001)
    end_min = st.number_input('모형 분석 시간 (분)', min_value=0.1, value=30.0, step=5.0)
    model_sizes = st.multiselect('비교할 모형 지름 (mm)', [2., 4., 6.], default=[2.,4.,6.])
    times = np.linspace(0, end_min, 301)
    model = pd.DataFrame({'시간(분)':times})
    for size in model_sizes:
        model[f'{size:g} mm 이론 방출률(%)'] = sphere_release(times*60, size, D)
    if model_sizes:
        st.line_chart(model.set_index('시간(분)'))
    if groups:
        target = st.selectbox('이론과 비교할 저장 실험군', ['선택 안 함'] + list(groups))
        if target != '선택 안 함':
            size, _, df = groups[target]
            if '누적 방출률(%)' not in df or not df['누적 방출률(%)'].notna().any():
                st.warning('초기 색소량을 알고 있는 실험군만 방출률을 비교할 수 있습니다.')
            else:
                comparison = df[['시간(분)', '누적 방출률(%)']].copy()
                comparison['이론 방출률(%)'] = sphere_release(comparison['시간(분)'].to_numpy()*60, size, D)
                comparison['잔차(%p)'] = comparison['누적 방출률(%)']-comparison['이론 방출률(%)']
                st.caption(f"{target} | {df['방출 분석 구분'].iloc[0]} | 지름 {size:g} mm")
                st.line_chart(comparison.set_index('시간(분)')[['누적 방출률(%)','이론 방출률(%)']])
                st.metric('RMSE (%p)', f"{np.sqrt(np.nanmean(comparison['잔차(%p)']**2)):.3f}")
                st.dataframe(comparison)
                st.download_button('이론·실험 비교 CSV 다운로드', comparison.to_csv(index=False).encode('utf-8-sig'), 'model_comparison.csv','text/csv')
    st.caption('확산계수는 직접 설정한 가정값이며 자동 추정된 실험 물성값이 아닙니다. 모형 일치만으로 실제 약물의 방출이나 치료 효과를 입증할 수 없습니다.')


# 기본 페이지 메뉴를 숨기고 모든 페이지에 공통 버튼을 표시한다.
video = st.Page(video_page, title='영상·농도·방출 분석', default=True)
compare = st.Page(compare_page, title='크기별 실험군 비교', url_path='compare')
model = st.Page(model_page, title='물리적 구조 및 확산 모형', url_path='diffusion')
menu = [('실험 데이터 분석', [video, compare]), ('심화 분석', [model])]
# 기존 pages 파일을 수정하지 않고 연결한다. 파일이 없으면 안내한다.
similarity_path = 'pages/01_방출곡선_유사도_분석.py'
if (Path(__file__).resolve().parent / similarity_path).is_file():
    similarity = st.Page(similarity_path, title='방출곡선 유사도 분석', url_path='similarity')
    menu[1][1].append(similarity)

current_page = st.navigation([p for _, items in menu for p in items], position='hidden')
with st.sidebar:
    st.title('HydroRelease Lab')
    st.caption('하이드로젤 물질 방출 분석 시스템')
    for category, items in menu:
        st.markdown(f'**{category}**')
        for p in items:
            active = current_page.url_path == p.url_path
            if st.button(p.title, key='nav_' + p.url_path, type='primary' if active else 'secondary', use_container_width=True):
                if not active:
                    st.switch_page(p)
    if not (Path(__file__).resolve().parent / similarity_path).is_file():
        st.warning('pages 폴더의 방출곡선 유사도 분석 파일을 확인하세요.')
    st.divider()
    st.caption('실험군 데이터는 현재 세션에 저장됩니다.')
current_page.run()
