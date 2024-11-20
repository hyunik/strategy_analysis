import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

st.set_page_config(
    page_title="거래 분석기",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .big-font {
        font-size:20px !important;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

def analyze_trading_amounts(df, leverage):
    """거래 데이터 분석"""
    df = df.copy()
    df = df.iloc[::-1].reset_index(drop=True)
    
    # 신호에서 숫자 제거하고 기본 신호만 추출
    df['기본신호'] = df['신호'].str.extract(r'(롱진입|숏진입|롱%추매|숏%추매|롱R추매|숏R추매|매수)')
    
    # 엔트리 데이터만 필터링
    entries = df[df['타입'].str.contains('엔트리')].copy()
    
    # 전체 매수 신호 통계
    signal_counts = entries['기본신호'].value_counts()
    total_trades = len(entries)
    
    # 시간순으로 정렬된 매매 그룹 분석
    trade_groups = []
    current_group = None
    current_contracts = 0
    current_amount = 0
    current_signals = []
    max_drawdown = 0
    max_runup = 0
    
    for idx, row in entries.iterrows():
        is_new_group = (current_group is None or 
                       (row['기본신호'] in ['롱진입', '롱%추매', '롱R추매', '매수'] and current_group.get('포지션') != 'long') or
                       (row['기본신호'] in ['숏진입', '숏%추매', '숏R추매'] and current_group.get('포지션') != 'short'))
        
        if is_new_group:
            if current_group is not None:
                trade_groups.append({
                    '시작시간': current_group['시작시간'],
                    '종료시간': prev_row['날짜/시간'],
                    '계약수': current_contracts,
                    '필요증거금': current_amount,
                    '신호목록': current_signals,
                    '시작가격': current_group['시작가격'],
                    '최대손실': max_drawdown,
                    '최대이익': max_runup,
                    '매수횟수': len(current_signals),
                    '포지션': current_group['포지션']
                })
            
            current_group = {
                '시작시간': row['날짜/시간'],
                '시작가격': row['가격 USDT'],
                '포지션': 'long' if row['기본신호'] in ['롱진입', '롱%추매', '롱R추매', '매수'] else 'short'
            }
            current_contracts = row['계약']
            current_amount = row['계약'] * row['가격 USDT'] / leverage
            current_signals = [row['기본신호']]
            max_drawdown = 0
            max_runup = 0
        else:
            current_contracts += row['계약']
            current_amount += row['계약'] * row['가격 USDT'] / leverage
            current_signals.append(row['기본신호'])
            
            price_change = row['가격 USDT'] - current_group['시작가격']
            if current_group['포지션'] == 'short':
                price_change = -price_change
                
            if price_change > 0:
                max_runup = max(max_runup, price_change * current_contracts)
            else:
                max_drawdown = min(max_drawdown, price_change * current_contracts)
        
        prev_row = row
    
    if current_group is not None:
        trade_groups.append({
            '시작시간': current_group['시작시간'],
            '종료시간': prev_row['날짜/시간'],
            '계약수': current_contracts,
            '필요증거금': current_amount,
            '신호목록': current_signals,
            '시작가격': current_group['시작가격'],
            '최대손실': max_drawdown,
            '최대이익': max_runup,
            '매수횟수': len(current_signals),
            '포지션': current_group['포지션']
        })
    
    results_df = pd.DataFrame(trade_groups)
    
    return results_df, signal_counts, total_trades


def create_margin_timeline(results_df):
    """증거금 변화 시각화"""
    fig = go.Figure()
    
    # 롱/숏 포지션별로 다른 색상 사용
    colors = {'long': 'rgba(99, 110, 250, 0.8)', 'short': 'rgba(239, 85, 59, 0.8)'}
    
    for position in ['long', 'short']:
        position_df = results_df[results_df['포지션'] == position]
        
        if len(position_df) > 0:
            fig.add_trace(go.Scatter(
                x=position_df['시작시간'],
                y=position_df['필요증거금'],
                mode='lines+markers',
                name=f"{'롱' if position == 'long' else '숏'} 포지션",
                marker=dict(size=8),
                line=dict(color=colors[position]),
                hovertemplate='시간: %{x}<br>필요증거금: %{y:.2f} USDT<br>매수횟수: %{text}<br>포지션: ' + 
                            ('롱' if position == 'long' else '숏') + '<extra></extra>',
                text=position_df['매수횟수']
            ))
    
    fig.update_layout(
        title='시간별 필요증거금 변화',
        xaxis_title='시간',
        yaxis_title='필요증거금 (USDT)',
        hovermode='x unified'
    )
    
    return fig

def create_trade_counts_chart(signal_counts):
    """매수 신호별 횟수 시각화"""
    fig = go.Figure(data=[
        go.Bar(
            x=signal_counts.index,
            y=signal_counts.values,
            text=signal_counts.values,
            textposition='auto',
            marker_color=['rgba(99, 110, 250, 0.8)' if '롱' in x else 'rgba(239, 85, 59, 0.8)' 
                         for x in signal_counts.index]
        )
    ])
    
    fig.update_layout(
        title='매매 신호별 횟수',
        xaxis_title='매매 신호',
        yaxis_title='횟수',
        showlegend=False
    )
    
    return fig

def main():
    st.title("거래 분석기 📊")
    st.write("거래 데이터를 분석하여 필요 증거금과 매매 패턴을 확인해보세요.")
    
    uploaded_file = st.file_uploader(
        "거래 데이터 파일을 업로드하세요 (CSV)",
        type=['csv']
    )
    
    if uploaded_file is not None:
        leverage = st.number_input("레버리지 설정", min_value=1, max_value=100, value=10)
        
        try:
            df = pd.read_csv(uploaded_file)
            results, signal_counts, total_trades = analyze_trading_amounts(df, leverage)
            
            max_margin_point = results.loc[results['필요증거금'].idxmax()]
            max_trades_point = results.loc[results['매수횟수'].idxmax()]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("총 거래 그룹 수", f"{len(results):,}")
                st.metric("총 매매 횟수", f"{total_trades:,}")
            with col2:
                st.metric("최대 필요증거금", f"{max_margin_point['필요증거금']:.2f} USDT")
                st.metric("해당 시점 매매횟수", f"{max_margin_point['매수횟수']:,}")
            with col3:
                st.metric("최대 매매횟수", f"{max_trades_point['매수횟수']:,}")
                st.metric("해당 시점 증거금", f"{max_trades_point['필요증거금']:.2f} USDT")
            
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(create_trade_counts_chart(signal_counts), use_container_width=True)
            with col2:
                st.subheader("매매 신호별 통계")
                st.dataframe(pd.DataFrame({
                    '신호': signal_counts.index,
                    '횟수': signal_counts.values,
                    '비율': (signal_counts.values / total_trades * 100).round(2)
                }).style.format({'비율': '{:.2f}%'}))
            
            st.plotly_chart(create_margin_timeline(results), use_container_width=True)
            
            # 포지션별 상세 데이터 표시
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("최대 필요증거금 Top 10")
                st.dataframe(results.nlargest(10, '필요증거금')[
                    ['시작시간', '종료시간', '계약수', '필요증거금', '매수횟수', '신호목록', '포지션']
                ])
            with col2:
                st.subheader("최대 매수횟수 Top 10")
                st.dataframe(results.nlargest(10, '매수횟수')[
                    ['시작시간', '종료시간', '계약수', '필요증거금', '매수횟수', '신호목록', '포지션']
                ])
            
            csv = results.to_csv(index=False).encode('utf-8')
            st.download_button(
                "전체 분석 결과 다운로드 (CSV)",
                csv,
                "trade_analysis_results.csv",
                "text/csv",
                key='download-csv'
            )
            
        except Exception as e:
            st.error(f"데이터 분석 중 오류가 발생했습니다: {str(e)}")
            
    else:
        st.info("CSV 파일을 업로드하면 분석이 시작됩니다.")

if __name__ == "__main__":
    main()
