import os
import tempfile
import cv2
import numpy as np
import pandas as pd
import streamlit as st

from pathlib import Path

st.set_page_config(page_title='HydroRelease Lab', layout='wide', initial_sidebar_state='expanded')


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

            rows.append({
                '시간(초)': index / fps,
                'R': r,
                'G': g,
                'B': b
            })

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

    out['추정 농도'] = np.where(
        inside,
        np.clip(c, low, high),
        np.nan
    )

    out['검량선 범위'] = np.where(
        inside,
        '범위 내',
        '범위 밖 또는 측정 불가'
    )

    return out


# 농도(mg/L)와 외부 용액 부피(L)로 방출량을 계산한다.
def calculate_release(data, volume_ml, initial_mass=None):

    if not np.isfinite(volume_ml) or volume_ml <= 0:
        raise ValueError('용액 부피는 양수여야 합니다.')

    if initial_mass is not None and (not np.isfinite(initial_mass) or initial_mass <= 0):
        raise ValueError('초기 색소량은 양수여야 합니다.')

    out = data.sort_values('시간(초)').reset_index(drop=True).copy()

    t = out['시간(초)'].to_numpy(dtype=float) / 60

    if not np.isfinite(t).all() or (t < 0).any() or (np.diff(t) <= 0).any():
        raise ValueError('시간은 중복 없이 증가해야 합니다.')

    c = out['추정 농도'].to_numpy(dtype=float)

    mass = np.where(
        np.isfinite(c) & (c >= 0),
        c * volume_ml / 1000,
        np.nan
    )

    out['시간(분)'] = t

    out['누적 방출량(mg)'] = mass

    out['평균 방출 속도(mg/min)'] = (
        np.r_[np.nan, np.diff(mass) / np.diff(t)]
        if len(t)
        else []
    )

    t50 = None

    if initial_mass is not None:

        fraction = mass / initial_mass * 100

        out['누적 방출률(%)'] = fraction

        # 처음 50%를 넘는 구간이 연속 측정되었을 때만 선형 보간한다.
        hits = np.flatnonzero(
            np.isfinite(fraction) & (fraction >= 50)
        )

        if len(hits):

            j = hits[0]

            if j > 0 and np.isfinite(fraction[:j]).all() and fraction[j-1] < 50:

                t50 = (
                    t[j-1]
                    + (50-fraction[j-1])
                    * (t[j]-t[j-1])
                    / (fraction[j]-fraction[j-1])
                )

    return out, t50


