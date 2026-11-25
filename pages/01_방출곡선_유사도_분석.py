import streamlit as st
import pandas as pd
import numpy as np

# ==========================================
# 1. 페이지 기본 설정
# ==========================================

st.set_page_config(
    page_title="방출 곡선 유사도 분석",
    page_icon="📈",
    layout="wide"
)

st.title("📈 방출 곡선 유사도 분석")

st.caption(
    "HydroRelease Lab | Release Profile Similarity Analysis"
)

st.info(
    "목표 방출 곡선과 실제 실험 결과를 비교하여 "
    "목표 방출 특성에 가장 가까운 실험군을 탐색합니다."
)

# ==========================================
# 2. 데이터 검증 함수
# ==========================================

def validate_data(df):

    df = df.dropna(how="all").copy()

    if len(df) < 2:
        raise ValueError(
            "데이터를 2개 이상 입력해 주세요."
        )

    df = df.apply(pd.to_numeric, errors="coerce")

    if not np.isfinite(df.to_numpy()).all():
        raise ValueError(
            "모든 데이터에 유효한 숫자를 입력해 주세요."
        )

    if (df["시간"] < 0).any():
        raise ValueError(
            "시간은 음수가 될 수 없습니다."
        )

    if df["시간"].duplicated().any():
        raise ValueError(
            "동일한 시간의 데이터가 중복되어 있습니다."
        )

    if (
        (df["누적 방출률(%)"] < 0)
        | (df["누적 방출률(%)"] > 100)
    ).any():

        raise ValueError(
            "누적 방출률은 0~100% 사이여야 합니다."
        )

    return df.sort_values("시간").reset_index(drop=True)


# ==========================================
# 3. 목표 방출 곡선 설정
# ==========================================

st.header("1. 목표 방출 곡선 설정")

unit = st.selectbox(
    "시간 단위",
    ["초", "분", "시간", "일"],
    index=1
)

st.write(
    "연구 목적에 맞는 시간별 목표 누적 방출률을 "
    "입력해 주세요."
)

target_default = pd.DataFrame({
    "시간": [0., 10., 20., 30., 40., 50.],
    "누적 방출률(%)": [
        0., 20., 40., 60., 80., 100.
    ]
})

target_data = st.data_editor(
    target_default,
    num_rows="dynamic",
    hide_index=True,
    use_container_width=True,
    key="target_curve",
    column_config={
        "시간": st.column_config.NumberColumn(
            f"시간({unit})",
            min_value=0.0
        ),
        "누적 방출률(%)":
            st.column_config.NumberColumn(
                min_value=0.0,
                max_value=100.0
            )
    }
)

try:

    target = validate_data(target_data)

    if (
        np.diff(target["누적 방출률(%)"]) < 0
    ).any():

        raise ValueError(
            "목표 누적 방출률은 감소할 수 없습니다."
        )

    st.line_chart(
        target.set_index("시간"),
        y_label="누적 방출률(%)",
        x_label=f"시간({unit})"
    )

except ValueError as e:

    st.error(str(e))
    st.stop()


# ==========================================
# 4. 실험군 추가 및 데이터 입력
# ==========================================

st.divider()

st.header("2. 실제 실험 데이터 입력")

data_mode = st.radio(
    "데이터 입력 방식",
    ["테스트용 가상 데이터", "실제 실험 데이터"],
    horizontal=True
)

if data_mode == "테스트용 가상 데이터":

    st.warning(
        "현재 데이터는 기능 검증을 위한 가상 데이터입니다."
    )

experiment_count = st.number_input(
    "비교할 실험군 수",
    min_value=1,
    max_value=10,
    value=3,
    step=1
)

experiments = []

example_values = [
    [0., 45., 70., 85., 95., 100.],
    [0., 18., 38., 63., 78., 98.],
    [0., 5., 15., 28., 45., 60.]
]

for i in range(experiment_count):

    with st.expander(
        f"실험군 {i + 1}",
        expanded=(i == 0)
    ):

        name = st.text_input(
            "실험군 이름",
            value=f"실험군 {i + 1}",
            key=f"group_name_{i}"
        )

        conditions = st.text_area(
            "하이드로젤 제조 조건",
            placeholder=(
                "알지네이트 농도, 가교제 농도, "
                "가교 시간, 비드 크기 등을 기록하세요."
            ),
            key=f"conditions_{i}"
        )

        if data_mode == "테스트용 가상 데이터":

            default = pd.DataFrame({
                "시간": [
                    0., 10., 20., 30., 40., 50.
                ],
                "누적 방출률(%)":
                    example_values[i % 3]
            })

        else:

            default = pd.DataFrame({
                "시간": [0., np.nan],
                "누적 방출률(%)": [0., np.nan]
            })

        edited = st.data_editor(
            default,
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            key=f"experiment_{data_mode}_{i}",
            column_config={
                "시간":
                    st.column_config.NumberColumn(
                        f"시간({unit})",
                        min_value=0.0
                    ),
                "누적 방출률(%)":
                    st.column_config.NumberColumn(
                        min_value=0.0,
                        max_value=100.0
                    )
            }
        )

        try:

            valid = validate_data(edited)

            if (
                np.diff(valid["누적 방출률(%)"]) < 0
            ).any():

                st.warning(
                    "누적 방출률이 감소하는 구간이 있습니다. "
                    "측정 오차 또는 계산 오류를 확인하세요."
                )

            experiments.append({
                "id": i,
                "name": name.strip() or f"실험군 {i+1}",
                "conditions": conditions,
                "data": valid
            })

        except ValueError as e:

            st.warning(str(e))


