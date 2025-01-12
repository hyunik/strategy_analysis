import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from io import StringIO
from datetime import datetime

def load_data(uploaded_file):
    if uploaded_file is not None:
        string_data = StringIO(uploaded_file.getvalue().decode('utf-8'))
        df = pd.read_csv(string_data)
        return df
    return None

def calculate_time_difference(start_time, end_time):
    start = datetime.strptime(start_time, '%Y-%m-%d %H:%M')
    end = datetime.strptime(end_time, '%Y-%m-%d %H:%M')
    diff = end - start
    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    return f"{days}일 {hours}시간 {minutes}분"

def get_strategy_signals(strategy):
    if strategy == 'ATM':
        return ['매수', 'E추매', '바닥', '%추매', '동적긴급추매']
    elif strategy == 'BRM':
        return ['매수', '추매']
    return []

def calculate_margin_requirements(df, leverage, strategy):
    entry_signals = get_strategy_signals(strategy)
    buy_positions = df[df['신호'] == '매수'].index.tolist()
    trade_sections = []
    
    for i, start_pos in enumerate(buy_positions):
        end_pos = buy_positions[i + 1] if i < len(buy_positions) - 1 else len(df)
        section_df = df.iloc[start_pos:end_pos].copy()
        
        # 매수 관련 신호 필터링
        section_entries = section_df[section_df['신호'].isin(entry_signals)].copy()
        # 익절/손절 찾기
        exit_trade = section_df.iloc[-1]
        
        # 증거금 계산
        section_entries['증거금'] = (section_entries['가격 USDT'] * section_entries['계약']) / leverage
        
        # 매수부터 익절까지의 시간 계산
        time_to_exit = calculate_time_difference(
            section_entries.iloc[0]['날짜/시간'],
            exit_trade['날짜/시간']
        )
        
        trade_info = {
            '시작시간': section_entries.iloc[0]['날짜/시간'],
            '종료시간': exit_trade['날짜/시간'],
            '거래 #': section_entries.iloc[0]['거래 #'],
            '총_증거금': section_entries['증거금'].sum(),
            '매수횟수': len(section_entries),
            '청산종류': exit_trade['신호'],
            '청산가격': exit_trade['가격 USDT'],
            '소요시간': time_to_exit,
            '신호별_횟수': section_entries['신호'].value_counts().to_dict(),
            '신호별_증거금': section_entries.groupby('신호')['증거금'].sum().to_dict(),
            '상세거래': section_entries[['날짜/시간', '신호', '가격 USDT', '계약', '증거금']].to_dict('records'),
            '수익': exit_trade.get('수익 USDT', 0),
            '수익률': exit_trade.get('수익 %', 0)
        }
        trade_sections.append(trade_info)
    
    return pd.DataFrame(trade_sections)

def display_max_margin_analysis(trade_sections, strategy):
    st.header('최대 증거금 구간 분석')
    
    max_margin_section = trade_sections.loc[trade_sections['총_증거금'].idxmax()]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric('최대 필요 증거금', f"${max_margin_section['총_증거금']:.2f}")
    with col2:
        st.metric('총 진입 횟수', str(max_margin_section['매수횟수']))
    with col3:
        st.metric('소요 시간', max_margin_section['소요시간'])
    
    st.write('### 거래 상세 정보')
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"거래 번호: #{max_margin_section['거래 #']}")
        st.write(f"시작 시간: {max_margin_section['시작시간']}")
        st.write(f"종료 시간: {max_margin_section['종료시간']}")
    with col2:
        st.write(f"청산 유형: {max_margin_section['청산종류']}")
        st.write(f"청산 가격: ${max_margin_section['청산가격']:.2f}")
        st.write(f"수익: ${max_margin_section['수익']:.2f} ({max_margin_section['수익률']:.2f}%)")
    
    st.write('### 신호별 분석')
    signal_df = pd.DataFrame({
        '신호': list(max_margin_section['신호별_횟수'].keys()),
        '횟수': list(max_margin_section['신호별_횟수'].values()),
        '증거금': [max_margin_section['신호별_증거금'].get(signal, 0) for signal in max_margin_section['신호별_횟수'].keys()]
    })
    st.dataframe(signal_df)
    
    st.write('### 상세 거래 내역')
    detail_df = pd.DataFrame(max_margin_section['상세거래'])
    detail_df['누적_증거금'] = detail_df['증거금'].cumsum()
    st.dataframe(detail_df)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=detail_df['날짜/시간'],
        y=detail_df['누적_증거금'],
        mode='lines+markers',
        name='누적 증거금'
    ))
    fig.update_layout(title='최대 증거금 구간의 누적 증거금 변화')
    st.plotly_chart(fig)

