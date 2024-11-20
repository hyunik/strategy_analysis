import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import io

# 페이지 설정
st.set_page_config(
    page_title="암호화폐 거래 분석",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일 설정
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stButton>button {
        width: 100%;
    }
    .reportview-container .main .block-container {
        padding-top: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

def read_data_file(uploaded_file):
    """CSV 또는 Excel 파일 읽기"""
    try:
        # 파일 확장자 확인
        file_extension = Path(uploaded_file.name).suffix.lower()
        
        if file_extension == '.csv':
            # CSV 파일 읽기 (인코딩 자동 감지)
            try:
                return pd.read_csv(uploaded_file)
            except UnicodeDecodeError:
                # UTF-8 실패시 cp949 시도
                uploaded_file.seek(0)  # 파일 포인터 리셋
                return pd.read_csv(uploaded_file, encoding='cp949')
        else:
            # Excel 파일 읽기
            return pd.read_excel(uploaded_file)
            
    except Exception as e:
        st.error(f"파일 읽기 오류: {str(e)}")
        return None

def analyze_trading_signals(df, leverage, side_col, time_col, price_col, amount_col):
    """거래 데이터 분석 함수"""
    try:
        # 시간을 datetime 형식으로 변환
        df[time_col] = pd.to_datetime(df[time_col])
        
        # 시간순 오름차순 정렬 (과거 -> 현재)
        df = df.sort_values(time_col, ascending=True)
        
        # '매수'가 포함된 신호만 필터링
        entry_signals = df[df[side_col].str.contains('매수', case=False)]
        
        if entry_signals.empty:
            st.error("매수 신호가 없습니다. 데이터를 확인해주세요.")
            return None, None
        
        # 필요한 증거금 계산 (계약 × 가격 ÷ 레버리지)
        entry_signals['필요증거금'] = (entry_signals[amount_col].astype(float) * 
                                  entry_signals[price_col].astype(float) / leverage)
        
        # 결과 저장을 위한 리스트
        results = []
        
        # 매수 그룹 분석 변수
        current_group_start = None
        current_group_entries = []
        
        # 각 행을 순회하며 매수 그룹 분석
        for idx, row in entry_signals.iterrows():
            current_time = row[time_col]
            current_margin = row['필요증거금']
            signal_type = row[side_col]
            
            if current_group_start is None:
                # 새로운 그룹 시작
                current_group_start = current_time
                current_group_entries = [(current_time, current_margin, signal_type)]
            else:
                # 이전 매수와의 시간 간격 확인
                prev_time = current_group_entries[-1][0]
                time_diff = (current_time - prev_time).total_seconds()
                
                if time_diff <= 300:  # 5분 이내의 매수는 같은 그룹으로 처리
                    current_group_entries.append((current_time, current_margin, signal_type))
                else:
                    # 이전 그룹 저장
                    total_margin = sum(margin for _, margin, _ in current_group_entries)
                    results.append({
                        '시작시간': current_group_start,
                        '종료시간': current_group_entries[-1][0],
                        '필요증거금합계': total_margin,
                        '진입횟수': len(current_group_entries),
                        '개별진입시간': [time.strftime('%Y-%m-%d %H:%M:%S') for time, _, _ in current_group_entries],
                        '개별진입금액': [f"{margin:.2f}" for _, margin, _ in current_group_entries],
                        '신호유형': [signal for _, _, signal in current_group_entries]
                    })
                    
                    # 새로운 그룹 시작
                    current_group_start = current_time
                    current_group_entries = [(current_time, current_margin, signal_type)]
        
        # 마지막 그룹 처리
        if current_group_entries:
            total_margin = sum(margin for _, margin, _ in current_group_entries)
            results.append({
                '시작시간': current_group_start,
                '종료시간': current_group_entries[-1][0],
                '필요증거금합계': total_margin,
                '진입횟수': len(current_group_entries),
                '개별진입시간': [time.strftime('%Y-%m-%d %H:%M:%S') for time, _, _ in current_group_entries],
                '개별진입금액': [f"{margin:.2f}" for _, margin, _ in current_group_entries],
                '신호유형': [signal for _, _, signal in current_group_entries]
            })
        
        results_df = pd.DataFrame(results)
        
        # 통계 정보 추가
        total_entries = sum(len(entry_times) for entry_times in results_df['개별진입시간'])
        avg_entries_per_group = total_entries / len(results_df) if len(results_df) > 0 else 0
        max_margin = results_df['필요증거금합계'].max()
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("매수 분석")
        st.sidebar.write(f"총 진입 횟수: {total_entries}")
        st.sidebar.write(f"매수 그룹 수: {len(results_df)}")
        st.sidebar.write(f"그룹당 평균 진입 횟수: {avg_entries_per_group:.2f}")
        st.sidebar.write(f"최대 필요증거금: {max_margin:.2f} USDT")
        
        return results_df, entry_signals
        
    except Exception as e:
        st.error(f"분석 중 오류 발생: {str(e)}")
        st.error(f"에러 상세: {str(e.__class__.__name__)}")
        return None, None

def create_visualizations(results_df):
    """분석 결과 시각화"""
    # 필요증거금 변화 그래프
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=results_df['시작시간'], y=results_df['필요증거금합계'],
                             mode='lines+markers', name='필요증거금'))
    fig1.update_layout(title='시간대별 필요증거금 변화',
                      xaxis_title='시간',
                      yaxis_title='필요증거금 (USDT)')
    
    # 진입횟수 그래프
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=results_df['시작시간'], y=results_df['진입횟수'],
                         name='진입횟수'))
    fig2.update_layout(title='시간대별 진입횟수',
                      xaxis_title='시간',
                      yaxis_title='진입횟수')
    
    return fig1, fig2

