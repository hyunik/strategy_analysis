# 분석 함수만 수정된 버전입니다. 나머지 코드는 동일합니다.

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
