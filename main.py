import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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

def is_matching_signal(signal, strategy):
    if strategy == 'ATM':
        return signal in ['매수', 'E추매', '바닥', '%추매', '동적긴급추매']
    elif strategy == 'BRM':
        return signal in ['매수', '추매']
    elif strategy == 'ALL_KILL':
        return any(['롱진입' in signal, '숏진입' in signal]) or \
               any(['추매' in signal and ('롱' in signal or '숏' in signal)])
    return False

def is_entry_signal(signal, strategy):
    if strategy == 'ALL_KILL':
        return '롱진입' in signal or '숏진입' in signal
    return signal == '매수'

def calculate_margin_requirements(df, leverage, strategy):
    # 진입 포지션 찾기
    buy_positions = df[df['신호'].apply(lambda x: is_entry_signal(x, strategy))].index.tolist()
    if not buy_positions:  # 진입 포지션이 없는 경우
        return pd.DataFrame()  # 빈 데이터프레임 반환
        
    trade_sections = []
    
    for i, start_pos in enumerate(buy_positions):
        end_pos = buy_positions[i + 1] if i < len(buy_positions) - 1 else len(df)
        section_df = df.iloc[start_pos:end_pos].copy()
        
        section_entries = section_df[section_df['신호'].apply(lambda x: is_matching_signal(x, strategy))].copy()
        exit_trade = section_df.iloc[-1]
        
        # 증거금 계산
        section_entries['증거금'] = (section_entries['가격 USDT'] * section_entries['계약']) / leverage
        time_to_exit = calculate_time_difference(
            section_entries.iloc[0]['날짜/시간'],
            exit_trade['날짜/시간']
        )
        
        # 포지션 방향 확인 (ALL KILL 전략용)
        position_type = section_entries.iloc[0]['신호']
        
        trade_info = {
            '시작시간': section_entries.iloc[0]['날짜/시간'],
            '종료시간': exit_trade['날짜/시간'],
            '거래 #': section_entries.iloc[0]['거래 #'],
            '포지션': position_type,
            '총_증거금': section_entries['증거금'].sum(),
            '매수횟수': len(section_entries),
            '청산종류': exit_trade['신호'],
            '소요시간': time_to_exit,
            '신호별_횟수': section_entries['신호'].value_counts().to_dict(),
            '상세거래': section_entries[['날짜/시간', '신호', '가격 USDT', '계약', '증거금']].to_dict('records')
        }
        trade_sections.append(trade_info)
    
    return pd.DataFrame(trade_sections)

def main():
    st.title('최대 필요 증거금 분석기')
    
    st.sidebar.header('설정')
    strategy = st.sidebar.selectbox('전략 선택', ['ATM', 'BRM', 'ALL_KILL'])
    leverage = st.sidebar.number_input('레버리지 설정', min_value=1, value=20, step=1)
    
    # ALL_KILL 전략 선택 시 안내 메시지 표시
    if strategy == 'ALL_KILL':
        st.sidebar.info('ALL_KILL 전략은 롱/숏 포지션과 %추매/R추매를 분석합니다.')
    
    uploaded_file = st.file_uploader("거래 데이터 CSV 파일을 업로드하세요", type=['csv'])
    
    if uploaded_file is not None:
        try:
            df = load_data(uploaded_file)
            
            if df is not None:
                trade_sections = calculate_margin_requirements(df, leverage, strategy)
                
                if trade_sections.empty:
                    st.warning('분석할 수 있는 거래 데이터가 없습니다.')
                    return
                    
                try:
                    max_margin_section = trade_sections.loc[trade_sections['총_증거금'].idxmax()]
                except Exception as e:
                    st.error('거래 데이터 분석 중 오류가 발생했습니다. 데이터를 확인해주세요.')
                    return
                
                # 최대 증거금 정보를 큰 숫자로 표시
                st.markdown(f"## 최대 필요 증거금: ${max_margin_section['총_증거금']:.2f}")
                
                # 주요 정보 표시
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 거래 정보")
                    st.write(f"거래 번호: #{max_margin_section['거래 #']}")
                    if strategy == 'ALL_KILL':
                        st.write(f"포지션: {max_margin_section['포지션']}")
                    st.write(f"진입 횟수: {max_margin_section['매수횟수']}회")
                    st.write(f"소요 시간: {max_margin_section['소요시간']}")
                
                with col2:
                    st.markdown("### 신호별 횟수")
                    for signal, count in max_margin_section['신호별_횟수'].items():
                        st.write(f"{signal}: {count}회")
                
                # 상세 거래 내역
                st.markdown("### 상세 거래 내역")
                detail_df = pd.DataFrame(max_margin_section['상세거래'])
                detail_df['누적_증거금'] = detail_df['증거금'].cumsum()
                st.dataframe(detail_df[['날짜/시간', '신호', '가격 USDT', '계약', '증거금', '누적_증거금']])
                
                # 누적 증거금 변화 그래프
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=detail_df['날짜/시간'],
                    y=detail_df['누적_증거금'],
                    mode='lines+markers',
                    name='누적 증거금'
                ))
                fig.update_layout(
                    title='최대 증거금 구간의 누적 증거금 변화',
                    yaxis_title='증거금 (USDT)',
                    showlegend=False
                )
                st.plotly_chart(fig)
                
        except Exception as e:
            st.error(f'데이터 처리 중 오류가 발생했습니다: {str(e)}')

if __name__ == '__main__':
    main()
