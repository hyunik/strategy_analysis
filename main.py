# streamlit_app.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="암호화폐 거래 분석", layout="wide")

st.title("암호화폐 거래 분석 도구 📊")

# 파일 업로드
uploaded_file = st.file_uploader("거래 데이터 파일을 업로드하세요 (Excel)", type=['xlsx'])
leverage = st.number_input("레버리지 배수를 입력하세요", min_value=1.0, value=10.0, step=0.1)

def analyze_trading_signals(df, leverage):
    # 기존의 분석 함수와 동일
    df['날짜/시간'] = pd.to_datetime(df['날짜/시간'])
    df = df.sort_values('날짜/시간')
    entry_signals = df[df['구분'].str.contains('매수')]
    entry_signals['필요증거금'] = (entry_signals['개수'].astype(float) * 
                              entry_signals['가격 USDT'].astype(float) / leverage)
    
    results = []
    prev_entry_time = None
    total_margin = 0
    entries_in_group = 0
    
    for idx, row in entry_signals.iterrows():
        current_time = row['날짜/시간']
        margin = row['필요증거금']
        
        if prev_entry_time is None:
            total_margin = margin
            entry_group_start = current_time
            entries_in_group = 1
        else:
            if (current_time - prev_entry_time).total_seconds() <= 300:
                total_margin += margin
                entries_in_group += 1
            else:
                results.append({
                    '시작시간': entry_group_start,
                    '종료시간': prev_entry_time,
                    '필요증거금합계': total_margin,
                    '매수횟수': entries_in_group
                })
                total_margin = margin
                entry_group_start = current_time
                entries_in_group = 1
        
        prev_entry_time = current_time
    
    if prev_entry_time is not None:
        results.append({
            '시작시간': entry_group_start,
            '종료시간': prev_entry_time,
            '필요증거금합계': total_margin,
            '매수횟수': entries_in_group
        })
    
    return pd.DataFrame(results), entry_signals

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    results_df, entry_signals = analyze_trading_signals(df, leverage)
    
    # 분석 결과 표시
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("전체 거래 수", len(df))
    with col2:
        st.metric("총 매수 횟수", len(entry_signals))
    with col3:
        st.metric("매수 그룹 수", len(results_df))
    
    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric("최대 필요증거금", f"{results_df['필요증거금합계'].max():.2f} USDT")
    with col5:
        st.metric("평균 필요증거금", f"{results_df['필요증거금합계'].mean():.2f} USDT")
    with col6:
        st.metric("총 필요증거금", f"{results_df['필요증거금합계'].sum():.2f} USDT")
    
    # 그래프 표시
    st.subheader("시간대별 필요증거금 변화")
    fig1 = px.line(results_df, x='시작시간', y='필요증거금합계')
    st.plotly_chart(fig1, use_container_width=True)
    
    st.subheader("시간대별 매수횟수")
    fig2 = px.bar(results_df, x='시작시간', y='매수횟수')
    st.plotly_chart(fig2, use_container_width=True)
    
    # 상세 데이터 표시
    st.subheader("상세 분석 결과")
    st.dataframe(results_df)
    
    # 결과 다운로드 버튼
    csv = results_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "분석 결과 다운로드 (CSV)",
        csv,
        "trading_analysis_results.csv",
        "text/csv",
        key='download-csv'
    )

else:
    st.info("Excel 파일을 업로드하면 분석이 시작됩니다.")
