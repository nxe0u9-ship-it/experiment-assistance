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
# 2. 데이터 처리 함수
# ==========================================

TIME_FACTORS = {
    "초": 60,
    "분": 1,
    "시간": 1 / 60,
    "일": 1 / 1440
}


# 빈 입력표 생성

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


# 입력 데이터의 유효성 검사

def validate_data(df):

    df = df.dropna(how="all").copy()

    if len(df) < 2:
        raise ValueError(
            "데이터를 2개 이상 입력해 주세요."
        )

    df = df.apply(
        pd.to_numeric,
        errors="coerce"
    )

    if not np.isfinite(df.to_numpy()).all():
        raise ValueError(
            "모든 항목에 유효한 숫자를 입력해 주세요."
        )

    if (df["시간"] < 0).any():
        raise ValueError(
            "시간은 음수가 될 수 없습니다."
        )

    if df["시간"].duplicated().any():
        raise ValueError(
            "동일한 시간이 중복되어 있습니다."
        )

    if (
        (df["누적 방출률(%)"] < 0)
        | (df["누적 방출률(%)"] > 100)
    ).any():
        raise ValueError(
            "누적 방출률은 0~100% 사이여야 합니다."
        )

    return df.sort_values(
        "시간"
    ).reset_index(drop=True)


# 실험 데이터 분석 페이지에서 가져온 데이터 변환

def convert_release_data(df, unit):

    required = [
        "시간(분)",
        "누적 방출률(%)"
    ]

    if not all(col in df.columns for col in required):
        raise ValueError(
            "누적 방출률이 계산되지 않은 실험군입니다."
        )

    if "방출 분석 구분" not in df.columns:
        raise ValueError(
            "실험 데이터의 출처를 확인할 수 없습니다."
        )

    if not df["방출 분석 구분"].eq("실험 추정값").all():
        raise ValueError(
            "테스트용 가상 데이터는 불러올 수 없습니다."
        )

    converted = df[required].copy()

    converted = converted.rename(
        columns={"시간(분)": "시간"}
    )

    # 기존 페이지는 분 단위로 저장하므로
    # 현재 유사도 분석 페이지의 시간 단위로 환산한다.

    converted["시간"] = (
        converted["시간"] * TIME_FACTORS[unit]
    )

    # 결측값을 임의로 채우거나 제거하지 않는다.
    # 잘못된 방출률도 임의로 보정하지 않는다.

    if converted.isna().any().any():
        raise ValueError(
            "측정되지 않은 값이 포함되어 있습니다. "
            "원본 실험 결과를 확인해 주세요."
        )

    return validate_data(converted)


# 입력표 공통 설정

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

st.caption(
    "표 하단의 + 버튼을 이용해 측정 시점을 "
    "추가할 수 있습니다. "
    "시간 단위를 변경하면 직접 입력란은 "
    "해당 단위의 별도 입력란으로 전환됩니다."
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
        np.diff(target["누적 방출률(%)"]) < 0
    ).any():

        raise ValueError(
            "목표 누적 방출률은 감소할 수 없습니다."
        )

    st.line_chart(
        target.set_index("시간"),
        x_label=f"시간({unit})",
        y_label="누적 방출률(%)"
    )

except ValueError as e:

    target = None
    st.info(str(e))


# ==========================================
# 4. 실험 데이터 입력 방식 선택
# ==========================================

st.divider()

st.header("2. 실제 실험 데이터 입력")

input_modes = st.multiselect(
    "데이터 입력 방식",
    [
        "저장된 실험 데이터 불러오기",
        "직접 입력"
    ],
    default=["직접 입력"]
)

st.caption(
    "두 가지 입력 방식을 동시에 선택하여 "
    "저장된 실험군과 직접 입력한 실험군을 "
    "함께 비교할 수 있습니다."
)

experiments = []

input_error = False

# ==========================================
# 5. 저장된 실험 데이터 불러오기
# ==========================================