def main():
    st.title('트레이딩 전략 분석기')
    
    st.sidebar.header('전략 설정')
    strategy = st.sidebar.selectbox(
        '전략 선택',
        ['ATM', 'BRM']
    )
    
    leverage = st.sidebar.number_input('레버리지 설정', min_value=1, value=20, step=1)
    
    uploaded_file = st.file_uploader("거래 데이터 CSV 파일을 업로드하세요", type=['csv'])
    
    if uploaded_file is not None:
        try:
            df = load_data(uploaded_file)
            
            if df is not None:
                trade_sections = calculate_margin_requirements(df, leverage, strategy)
                
                # 최대 증거금 구간 분석
                display_max_margin_analysis(trade_sections, strategy)
                
                # 전체 구간 통계
                st.header('전체 거래 통계')
                
                # 익절 유형 분석
                exit_types = trade_sections['청산종류'].value_counts()
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("### 익절 유형 분포")
                    st.dataframe(pd.DataFrame({
                        '익절유형': exit_types.index,
                        '횟수': exit_types.values,
                        '비율(%)': (exit_types.values / len(trade_sections) * 100).round(2)
                    }))
                
                with col2:
                    fig = px.pie(values=exit_types.values, names=exit_types.index, title='익절 유형 비율')
                    st.plotly_chart(fig)
                
                # 증거금 분포 분석
                st.write("### 증거금 분포")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric('평균 필요 증거금', f"${trade_sections['총_증거금'].mean():.2f}")
                with col2:
                    st.metric('중간값 필요 증거금', f"${trade_sections['총_증거금'].median():.2f}")
                with col3:
                    st.metric('표준편차', f"${trade_sections['총_증거금'].std():.2f}")
                
                # 증거금 분포 히스토그램
                fig = px.histogram(
                    trade_sections, 
                    x='총_증거금',
                    title='거래별 필요 증거금 분포',
                    labels={'총_증거금': '필요 증거금 (USDT)'},
                    nbins=20
                )
                st.plotly_chart(fig)
                
                # 구간별 상세 분석
                st.header('매수 구간별 상세 분석')
                selected_section = st.selectbox(
                    '매수 구간 선택', 
                    range(len(trade_sections)),
                    format_func=lambda x: f"구간 {x+1} ({trade_sections.iloc[x]['시작시간']} ~ {trade_sections.iloc[x]['종료시간']})"
                )
                
                if selected_section is not None:
                    section_data = trade_sections.iloc[selected_section]
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric('필요 증거금', f"${section_data['총_증거금']:.2f}")
                    with col2:
                        st.metric('진입 횟수', str(section_data['매수횟수']))
                    with col3:
                        st.metric('소요 시간', section_data['소요시간'])
                    
                    st.write('### 신호별 분석')
                    signal_df = pd.DataFrame({
                        '신호': list(section_data['신호별_횟수'].keys()),
                        '횟수': list(section_data['신호별_횟수'].values()),
                        '증거금': [section_data['신호별_증거금'].get(signal, 0) for signal in section_data['신호별_횟수'].keys()]
                    })
                    st.dataframe(signal_df)
                    
                    st.write('### 상세 거래 내역')
                    detail_df = pd.DataFrame(section_data['상세거래'])
                    detail_df['누적_증거금'] = detail_df['증거금'].cumsum()
                    st.dataframe(detail_df)
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=detail_df['날짜/시간'],
                        y=detail_df['누적_증거금'],
                        mode='lines+markers',
                        name='누적 증거금'
                    ))
                    fig.update_layout(title='구간 내 누적 증거금 변화')
                    st.plotly_chart(fig)
                    
        except Exception as e:
            st.error(f'데이터 처리 중 오류가 발생했습니다: {str(e)}')

if __name__ == '__main__':
    main()