# 물질 방출 특성 분석 화면
def show_release(data, unit, mode):

    st.header('물질 방출 특성 분석')

    demo = mode == '테스트용 가상 데이터'

    if demo:

        st.warning(
            '기능 테스트 전용: 가상 농도 수치를 mg/L라고 가정하여 계산합니다. 실제 방출량이 아닙니다.'
        )

    elif unit.strip().lower() != 'mg/l':

        st.warning(
            '방출량 계산에는 기준 농도 단위를 mg/L로 통일해야 합니다. 검량선 입력을 확인하세요.'
        )

        return

    st.caption(
        '외부 용액의 초기 색소량이 0이고, 부피가 일정하며 균일하게 혼합되고, 별도 채취나 손실이 없다는 가정입니다.'
    )

    volume = st.number_input(
        '외부 용액 부피 (mL)',
        min_value=0.1,
        value=100.0,
        step=10.0
    )

    known = st.checkbox(
        '초기 하이드로젤 색소 포함량을 알고 있음',
        value=demo
    )

    initial = (
        st.number_input(
            '초기 색소 포함량 (mg)',
            min_value=0.001,
            value=10.0,
            format='%.3f'
        )
        if known
        else None
    )

    try:

        result, t50 = calculate_release(
            data,
            volume,
            initial
        )

    except ValueError as e:

        st.error(str(e))
        return

    result['방출 분석 구분'] = (
        '가상 테스트' if demo else '실험 추정값'
    )

    result['외부 용액 부피(mL)'] = volume

    result['초기 색소량(mg)'] = initial

    st.session_state['latest_release'] = result.copy()

    mass = result['누적 방출량(mg)']

    rate = result['평균 방출 속도(mg/min)']

    cols = st.columns(3)

    cols[0].metric(
        '마지막 측정 방출량',
        f'{mass.iloc[-1]:.3f} mg'
        if len(mass) and pd.notna(mass.iloc[-1])
        else '측정 불가'
    )

    cols[1].metric(
        '첫 구간 평균 속도',
        f'{rate.iloc[1]:.3f} mg/min'
        if len(rate)>1 and pd.notna(rate.iloc[1])
        else '측정 불가'
    )

    cols[2].metric(
        'T₅₀ (선형 보간)',
        f'{t50:.3f} 분'
        if t50 is not None
        else '산출 불가'
    )

    if len(mass) and pd.notna(mass.iloc[0]) and mass.iloc[0] > 0:

        st.info(
            '첫 프레임에서 이미 색소가 검출되었습니다. 실험 시작 전 배경 농도 또는 촬영 시작 시점을 확인하세요.'
        )

    if rate.lt(0).any():

        st.warning(
            '방출량 감소 구간이 있습니다. 측정 오차 또는 혼합 상태를 확인하세요. 값은 임의로 보정하지 않았습니다.'
        )

    indexed = result.set_index('시간(분)')

    st.subheader('시간별 누적 방출량')

    st.line_chart(indexed['누적 방출량(mg)'])

    st.subheader('구간별 평균 방출 속도')

    st.line_chart(indexed['평균 방출 속도(mg/min)'])

    st.caption(
        '각 속도는 직전 측정 시점부터 현재 시점까지의 평균입니다. 첫 시점 및 결측 구간은 계산하지 않습니다.'
    )

    if initial is not None:

        st.subheader('시간별 누적 방출률')

        st.line_chart(indexed['누적 방출률(%)'])

        if result['누적 방출률(%)'].gt(100).any():

            st.warning(
                '100% 초과 값이 있습니다. 초기 색소량, 부피 및 검량선을 확인하세요.'
            )

        if t50 is None:

            st.info(
                '50% 미도달, 첫 측정부터 50% 이상, 또는 결측으로 T₅₀를 확정할 수 없습니다.'
            )

    else:

        st.info(
            '초기 포함량을 모르면 누적 방출률과 T₅₀는 계산하지 않습니다.'
        )

    st.dataframe(result)

    st.download_button(
        '방출 분석 CSV 다운로드',
        result.to_csv(index=False).encode('utf-8-sig'),
        'release_result.csv',
        'text/csv'
    )

    # ==========================================
    # 신규 기능: 방출 곡선 유사도 분석 연동
    # ==========================================

    st.divider()

    st.subheader('방출 곡선 유사도 분석')

    if demo:

        st.info(
            '테스트용 가상 데이터는 유사도 분석에 사용할 수 없습니다.'
        )

    elif initial is None:

        st.info(
            '초기 색소 포함량을 입력하여 누적 방출률을 계산하면 유사도 분석을 진행할 수 있습니다.'
        )

    else:

        # 유사도 분석에 필요한 시간과 누적 방출률만 추출한다.

        similarity_data = result[
            ['시간(분)', '누적 방출률(%)']
        ].copy()

        values = similarity_data.to_numpy(dtype=float)

        # 전달하기 전에 데이터의 유효성을 검사한다.

        valid = (
            len(similarity_data) >= 2
            and np.isfinite(values).all()
            and similarity_data['시간(분)'].ge(0).all()
            and not similarity_data['시간(분)'].duplicated().any()
            and similarity_data['누적 방출률(%)'].between(0, 100).all()
        )

        if not valid:

            st.warning(
                '유사도 분석에 사용할 수 없는 측정값이 포함되어 있습니다. 방출 분석 결과를 확인하세요.'
            )

        elif 'similarity' not in globals():

            st.warning(
                '유사도 분석 페이지 파일을 찾을 수 없습니다.'
            )

        else:

            st.caption(
                '현재 실험 결과를 유사도 분석 페이지로 전달합니다. 데이터를 다시 입력할 필요가 없습니다.'
            )

            if st.button(
                '📈 이 결과로 유사도 분석하기',
                type='primary',
                use_container_width=True,
                key='go_to_similarity'
            ):

                # 현재 실험 데이터를 페이지 간 공유 공간에 저장한다.

                st.session_state['similarity_transfer'] = {
                    'name': '현재 실험 결과',
                    'data': similarity_data.copy(),
                    'time_unit': '분',
                    'volume_ml': volume,
                    'initial_mass_mg': initial,
                    'source': '영상·농도·방출 분석'
                }

                # 이전 연동 데이터의 이름과 제조 조건이 남지 않도록 초기화한다.

                st.session_state.pop(
                    'imported_experiment_name',
                    None
                )

                st.session_state.pop(
                    'imported_conditions',
                    None
                )

                # 기존 페이지 이동 구조를 활용하여 유사도 분석 페이지로 이동한다.

                st.switch_page(similarity)