if "저장된 실험 데이터 불러오기" in input_modes:

    st.subheader("저장된 실험 데이터")

    # main.py에서 저장한 실험군을 가져온다.
    # 저장 구조: 실험군 이름 → (지름, 개수, 데이터)

    saved_groups = st.session_state.get(
        "release_groups",
        {}
    )

    available_groups = {}
    unavailable_groups = {}

    for name, group in saved_groups.items():

        try:

            diameter, bead_count, df = group

            converted = convert_release_data(
                df,
                unit
            )

            available_groups[
                f"저장 실험군: {name}"
            ] = {
                "name": name,
                "conditions": (
                    f"평균 비드 지름: {diameter:g} mm\n"
                    f"비드 개수: {bead_count}개"
                ),
                "data": converted
            }

        except (ValueError, TypeError, KeyError) as e:

            unavailable_groups[name] = str(e)

    # 실험 데이터 분석 페이지의 가장 최근 결과도
    # 실험군 저장 여부와 관계없이 가져올 수 있도록 한다.

    latest = st.session_state.get(
        "latest_release"
    )

    if isinstance(latest, pd.DataFrame):

        try:

            converted = convert_release_data(
                latest,
                unit
            )

            available_groups[
                "최근 방출 분석 결과"
            ] = {
                "name": "최근 방출 분석 결과",
                "conditions": (
                    "실험 데이터 분석 페이지의 "
                    "최근 분석 결과"
                ),
                "data": converted
            }

        except ValueError as e:

            unavailable_groups[
                "최근 방출 분석 결과"
            ] = str(e)

    # 불러올 수 있는 실험군이 있는 경우

    if available_groups:

        selected_groups = st.multiselect(
            "불러올 실험군 선택",
            options=list(available_groups.keys())
        )

        if not selected_groups:

            st.info(
                "비교할 실험군을 선택해 주세요."
            )

            input_error = True

        for selected in selected_groups:

            imported = available_groups[selected]

            with st.expander(
                f"📂 {imported['name']}",
                expanded=True
            ):

                st.success(
                    "실험 데이터 연동 완료"
                )

                st.write(
                    "**하이드로젤 제조 조건**"
                )

                st.write(
                    imported["conditions"]
                )

                extra_conditions = st.text_area(
                    "추가 제조 조건",
                    placeholder=(
                        "알지네이트 농도, 가교제 농도, "
                        "가교 시간 등을 추가로 기록하세요."
                    ),
                    key=f"import_conditions_{selected}"
                )

                st.dataframe(
                    imported["data"],
                    hide_index=True,
                    use_container_width=True,
                    column_config=editor_config(unit)
                )

                st.caption(
                    "불러온 측정값은 원본 데이터 보존을 "
                    "위해 이 페이지에서 수정하지 않습니다."
                )

                if (
                    np.diff(
                        imported["data"]["누적 방출률(%)"]
                    ) < 0
                ).any():

                    st.warning(
                        "누적 방출률이 감소하는 구간이 "
                        "있습니다. 측정 오차를 확인하세요."
                    )

                conditions = imported["conditions"]

                if extra_conditions.strip():

                    conditions += (
                        "\n" + extra_conditions.strip()
                    )

                experiments.append({
                    "name": imported["name"],
                    "conditions": conditions,
                    "source": "실험 데이터 연동",
                    "data": imported["data"].copy()
                })

    else:

        st.info(
            "불러올 수 있는 실험 데이터가 없습니다. "
            "실험 데이터 분석 페이지에서 방출률을 "
            "계산하고 실험군을 저장해 주세요."
        )

        input_error = True

    # 불러올 수 없는 실험군과 그 이유를 표시한다.

    if unavailable_groups:

        with st.expander(
            "불러올 수 없는 실험 데이터 확인"
        ):

            for name, reason in unavailable_groups.items():

                st.warning(
                    f"{name}: {reason}"
                )

    st.caption(
        "저장된 실험 데이터는 현재 브라우저 세션에서 "
        "공유됩니다. 새로고침하거나 접속을 종료하면 "
        "사라질 수 있습니다."
    )


# ==========================================
# 6. 실제 실험 데이터 직접 입력
# ==========================================

if "직접 입력" in input_modes:

    st.subheader("실험 데이터 직접 입력")

    experiment_count = st.number_input(
        "직접 입력할 실험군 수",
        min_value=1,
        max_value=10,
        value=1,
        step=1
    )

    for i in range(experiment_count):

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
                    "가교 시간, 비드 크기 등을 "
                    "기록하세요."
                ),
                key=f"manual_conditions_{i}"
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
                        "있습니다. 측정 오차 또는 "
                        "계산 오류를 확인하세요."
                    )

                experiments.append({
                    "name": (
                        name.strip()
                        or f"실험군 {i + 1}"
                    ),
                    "conditions": conditions,
                    "source": "직접 입력",
                    "data": valid
                })

                st.success(
                    "데이터 입력 완료"
                )

            except ValueError as e:

                st.info(str(e))
                input_error = True


# ==========================================
# 7. 분석 가능 여부 확인
# ==========================================

st.divider()

