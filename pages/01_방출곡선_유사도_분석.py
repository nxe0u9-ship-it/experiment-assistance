import streamlit as st
import pandas as pd
import numpy as np

# ==========================================
# 1. 페이지 기본 설정
# ==========================================

st.title("📈 방출 곡선 유사도 분석")

st.caption(
    "HydroRelease Lab | Release Profile Similarity Analysis"
)

st.info(
    "목표 방출 곡선과 실제 실험 결과를 비교하여 "
    "목표 방출 특성에 가장 가까운 실험 조건을 탐색합니다."
)


# ==========================================
# 2. 데이터 처리 함수
# ==========================================

TIME_FACTORS = {
    "초": 60,
    "분": 1,
    "시간": 1 / 60,
    "일": 1 / 1440
}


# 빈 데이터 입력표 생성

def create_empty_data():

    return pd.DataFrame({
        "시간": pd.Series(
            [np.nan, np.nan],
            dtype="float64"
        ),
        "누적 방출률(%)": pd.Series(
            [np.nan, np.nan],
            dtype="float64"
        )
    })


# 데이터 유효성 검사

def validate_data(df):

    required = [
        "시간",
        "누적 방출률(%)"
    ]

    if not all(col in df.columns for col in required):

        raise ValueError(
            "필수 데이터 항목이 누락되었습니다."
        )

    df = df[required].copy()

    df = df.dropna(how="all")

    if len(df) < 2:

        raise ValueError(
            "시간과 누적 방출률을 2개 이상 입력해 주세요."
        )

    df = df.apply(
        pd.to_numeric,
        errors="coerce"
    )

    if not np.isfinite(
        df.to_numpy(dtype=float)
    ).all():

        raise ValueError(
            "모든 항목에 유효한 숫자를 입력해 주세요."
        )

    if (df["시간"] < 0).any():

        raise ValueError(
            "시간은 음수가 될 수 없습니다."
        )

    if df["시간"].duplicated().any():

        raise ValueError(
            "동일한 측정 시간이 중복되어 있습니다."
        )

    if not df["누적 방출률(%)"].between(
        0, 100
    ).all():

        raise ValueError(
            "누적 방출률은 0~100% 사이여야 합니다."
        )

    return df.sort_values(
        "시간"
    ).reset_index(drop=True)


# 입력표 열 설정