# ==========================================
# 5. 유사도 분석
# ==========================================

st.divider()

st.header("3. 방출 곡선 유사도 분석")

if len(experiments) != experiment_count:

    st.warning(
        "모든 실험군에 유효한 데이터를 입력해 주세요."
    )

    st.stop()

with st.expander("유사도 계산 원리"):

    st.latex(
        r"RMSE="
        r"\sqrt{\frac{1}{n}"
        r"\sum_{i=1}^{n}(T_i-E_i)^2}"
    )

    st.latex(
        r"\text{Similarity Score}=100-RMSE"
    )

    st.write(
        "RMSE가 작을수록 목표 방출 곡선과 "
        "실험 방출 곡선의 차이가 작습니다."
    )

    st.caption(
        "유사도 점수는 본 프로그램에서 정의한 "
        "비교 지표이며 공인된 약학적 평가 지표가 "
        "아닙니다."
    )

# 모든 실험군에서 공통으로 비교할 수 있는 시간 범위

start_time = max(
    [target["시간"].min()]
    + [
        e["data"]["시간"].min()
        for e in experiments
    ]
)

end_time = min(
    [target["시간"].max()]
    + [
        e["data"]["시간"].max()
        for e in experiments
    ]
)

if end_time <= start_time:

    st.error(
        "목표 곡선과 실험군의 공통 측정 시간 "
        "범위가 부족합니다."
    )

    st.stop()

# 공통 범위를 일정한 간격으로 나눈다.
# 측정 범위 밖의 값은 추정하지 않는다.

common_time = np.linspace(
    start_time,
    end_time,
    201
)

# 선형 보간을 통해 목표 방출률을 계산한다.

target_y = np.interp(
    common_time,
    target["시간"],
    target["누적 방출률(%)"]
)

chart_data = pd.DataFrame({
    "시간": common_time,
    "목표 방출 곡선": target_y
})

results = []

for experiment in experiments:

    data = experiment["data"]

    # 실제 측정 시간과 목표 시간이 다를 경우
    # 선형 보간을 적용한다.

    actual_y = np.interp(
        common_time,
        data["시간"],
        data["누적 방출률(%)"]
    )

    # 평균 제곱근 오차 계산

    rmse = np.sqrt(
        np.mean((target_y - actual_y) ** 2)
    )

    similarity = 100 - rmse

    label = (
        f'{experiment["name"]} '
        f'({experiment["id"] + 1})'
    )

    chart_data[label] = actual_y

    results.append({
        "실험군": label,
        "제조 조건": experiment["conditions"],
        "RMSE": float(rmse),
        "유사도 점수": float(similarity)
    })


# ==========================================
# 6. 방출 곡선 시각화
# ==========================================

st.subheader("방출 곡선 비교")

st.caption(
    f"공통 분석 범위: "
    f"{start_time:g}~{end_time:g}{unit}"
)

if (
    start_time > target["시간"].min()
    or end_time < target["시간"].max()
):

    st.warning(
        "목표 시간 범위 전체를 비교할 수 없어 "
        "공통 구간만 분석했습니다."
    )

st.line_chart(
    chart_data.set_index("시간"),
    x_label=f"시간({unit})",
    y_label="누적 방출률(%)"
)

# ==========================================
# 7. 유사도 순위
# ==========================================

st.divider()

st.header("4. 유사도 분석 결과")

ranking = pd.DataFrame(results)

ranking = ranking.sort_values(
    "RMSE",
    ascending=True
).reset_index(drop=True)

ranking.insert(
    0,
    "순위",
    ranking["RMSE"].rank(
        method="min"
    ).astype(int)
)

for _, row in ranking.iterrows():

    left, right = st.columns([3, 1])

    with left:

        st.write(
            f'**{row["순위"]}위 · '
            f'{row["실험군"]}**'
        )

        st.progress(
            float(
                np.clip(
                    row["유사도 점수"] / 100,
                    0,
                    1
                )
            )
        )

    with right:

        st.metric(
            "유사도",
            f'{row["유사도 점수"]:.2f}점'
        )

    st.caption(
        f'RMSE: {row["RMSE"]:.3f}%p'
    )

best = ranking.iloc[0]

st.success(
    f'비교한 실험군 중 목표 방출 곡선에 '
    f'가장 가까운 조건: {best["실험군"]}'
)

if best["제조 조건"]:

    st.write(
        "**해당 실험군의 제조 조건**"
    )

    st.write(best["제조 조건"])

st.caption(
    "본 결과는 입력된 실험 데이터의 비교 결과이며, "
    "실험하지 않은 제조 조건의 성능이나 "
    "실제 약물의 치료 효과를 예측하지 않습니다."
)

# ==========================================
# 8. 결과 저장
# ==========================================

st.divider()

st.header("5. 분석 결과 저장")

st.dataframe(
    ranking.round(3),
    hide_index=True,
    use_container_width=True
)

st.download_button(
    label="📥 유사도 분석 결과 CSV 다운로드",
    data=ranking.to_csv(
        index=False
    ).encode("utf-8-sig"),
    file_name="release_similarity.csv",
    mime="text/csv"
)

st.download_button(
    label="📥 방출 곡선 데이터 CSV 다운로드",
    data=chart_data.to_csv(
        index=False
    ).encode("utf-8-sig"),
    file_name="release_curves.csv",
    mime="text/csv"
)