st.header("3. 방출 곡선 유사도 분석")

if target is None:

    st.info(
        "목표 방출 곡선을 먼저 입력해 주세요."
    )

    st.stop()

if not experiments:

    st.info(
        "실험 데이터를 불러오거나 "
        "직접 입력해 주세요."
    )

    st.stop()

if input_error:

    st.info(
        "선택한 모든 입력 방식의 데이터 입력을 "
        "완료해 주세요. 사용하지 않는 입력 방식은 "
        "선택을 해제할 수 있습니다."
    )

    st.stop()

st.success(
    f"총 {len(experiments)}개 실험군의 "
    "유사도를 분석합니다."
)


# ==========================================
# 8. 유사도 계산 원리
# ==========================================

with st.expander("유사도 계산 원리"):

    st.latex(
        r"RMSE="
        r"\sqrt{\frac{1}{n}"
        r"\sum_{i=1}^{n}(T_i-E_i)^2}"
    )

    st.write(
        "T는 목표 방출률, E는 실험 방출률, "
        "n은 비교한 데이터의 개수입니다."
    )

    st.write(
        "RMSE가 작을수록 두 방출 곡선의 "
        "차이가 작습니다."
    )

    st.latex(
        r"\text{Similarity Score}=100-RMSE"
    )

    st.caption(
        "유사도 점수는 본 프로그램에서 정의한 "
        "비교 지표이며, 공인된 약학적 평가 "
        "지표는 아닙니다."
    )


# ==========================================
# 9. 공통 분석 시간 범위 설정
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
        "목표 곡선과 실험군의 공통 측정 "
        "시간 범위가 부족합니다."
    )

    st.stop()

# 모든 실험군을 동일한 시간 범위에서 비교한다.

common_time = np.linspace(
    start_time,
    end_time,
    201
)

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
# 10. 실험군별 유사도 계산
# ==========================================

for i, experiment in enumerate(experiments):

    data = experiment["data"]

    # 측정 시간이 서로 다른 경우
    # 선형 보간으로 동일한 시간에서 비교한다.
    # 측정 범위를 벗어난 값은 추정하지 않는다.

    actual_y = np.interp(
        common_time,
        data["시간"],
        data["누적 방출률(%)"]
    )

    rmse = np.sqrt(
        np.mean(
            (target_y - actual_y) ** 2
        )
    )

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
# 11. 방출 곡선 시각화
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
        "모든 실험군에 공통으로 포함되는 "
        "시간 범위만 분석했습니다. "
        "이 결과를 전체 목표 곡선에 대한 "
        "유사도로 해석하지 마세요."
    )

st.line_chart(
    chart_data.set_index("시간"),
    x_label=f"시간({unit})",
    y_label="누적 방출률(%)"
)


# ==========================================
# 12. 유사도 순위 표시
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

        st.caption(
            f'데이터 출처: {row["데이터 출처"]}'
        )

    with right:

        st.metric(
            "유사도",
            f'{row["유사도 점수"]:.2f}점'
        )

    st.caption(
        f'RMSE: {row["RMSE"]:.3f}%p'
    )


# ==========================================
# 13. 가장 유사한 실험군 표시
# ==========================================

best_groups = ranking[
    ranking["순위"] == 1
]

st.subheader(
    "목표 방출 특성에 가장 가까운 실험군"
)

for _, best in best_groups.iterrows():

    st.success(
        f'{best["실험군"]} — '
        f'유사도 {best["유사도 점수"]:.2f}점'
    )

    if best["제조 조건"].strip():

        st.write(
            "**하이드로젤 제조 조건**"
        )

        st.write(best["제조 조건"])

st.caption(
    "본 분석은 입력된 실험 데이터에 대한 "
    "비교 결과이며, 실험하지 않은 제조 조건의 "
    "방출 특성이나 실제 약물의 치료 효과를 "
    "예측하지 않습니다."
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

with col1:

    st.download_button(
        label="📥 유사도 분석 결과 CSV 다운로드",
        data=ranking.to_csv(
            index=False
        ).encode("utf-8-sig"),
        file_name="release_similarity.csv",
        mime="text/csv",
        use_container_width=True
    )

with col2:

    export_chart = chart_data.rename(
        columns={
            "시간": f"시간({unit})"
        }
    )

    st.download_button(
        label="📥 방출 곡선 데이터 CSV 다운로드",
        data=export_chart.to_csv(
            index=False
        ).encode("utf-8-sig"),
        file_name="release_curves.csv",
        mime="text/csv",
        use_container_width=True
    )