def editor_config(unit):

    return {

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


# ==========================================
# 3. 메인 페이지에서 전달한 데이터 수신
# ==========================================

transfer = st.session_state.get(
    "similarity_transfer"
)

has_transfer = transfer is not None

is_demo = (
    bool(transfer.get("is_demo", False))
    if has_transfer
    else False
)

if has_transfer:

    if is_demo:

        st.warning(
            "영상·농도·방출 분석 페이지에서 전달된 "
            "테스트용 가상 데이터입니다. "
            "분석 결과는 기능 검증에만 활용하세요."
        )

    else:

        st.success(
            "영상·농도·방출 분석 결과가 "
            "자동으로 연동되었습니다."
        )


# ==========================================
# 4. 목표 방출 곡선 설정
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

st.caption(
    "표 하단의 + 버튼을 이용하여 "
    "측정 시점을 추가할 수 있습니다. "
    "시간 단위를 변경하면 직접 입력표도 "
    "해당 단위의 입력표로 전환됩니다."
)

target_data = st.data_editor(
    create_empty_data(),
    num_rows="dynamic",
    hide_index=True,
    use_container_width=True,
    key=f"target_curve_{unit}",
    column_config=editor_config(unit)
)

target = None

try:

    target = validate_data(target_data)

    if (
        np.diff(
            target["누적 방출률(%)"]
        ) < 0
    ).any():

        raise ValueError(
            "목표 누적 방출률은 감소할 수 없습니다."
        )

    st.subheader("목표 방출 곡선")

    st.line_chart(
        target.set_index("시간"),
        x_label=f"시간({unit})",
        y_label="누적 방출률(%)"
    )

except ValueError as e:

    target = None

    st.info(str(e))


# ==========================================
# 5. 실제 실험 데이터 입력
# ==========================================

st.divider()

st.header("2. 실제 실험 데이터 입력")

experiments = []

input_error = False


# ==========================================
# 6. 전달받은 실험 데이터 자동 입력
# ==========================================

if has_transfer:

    st.subheader("자동 연동된 실험 데이터")

    try:

        # 메인 페이지에서 전달된 원본 데이터를 복사한다.

        imported = transfer["data"].copy()

        required = [
            "시간(분)",
            "누적 방출률(%)"
        ]

        if not all(
            col in imported.columns
            for col in required
        ):

            raise ValueError(
                "전달된 데이터에 시간 또는 "
                "누적 방출률이 없습니다."
            )

        imported = imported[required].copy()

        # 유사도 분석 페이지의 데이터 형식으로 변경한다.

        imported = imported.rename(
            columns={
                "시간(분)": "시간"
            }
        )

        # 메인 페이지의 분 단위를
        # 사용자가 선택한 시간 단위로 환산한다.

        imported["시간"] = (
            imported["시간"]
            * TIME_FACTORS[unit]
        )

        if imported.isna().any().any():

            raise ValueError(
                "전달된 데이터에 측정 불가 값이 포함되어 있습니다."
            )

        imported = validate_data(
            imported
        )

        if is_demo:

            st.warning(
                f"테스트용 측정 데이터 "
                f"{len(imported)}개가 자동 입력되었습니다."
            )

        else:

            st.success(
                f"실험 측정 데이터 "
                f"{len(imported)}개가 자동 입력되었습니다."
            )

        imported_name = st.text_input(
            "실험군 이름",
            value=transfer.get(
                "name",
                "현재 실험 결과"
            ),
            key="imported_experiment_name"
        )

        conditions = st.text_area(
            "하이드로젤 제조 조건",
            placeholder=(
                "알지네이트 농도, 가교제 농도, "
                "가교 시간, 비드 크기 등을 입력하세요."
            ),
            key="imported_conditions"
        )

        col1, col2 = st.columns(2)

        volume = transfer.get(
            "volume_ml"
        )

        initial_mass = transfer.get(
            "initial_mass_mg"
        )

        with col1:

            st.metric(
                "외부 용액 부피",
                (
                    f"{volume:g} mL"
                    if volume is not None
                    else "정보 없음"
                )
            )

        with col2:

            st.metric(
                "초기 색소 포함량",
                (
                    f"{initial_mass:g} mg"
                    if initial_mass is not None
                    else "정보 없음"
                )
            )

        # 전달된 데이터가 실제 실험 데이터 영역에
        # 자동으로 표시되도록 한다.

        st.dataframe(
            imported,
            hide_index=True,
            use_container_width=True,
            column_config=editor_config(unit)
        )

        st.caption(
            "영상·농도·방출 분석 결과에서 "
            "자동으로 가져온 데이터입니다. "
            "별도로 입력할 필요가 없습니다."
        )

        if (
            np.diff(
                imported["누적 방출률(%)"]
            ) < 0
        ).any():

            st.warning(
                "누적 방출률이 감소하는 구간이 있습니다. "
                "측정 오차 또는 계산 오류를 확인해 주세요."
            )

        # 전달받은 데이터를 유사도 분석 대상에
        # 직접 추가하는 핵심 코드이다.

        experiments.append({

            "name": (
                imported_name.strip()
                or "현재 실험 결과"
            ),

            "conditions": conditions,

            "source": (
                "테스트용 가상 데이터"
                if is_demo
                else "영상·농도·방출 분석 연동"
            ),

            "data": imported.copy(),

            "is_demo": is_demo

        })

    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError
    ) as e:

        st.error(
            f"실험 데이터 연동 오류: {e}"
        )

        input_error = True

    if st.button(
        "연동된 실험 데이터 제거",
        key="remove_transfer"
    ):

        st.session_state.pop(
            "similarity_transfer",
            None
        )

        st.session_state.pop(
            "imported_experiment_name",
            None
        )

        st.session_state.pop(
            "imported_conditions",
            None
        )

        st.rerun()

    st.caption(
        "연동된 데이터는 현재 접속 세션에서 유지됩니다."
    )


# ==========================================
# 7. 실험 데이터 직접 입력
# ==========================================

if has_transfer:

    st.subheader("추가 실험군 직접 입력")

    st.caption(
        "연동된 실험 결과 외에 추가로 비교할 "
        "실험군이 있는 경우 입력해 주세요."
    )

else:

    st.subheader("실험 데이터 직접 입력")

    st.caption(
        "영상 분석 결과를 전달하지 않은 경우 "
        "측정 데이터를 직접 입력할 수 있습니다."
    )

# 자동 연동된 데이터가 있으면
# 직접 입력할 실험군 수를 기본 0개로 설정한다.

default_count = (
    0 if has_transfer else 1
)

manual_count = st.number_input(
    "직접 입력할 실험군 수",
    min_value=0,
    max_value=10,
    value=default_count,
    step=1,
    key=(
        "manual_count_linked"
        if has_transfer
        else "manual_count_unlinked"
    )
)