# 일정한 확산계수, 초기 균일 농도, 완전 흡수 경계의 구형 확산 해.
def sphere_release(time_s, diameter_mm, diffusivity):

    t = np.asarray(time_s, dtype=float)

    if diameter_mm <= 0 or diffusivity <= 0 or np.any(t < 0):

        raise ValueError(
            '지름과 확산계수는 양수, 시간은 음수가 아니어야 합니다.'
        )

    radius = diameter_mm / 2

    tau = diffusivity * t / radius**2

    result = np.zeros_like(tau)

    # 짧은 시간에서는 급수 수렴 문제를 피하는 단시간 근사식을 사용한다.

    short = (tau > 0) & (tau < 0.001)

    result[short] = (
        6 * np.sqrt(tau[short] / np.pi)
        - 3 * tau[short]
    )

    other = tau >= 0.001

    k = np.arange(1, 201, dtype=float)

    result[other] = (
        1 - 6 / np.pi**2
        * np.sum(
            np.exp(
                -np.pi**2 * tau[other, None] * k**2
            ) / k**2,
            axis=1
        )
    )

    return np.clip(result, 0, 1) * 100


# ==========================================
# 영상·농도·방출 분석 페이지
# ==========================================

def video_page():

    st.session_state.pop('latest_release', None)

    st.title('영상·농도·방출 분석')

    st.caption(
        '5차 개발 버전 | 영상·농도·방출·크기 비교·확산 모형'
    )

    st.info(
        '실제 농도 추정에는 동일한 촬영 조건에서 측정한 기준 용액 데이터가 필요합니다.'
    )

    upload = st.file_uploader(
        '실험 동영상 업로드',
        type=['mp4']
    )

    if upload is not None:

        path = save_video(upload)

        try:

            frame, fps, count = inspect_video(path)

            h, w = frame.shape[:2]

            st.write(
                f'영상 크기: {w} × {h} | FPS: {fps:.2f} | 예상 길이: {count/fps:.1f}초'
            )

            interval = st.number_input(
                '프레임 추출 간격(초)',
                min_value=1,
                value=30
            )

            if w < 2 or h < 2:

                raise ValueError(
                    '영상 크기가 너무 작습니다.'
                )

            x1, x2 = st.slider(
                '분석 영역 가로 범위',
                0,
                w,
                (
                    w//4,
                    max(w//4+1, w*3//4)
                )
            )

            y1, y2 = st.slider(
                '분석 영역 세로 범위',
                0,
                h,
                (
                    h//4,
                    max(h//4+1, h*3//4)
                )
            )

            preview = frame.copy()

            cv2.rectangle(
                preview,
                (x1, y1),
                (x2-1, y2-1),
                (0, 255, 0),
                2
            )

            st.image(
                cv2.cvtColor(
                    preview,
                    cv2.COLOR_BGR2RGB
                ),
                caption='첫 프레임 및 분석 영역'
            )

            if st.button(
                '영상 분석 시작',
                type='primary'
            ):

                if x1 >= x2 or y1 >= y2:

                    st.error(
                        '분석 영역의 가로와 세로 길이는 0보다 커야 합니다.'
                    )

                else:

                    with st.spinner('프레임 분석 중'):

                        result = analyze_video(
                            path,
                            interval,
                            (x1, y1, x2, y2)
                        )

                    st.session_state['rgb_result'] = result

                    st.session_state['rgb_settings'] = (
                        upload.file_id,
                        interval,
                        x1,
                        y1,
                        x2,
                        y2
                    )

            if st.session_state.get('rgb_settings') == (
                upload.file_id,
                interval,
                x1,
                y1,
                x2,
                y2
            ):

                result = st.session_state['rgb_result']

                st.line_chart(
                    result.set_index('시간(초)')
                )

                st.dataframe(result)

                st.download_button(
                    'CSV 다운로드',
                    result.to_csv(index=False).encode('utf-8-sig'),
                    'rgb_result.csv',
                    'text/csv'
                )

        except (ValueError, cv2.error) as e:

            st.error(str(e))

        finally:

            os.unlink(path)

    # 검량선 입력 화면: 예시 데이터는 실제 실험값과 구분한다.

    st.header('검량선 및 색소 농도 분석')

    mode = st.radio(
        '기준 데이터 종류',
        [
            '테스트용 가상 데이터',
            '실제 기준 용액 데이터'
        ]
    )

    channel = st.selectbox(
        '분석 색상 채널',
        ['R', 'G', 'B']
    )

    if mode == '테스트용 가상 데이터':

        st.warning(
            '가상 기준 데이터입니다. 실제 농도 또는 방출률로 해석할 수 없습니다.'
        )

        initial = pd.DataFrame({

            '농도': [
                0., 20., 40., 60., 80., 100.
            ],

            'R': (
                245 * 10 ** (
                    -0.0065 * np.arange(0, 101, 20)
                )
            ),

            'G': (
                245 * 10 ** (
                    -0.0028 * np.arange(0, 101, 20)
                )
            ),

            'B': (
                245 * 10 ** (
                    -0.0004 * np.arange(0, 101, 20)
                )
            )
        })

        unit = '가상 상대 농도 단위'

    else:

        initial = pd.DataFrame({
            '농도': [0., 1., 2.],
            'R': [np.nan]*3,
            'G': [np.nan]*3,
            'B': [np.nan]*3
        })

        unit = st.text_input(
            '농도 단위',
            'mg/L'
        )

    table = st.data_editor(
        initial,
        num_rows='dynamic',
        key='cal_' + mode
    )

    try:

        i0, slope, intercept, r2, a = fit_calibration(
            table,
            channel
        )

        st.write(
            f'A = {slope:.6f} × C + {intercept:.6f}'
        )

        st.metric(
            '결정계수 R²',
            f'{r2:.4f}'
        )

        chart = pd.DataFrame({

            '농도': table['농도'],

            '측정 지표': a,

            '회귀 예측': (
                slope * table['농도'] + intercept
            )

        }).sort_values('농도')

        st.line_chart(
            chart.set_index('농도')
        )

        if r2 < 0.95:

            st.warning(
                '선형 적합도가 낮습니다. 기준 용액과 촬영 조건을 확인하세요. R²만으로 정확성이 보장되지는 않습니다.'
            )

        current = (
            upload is not None
            and 'x1' in locals()
            and 'y1' in locals()
            and st.session_state.get('rgb_settings') == (
                upload.file_id,
                interval,
                x1,
                y1,
                x2,
                y2
            )
        )

        if current:

            out = estimate_concentration(
                st.session_state['rgb_result'],
                channel,
                i0,
                slope,
                intercept,
                float(table['농도'].min()),
                float(table['농도'].max())
            )

            st.subheader(
                f'시간별 추정 농도 ({unit})'
            )

            st.line_chart(
                out.set_index('시간(초)')['추정 농도']
            )

            st.dataframe(out)

            if out['추정 농도'].isna().any():

                st.warning(
                    '검량선 범위 밖의 값은 농도로 변환하지 않았습니다.'
                )

            out['농도 단위'] = unit

            out['기준 데이터 종류'] = mode

            st.download_button(
                '농도 분석 CSV 다운로드',
                out.to_csv(index=False).encode('utf-8-sig'),
                'concentration_result.csv',
                'text/csv'
            )

            show_release(
                out,
                unit,
                mode
            )

        else:

            st.info(
                '먼저 동영상 분석을 실행하면 농도 결과가 표시됩니다.'
            )

    except (
        ValueError,
        TypeError,
        np.linalg.LinAlgError
    ) as e:

        st.info(str(e))


# ==========================================
# 크기별 실험군 비교 페이지
# ==========================================

def compare_page():

    st.title("크기별 실험군 비교")

    st.caption(
        '영상·농도·방출 분석 페이지에서 분석을 완료한 뒤 이 페이지로 이동하세요. 실험군마다 영상 분석, 검량선 및 방출 분석을 완료한 뒤 저장하세요. 같은 이름은 덮어씁니다. 실제 실험과 가상 테스트는 분리하여 비교합니다.'
    )

    if 'release_groups' not in st.session_state:

        st.session_state['release_groups'] = {}

    groups = st.session_state['release_groups']

    group_name = st.text_input(
        '실험군 이름',
        '소형 비드'
    )

    diameter = st.number_input(
        '실험군 평균 지름 (mm)',
        min_value=0.01,
        value=2.0,
        step=0.5
    )

    bead_count = st.number_input(
        '실험군 비드 개수',
        min_value=1,
        value=1,
        step=1
    )

    if st.button(
        '현재 방출 결과를 실험군에 저장'
    ):

        latest = st.session_state.get(
            'latest_release'
        )

        if latest is None or not group_name.strip():

            st.error(
                '유효한 방출 분석 결과와 실험군 이름이 필요합니다.'
            )

        elif not latest[
            '누적 방출량(mg)'
        ].notna().any():

            st.error(
                '유효한 방출량 데이터가 없습니다.'
            )

        else:

            groups[group_name.strip()] = (
                diameter,
                bead_count,
                latest.copy()
            )

            st.success(
                '실험군을 저장했습니다.'
            )

    if groups:

        remove = st.selectbox(
            '삭제할 실험군',
            list(groups)
        )

        if st.button(
            '선택 실험군 삭제'
        ):

            del groups[remove]

            st.rerun()

        selected = st.multiselect(
            '비교할 실험군',
            list(groups),
            default=list(groups)
        )

        if selected:

            kinds = {
                groups[n][2]['방출 분석 구분'].iloc[0]
                for n in selected
            }

            if len(kinds) > 1:

                st.warning(
                    '실험 추정값과 가상 테스트를 함께 비교할 수 없습니다.'
                )

            else:

                st.caption(
                    ' / '.join(kinds)
                )

                tables, summaries = [], []

                for name in selected:

                    d, n, df = groups[name]

                    temp = df.assign(
                        실험군=name,
                        지름_mm=d,
                        비드_개수=n
                    )

                    tables.append(temp)

                    summaries.append({

                        '실험군': name,

                        '지름(mm)': d,

                        '비드 개수': n,

                        '총부피(mm³)': (
                            n * np.pi * d**3 / 6
                        ),

                        '총표면적(mm²)': (
                            n * np.pi * d**2
                        ),

                        '표면적/부피(mm⁻¹)': (
                            6 / d
                        ),

                        '첫 구간 속도(mg/min)': (
                            df['평균 방출 속도(mg/min)'].iloc[1]
                            if len(df)>1
                            else np.nan
                        )
                    })

                combined = pd.concat(
                    tables,
                    ignore_index=True
                )

                st.dataframe(
                    pd.DataFrame(summaries)
                )

                for metric in [

                    '누적 방출량(mg)',

                    '누적 방출률(%)',

                    '평균 방출 속도(mg/min)'

                ]:

                    if metric in combined and combined[metric].notna().any():

                        st.subheader(metric)

                        st.line_chart(
                            combined.pivot(
                                index='시간(분)',
                                columns='실험군',
                                values=metric
                            )
                        )

                st.caption(
                    '측정 시간이 다른 실험군은 실제 측정 시점으로 표시합니다. 공정한 비교를 위해 총 초기 색소량, 용액 부피, 가교 조건 등을 통제하세요.'
                )

                st.download_button(
                    '실험군 비교 CSV 다운로드',
                    combined.to_csv(index=False).encode('utf-8-sig'),
                    'group_comparison.csv',
                    'text/csv'
                )

    else:

        st.info(
            '저장한 실험군이 없습니다. 실험군은 현재 브라우저 세션에만 보관됩니다.'
        )


# ==========================================
# 물리적 구조 및 확산 모형 페이지
# ==========================================

def model_page():

    groups = st.session_state.get(
        "release_groups",
        {}
    )

    st.title(
        '물리적 구조 및 확산 모형'
    )

    st.header(
        '하이드로젤 물리적 구조 분석'
    )

    d = st.number_input(
        '구형 비드 지름 (mm)',
        min_value=0.01,
        value=4.0,
        step=0.5
    )

    n = st.number_input(
        '구형 비드 개수',
        min_value=1,
        value=27,
        step=1
    )

    area = np.pi * d**2

    volume = np.pi * d**3 / 6

    cols = st.columns(3)

    cols[0].metric(
        '비드 1개 표면적',
        f'{area:.3f} mm²'
    )

    cols[1].metric(
        '비드 1개 부피',
        f'{volume:.3f} mm³'
    )

    cols[2].metric(
        '표면적/부피',
        f'{6/d:.3f} mm⁻¹'
    )

    st.write(
        f'총 표면적: {area*n:.3f} mm² | 총 부피: {volume*n:.3f} mm³'
    )

    st.caption(
        '완전한 구형이며 비드가 서로 겹치지 않는다는 가정입니다.'
    )

    st.header(
        '확산 기반 이론적 방출 모형'
    )

    st.info(
        '이상적인 구형 확산 모형입니다. 확산계수 일정, 초기 색소 균일 분포, 표면 농도 0(완전 흡수 경계), 팽윤·분해 없음 등을 가정합니다. 실제 실험에서 이 가정은 성립하지 않을 수 있습니다.'
    )

    D = st.number_input(
        '가정한 유효 확산계수 (mm²/s)',
        min_value=0.00000001,
        value=0.0001,
        format='%.8f',
        step=0.00001
    )

    end_min = st.number_input(
        '모형 분석 시간 (분)',
        min_value=0.1,
        value=30.0,
        step=5.0
    )

    model_sizes = st.multiselect(
        '비교할 모형 지름 (mm)',
        [2., 4., 6.],
        default=[2., 4., 6.]
    )

    times = np.linspace(
        0,
        end_min,
        301
    )

    model = pd.DataFrame({
        '시간(분)': times
    })

    for size in model_sizes:

        model[
            f'{size:g} mm 이론 방출률(%)'
        ] = sphere_release(
            times * 60,
            size,
            D
        )

    if model_sizes:

        st.line_chart(
            model.set_index('시간(분)')
        )

    if groups:

        target = st.selectbox(
            '이론과 비교할 저장 실험군',
            ['선택 안 함'] + list(groups)
        )

        if target != '선택 안 함':

            size, _, df = groups[target]

            if (
                '누적 방출률(%)' not in df
                or not df['누적 방출률(%)'].notna().any()
            ):

                st.warning(
                    '초기 색소량을 알고 있는 실험군만 방출률을 비교할 수 있습니다.'
                )

            else:

                comparison = df[
                    [
                        '시간(분)',
                        '누적 방출률(%)'
                    ]
                ].copy()

                comparison['이론 방출률(%)'] = sphere_release(
                    comparison['시간(분)'].to_numpy() * 60,
                    size,
                    D
                )

                comparison['잔차(%p)'] = (
                    comparison['누적 방출률(%)']
                    - comparison['이론 방출률(%)']
                )

                st.caption(
                    f"{target} | {df['방출 분석 구분'].iloc[0]} | 지름 {size:g} mm"
                )

                st.line_chart(
                    comparison.set_index('시간(분)')[
                        [
                            '누적 방출률(%)',
                            '이론 방출률(%)'
                        ]
                    ]
                )

                st.metric(
                    'RMSE (%p)',
                    f"{np.sqrt(np.nanmean(comparison['잔차(%p)']**2)):.3f}"
                )

                st.dataframe(comparison)

                st.download_button(
                    '이론·실험 비교 CSV 다운로드',
                    comparison.to_csv(index=False).encode('utf-8-sig'),
                    'model_comparison.csv',
                    'text/csv'
                )

    st.caption(
        '확산계수는 직접 설정한 가정값이며 자동 추정된 실험 물성값이 아닙니다. 모형 일치만으로 실제 약물의 방출이나 치료 효과를 입증할 수 없습니다.'
    )


# ==========================================
# 기존 페이지 등록 및 사이드바
# ==========================================

# 기본 페이지 메뉴를 숨기고 모든 페이지에 공통 버튼을 표시한다.

video = st.Page(
    video_page,
    title='영상·농도·방출 분석',
    default=True
)

compare = st.Page(
    compare_page,
    title='크기별 실험군 비교',
    url_path='compare'
)

model = st.Page(
    model_page,
    title='물리적 구조 및 확산 모형',
    url_path='diffusion'
)

menu = [

    (
        '실험 데이터 분석',
        [video, compare]
    ),

    (
        '심화 분석',
        [model]
    )
]

# 기존 pages 파일을 수정하지 않고 연결한다.
# 파일이 없으면 안내한다.

similarity_path = 'pages/01_방출곡선_유사도_분석.py'

if (
    Path(__file__).resolve().parent / similarity_path
).is_file():

    similarity = st.Page(
        similarity_path,
        title='방출곡선 유사도 분석',
        url_path='similarity'
    )

    menu[1][1].append(similarity)


current_page = st.navigation(
    [
        p
        for _, items in menu
        for p in items
    ],
    position='hidden'
)


with st.sidebar:

    st.title('HydroRelease Lab')

    st.caption(
        '하이드로젤 물질 방출 분석 시스템'
    )

    for category, items in menu:

        st.markdown(
            f'**{category}**'
        )

        for p in items:

            active = (
                current_page.url_path == p.url_path
            )

            if st.button(
                p.title,
                key='nav_' + p.url_path,
                type='primary' if active else 'secondary',
                use_container_width=True
            ):

                if not active:

                    st.switch_page(p)

    if not (
        Path(__file__).resolve().parent / similarity_path
    ).is_file():

        st.warning(
            'pages 폴더의 방출곡선 유사도 분석 파일을 확인하세요.'
        )

    st.divider()

    st.caption(
        '실험군 데이터는 현재 세션에 저장됩니다.'
    )


current_page.run()