# 메인 앱
def main():
    st.title("암호화폐 거래 분석 도구 📊")
    st.write("거래 데이터를 분석하여 필요 증거금과 매수 패턴을 확인해보세요.")

    # 파일 업로드
    uploaded_file = st.file_uploader(
        "거래 데이터 파일을 업로드하세요 (CSV 또는 Excel)",
        type=['csv', 'xlsx', 'xls']
    )

    if uploaded_file is not None:
        # 데이터 읽기
        df = read_data_file(uploaded_file)
        
        if df is not None:
            # 데이터 미리보기
            st.subheader("데이터 미리보기")
            st.dataframe(df.head())
            
            # 컬럼 정보 표시
            st.subheader("데이터 구조")
            st.write("사용 가능한 컬럼:")
            for col in df.columns:
                st.code(col)
            
            # 사이드바에 파라미터 입력
            with st.sidebar:
                st.header("분석 파라미터 설정")
                leverage = st.number_input("레버리지 배수", min_value=1.0, value=10.0, step=0.1)
                
                # 컬럼 선택
                st.subheader("컬럼 매핑")
                side_col = st.selectbox("매수/매도 구분 컬럼", df.columns)
                time_col = st.selectbox("시간 컬럼", df.columns)
                price_col = st.selectbox("가격 컬럼", df.columns)
                amount_col = st.selectbox("수량 컬럼", df.columns)
                
                analyze_button = st.button("분석 시작")
            
            if analyze_button:
                # 분석 실행
                results_df, entry_signals = analyze_trading_signals(
                    df, leverage, side_col, time_col, price_col, amount_col
                )
                
                if results_df is not None and entry_signals is not None:
                    # 주요 지표 표시
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("전체 거래 수", len(df))
                    with col2:
                        st.metric("총 진입 횟수", len(entry_signals))
                    with col3:
                        st.metric("진입 그룹 수", len(results_df))
                    
                    col4, col5, col6 = st.columns(3)
                    with col4:
                        st.metric("최대 필요증거금", f"{results_df['필요증거금합계'].max():.2f} USDT")
                    with col5:
                        st.metric("평균 필요증거금", f"{results_df['필요증거금합계'].mean():.2f} USDT")
                    with col6:
                        st.metric("총 필요증거금", f"{results_df['필요증거금합계'].sum():.2f} USDT")
                    
                    # 시각화
                    fig1, fig2 = create_visualizations(results_df)
                    st.plotly_chart(fig1, use_container_width=True)
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    # 상세 분석 결과
                    st.subheader("상세 분석 결과")
                    st.dataframe(results_df)
                    
                    # 결과 다운로드 버튼
                    st.download_button(
                        label="분석 결과 다운로드 (CSV)",
                        data=results_df.to_csv(index=False).encode('utf-8'),
                        file_name='trading_analysis_results.csv',
                        mime='text/csv'
                    )

    else:
        st.info("CSV 또는 Excel 파일을 업로드하면 분석이 시작됩니다.")
    
    # 푸터
    st.markdown("---")
    st.markdown("Made with ❤️ for crypto traders")

if __name__ == "__main__":
    main()