for i in range(manual_count):

    with st.expander(
        f"직접 입력 실험군 {i + 1}",
        expanded=True
    ):

        name = st.text_input(
            "실험군 이름",
            value=f"실험군 {i + 1}",
            key=f"manual_name_{i}"
        )

        conditions = st.text_area(
            "하이드로젤 제조 조건",
            placeholder=(
                "알지네이트 농도, 가교제 농도, "
                "가교 시간, 비드 크기 등을 입력하세요."
            ),
            key=f"manual_conditions_{i}"
        )

        manual_demo = st.checkbox(
            "테스트용 가상 데이터",
            value=is_demo if has_transfer else False,
            key=f"manual_demo_{i}"
        )

        edited = st.data_editor(
            create_empty_data(),
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            key=f"manual_data_{i}_{unit}",
            column_config=editor_config(unit)
        )

        try:

            valid = validate_data(edited)

            if (
                np.diff(
                    valid["누적 방출률(%)"]
                ) < 0
            ).any():

                st.warning(
                    "누적 방출률이 감소하는 구간이 "
                    "있습니다. 측정값을 확인해 주세요."
                )

            experiments.append({

                "name": (
                    name.strip()
                    or f"실험군 {i + 1}"
                ),

                "conditions": conditions,

                "source": (
                    "직접 입력한 가상 데이터"
                    if manual_demo
                    else "직접 입력"
                ),

                "data": valid,

                "is_demo": manual_demo

            })

            st.success(
                "데이터 입력 완료"
            )

        except ValueError as e:

            st.info(str(e))

            input_error = True


# ==========================================
# 8. 유사도 분석 가능 여부 확인
# ==========================================

st.divider()

st.header("3. 방출 곡선 유사도 분석")

if target is None:

    st.info(
        "목표 방출 곡선을 설정하면 "
        "유사도 분석 결과가 자동으로 표시됩니다."
    )

    st.stop()

if not experiments:

    st.info(
        "실제 실험 데이터를 입력해 주세요."
    )

    st.stop()

if input_error:

    st.info(
        "입력 데이터 또는 연동 데이터를 확인해 주세요."
    )

    st.stop()

# 실제 실험 결과와 가상 데이터를 혼합하여
# 비교하지 않도록 한다.

data_types = {
    experiment["is_demo"]
    for experiment in experiments
}

if len(data_types) > 1:

    st.warning(
        "실제 실험 데이터와 테스트용 가상 데이터는 "
        "동시에 비교할 수 없습니다."
    )

    st.stop()

analysis_demo = True in data_types

if analysis_demo:

    st.warning(
        "현재 유사도 분석은 가상 데이터를 "
        "이용한 기능 검증입니다."
    )

st.caption(
    f"총 {len(experiments)}개 실험군을 분석합니다."
)


# ==========================================
# 9. 유사도 계산 원리
# ==========================================

with st.expander("유사도 계산 원리"):

    st.latex(
        r"RMSE="
        r"\sqrt{\frac{1}{n}"
        r"\sum_{i=1}^{n}(T_i-E_i)^2}"
    )

    st.write(
        "T는 목표 방출률, E는 실제 방출률, "
        "n은 비교 시점의 개수입니다."
    )

    st.write(
        "RMSE가 작을수록 목표 방출 곡선과 "
        "실험 방출 곡선이 유사합니다."
    )

    st.latex(
        r"\text{Similarity Score}=100-RMSE"
    )

    st.caption(
        "유사도 점수는 본 프로그램에서 정의한 "
        "비교 지표이며 공인된 약학적 평가 지표는 아닙니다."
    )


# ==========================================
# 10. 공통 분석 시간 범위 설정
# ==========================================

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
        "목표 곡선과 실험 결과의 "
        "공통 측정 시간 범위가 부족합니다."
    )

    st.stop()

# 공통 시간 범위를 일정한 간격으로 나눈다.

common_time = np.linspace(
    start_time,
    end_time,
    201
)

# 선형 보간으로 목표 방출률 계산

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


# ==========================================
# 11. 실험군별 유사도 계산
# ==========================================

for i, experiment in enumerate(experiments):

    data = experiment["data"]

    # 측정 시간이 다른 경우 선형 보간을 적용한다.
    # 측정 시간 범위 밖의 값은 추정하지 않는다.

    actual_y = np.interp(
        common_time,
        data["시간"],
        data["누적 방출률(%)"]
    )

    # 평균 제곱근 오차 계산

    rmse = np.sqrt(

        np.mean(
            (target_y - actual_y) ** 2
        )

    )

    # 유사도 점수 계산

    similarity = 100 - rmse

    label = (
        f'{experiment["name"]} '
        f'({i + 1})'
    )

    chart_data[label] = actual_y

    results.append({

        "실험군": label,

        "데이터 출처": experiment["source"],

        "제조 조건": experiment["conditions"],

        "분석 시작 시간": start_time,

        "분석 종료 시간": end_time,

        "시간 단위": unit,

        "RMSE": float(rmse),

        "유사도 점수": float(similarity)

    })


# ==========================================
# 12. 목표 및 실제 방출 곡선 비교
# ==========================================

st.subheader("목표 및 실제 방출 곡선 비교")

st.caption(
    f"공통 분석 범위: "
    f"{start_time:g}~{end_time:g}{unit}"
)

partial_analysis = (

    start_time > target["시간"].min()

    or end_time < target["시간"].max()

)

if partial_analysis:

    st.warning(
        "목표 시간 범위 전체를 비교할 수 없어 "
        "공통 시간 구간만 분석했습니다. "
        "전체 목표 곡선에 대한 유사도로 "
        "해석할 수 없습니다."
    )

st.line_chart(
    chart_data.set_index("시간"),
    x_label=f"시간({unit})",
    y_label="누적 방출률(%)"
)

st.caption(
    "측정 시점이 서로 다른 경우 "
    "선형 보간을 이용하여 비교합니다."
)


# ==========================================
# 13. 유사도 분석 결과
# ==========================================

st.divider()

st.header("4. 유사도 분석 결과")

ranking = pd.DataFrame(
    results
)

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

# 실험군이 한 개일 경우 유사도와 RMSE를 바로 표시한다.

if len(ranking) == 1:

    best = ranking.iloc[0]

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "목표 곡선 유사도",
            f'{best["유사도 점수"]:.2f}점'
        )

    with col2:

        st.metric(
            "평균 제곱근 오차",
            f'{best["RMSE"]:.3f}%p'
        )

    st.progress(
        float(
            np.clip(
                best["유사도 점수"] / 100,
                0,
                1
            )
        )
    )

    st.caption(
        f'데이터 출처: {best["데이터 출처"]}'
    )

else:

    # 여러 실험군이 있는 경우 유사도 순위를 표시한다.

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

            st.caption(
                f'데이터 출처: {row["데이터 출처"]}'
            )

        with right:

            st.metric(
                "유사도 점수",
                f'{row["유사도 점수"]:.2f}점'
            )

        st.caption(
            f'RMSE: {row["RMSE"]:.3f}%p'
        )

    st.subheader(

        "목표 방출 곡선에 가장 가까운 실험군"

        if not partial_analysis

        else "공통 시간 구간에서 가장 가까운 실험군"

    )

    best_groups = ranking[
        ranking["순위"] == 1
    ]

    for _, best in best_groups.iterrows():

        st.success(
            f'{best["실험군"]} — '
            f'유사도 {best["유사도 점수"]:.2f}점'
        )

        if best["제조 조건"].strip():

            st.write(
                "**하이드로젤 제조 조건**"
            )

            st.write(
                best["제조 조건"]
            )

st.caption(
    "본 분석은 입력된 실험 결과에 대한 비교이며, "
    "실험하지 않은 제조 조건의 방출 특성이나 "
    "실제 약물의 치료 효과를 예측하지 않습니다."
)


# ==========================================
# 14. 분석 결과 저장
# ==========================================

st.divider()

st.header("5. 분석 결과 저장")

st.dataframe(
    ranking.round(3),
    hide_index=True,
    use_container_width=True
)

col1, col2 = st.columns(2)

# 가상 데이터의 다운로드 파일명과 출처를 구분한다.

file_prefix = (
    "demo_" if analysis_demo else ""
)

with col1:

    st.download_button(

        label="📥 유사도 분석 결과 CSV 다운로드",

        data=ranking.to_csv(
            index=False
        ).encode("utf-8-sig"),

        file_name=(
            f"{file_prefix}release_similarity.csv"
        ),

        mime="text/csv",

        use_container_width=True

    )

with col2:

    export_chart = chart_data.rename(
        columns={
            "시간": f"시간({unit})"
        }
    ).copy()

    export_chart["데이터 구분"] = (
        "테스트용 가상 데이터"
        if analysis_demo
        else "실험 데이터"
    )

    st.download_button(

        label="📥 방출 곡선 데이터 CSV 다운로드",

        data=export_chart.to_csv(
            index=False
        ).encode("utf-8-sig"),

        file_name=(
            f"{file_prefix}release_curves.csv"
        ),

        mime="text/csv",

        use_container_width=True

    )
