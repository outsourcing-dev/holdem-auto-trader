# utils/log_analyzer.py
import re
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class LogAnalyzer:
    """로그 자동 분석 시스템"""
    
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        self.patterns = {
            'betting_win': r'🎉 베팅 승리!',
            'betting_lose': r'❌ 베팅 패배',
            'betting_tie': r'🤝 TIE 무승부',
            'betting_amount': r'베팅.*금액: (\d+,?\d*)',
            'martin_stage': r'마틴 (\d+)단계',
            'room_exit': r'방 나가기|return_to_streak_monitoring',
            'room_entry': r'방 입장 성공: (.+)',
            'qt_error': r'invokeMethod.*unexpected type',
            'martin_reset': r'마틴.*초기화',
            'game_round': r'라운드 (\d+)',
            'betting_execution': r'베팅 시도.*금액: (\d+)'
        }
    
    def get_latest_logs(self, lines: int = 500) -> List[str]:
        """최신 로그 라인들 가져오기"""
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return all_lines[-lines:] if len(all_lines) > lines else all_lines
        except Exception as e:
            print(f"로그 파일 읽기 오류: {e}")
            return []
    
    def analyze_betting_sequence(self, logs: List[str]) -> Dict:
        """베팅 시퀀스 분석"""
        results = {
            'betting_events': [],
            'martin_issues': [],
            'room_transitions': [],
            'qt_errors': [],
            'anomalies': []
        }
        
        current_betting = None
        
        for i, line in enumerate(logs):
            timestamp = self._extract_timestamp(line)
            
            # 베팅 시작 감지
            if '베팅 시도' in line:
                amount_match = re.search(r'금액: (\d+)', line)
                round_match = re.search(r'게임: (\d+)', line)
                
                current_betting = {
                    'timestamp': timestamp,
                    'line_num': i,
                    'amount': int(amount_match.group(1)) if amount_match else 0,
                    'round': int(round_match.group(1)) if round_match else 0,
                    'result': None,
                    'martin_stage': None
                }
            
            # 마틴 단계 감지
            martin_match = re.search(r'마틴 (\d+)단계', line)
            if martin_match and current_betting:
                current_betting['martin_stage'] = int(martin_match.group(1))
            
            # 베팅 결과 감지
            if current_betting:
                if '베팅 승리' in line:
                    current_betting['result'] = 'WIN'
                    results['betting_events'].append(current_betting.copy())
                    
                    # 승리 후 마틴 초기화 확인
                    next_lines = logs[i:i+10]  # 다음 10줄 확인
                    if any('마틴.*초기화' in next_line for next_line in next_lines):
                        if not any('방 나가기' in next_line for next_line in next_lines):
                            results['anomalies'].append({
                                'type': 'WIN_NO_ROOM_EXIT',
                                'timestamp': timestamp,
                                'line': i,
                                'description': '승리 후 방 나가기 없음'
                            })
                    
                    current_betting = None
                    
                elif '베팅 패배' in line or 'TIE 무승부' in line:
                    current_betting['result'] = 'LOSE' if '베팅 패배' in line else 'TIE'
                    results['betting_events'].append(current_betting.copy())
                    current_betting = None
            
            # Qt 오류 감지
            if 'invokeMethod' in line and 'unexpected type' in line:
                results['qt_errors'].append({
                    'timestamp': timestamp,
                    'line': i,
                    'description': 'Qt invokeMethod 오류'
                })
            
            # 방 전환 감지
            if '방 입장 성공' in line:
                room_match = re.search(r'방 입장 성공: (.+)', line)
                results['room_transitions'].append({
                    'timestamp': timestamp,
                    'line': i,
                    'type': 'ENTRY',
                    'room': room_match.group(1) if room_match else 'Unknown'
                })
            
            if '방 나가기' in line or 'return_to_streak_monitoring' in line:
                results['room_transitions'].append({
                    'timestamp': timestamp,
                    'line': i,
                    'type': 'EXIT'
                })
        
        return results
    
    def check_martin_progression(self, betting_events: List[Dict]) -> List[Dict]:
        """마틴게일 진행 검증"""
        issues = []
        
        for i in range(1, len(betting_events)):
            prev_bet = betting_events[i-1]
            curr_bet = betting_events[i]
            
            # 승리 후 마틴 초기화 확인
            if prev_bet['result'] == 'WIN':
                expected_amount = 10000  # 1단계 금액
                if curr_bet['amount'] != expected_amount:
                    issues.append({
                        'type': 'MARTIN_NOT_RESET_AFTER_WIN',
                        'prev_bet': prev_bet,
                        'curr_bet': curr_bet,
                        'expected': expected_amount,
                        'actual': curr_bet['amount']
                    })
            
            # 패배 후 마틴 증가 확인
            elif prev_bet['result'] == 'LOSE':
                # 마틴 단계별 금액 매핑
                martin_amounts = {1: 10000, 2: 20000, 3: 40000}
                expected_stage = (prev_bet.get('martin_stage', 1) or 1) + 1
                
                if expected_stage <= 3:
                    expected_amount = martin_amounts[expected_stage]
                    if curr_bet['amount'] != expected_amount:
                        issues.append({
                            'type': 'MARTIN_WRONG_PROGRESSION',
                            'prev_bet': prev_bet,
                            'curr_bet': curr_bet,
                            'expected_stage': expected_stage,
                            'expected_amount': expected_amount,
                            'actual_amount': curr_bet['amount']
                        })
        
        return issues
    
    def _extract_timestamp(self, line: str) -> str:
        """로그 라인에서 타임스탬프 추출"""
        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
        return match.group(1) if match else ''
    
    def generate_report(self) -> str:
        """분석 보고서 생성"""
        logs = self.get_latest_logs(1000)  # 최근 1000줄 분석
        analysis = self.analyze_betting_sequence(logs)
        martin_issues = self.check_martin_progression(analysis['betting_events'])
        
        report = []
        report.append("=== 로그 자동 분석 보고서 ===")
        report.append(f"분석 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"분석 로그 라인 수: {len(logs)}")
        report.append("")
        
        # 베팅 이벤트 요약
        betting_events = analysis['betting_events']
        if betting_events:
            wins = len([b for b in betting_events if b['result'] == 'WIN'])
            losses = len([b for b in betting_events if b['result'] == 'LOSE'])
            ties = len([b for b in betting_events if b['result'] == 'TIE'])
            
            report.append("[베팅 통계]")
            report.append(f"  - 총 베팅: {len(betting_events)}회")
            report.append(f"  - 승리: {wins}회, 패배: {losses}회, 무승부: {ties}회")
            if wins + losses > 0:
                win_rate = wins / (wins + losses) * 100
                report.append(f"  - 승률: {win_rate:.1f}%")
            report.append("")
        
        # 마틴게일 문제점
        if martin_issues:
            report.append("[마틴게일 진행 문제점]")
            for issue in martin_issues[-5:]:  # 최근 5개만
                if issue['type'] == 'MARTIN_NOT_RESET_AFTER_WIN':
                    report.append(f"  - 승리 후 마틴 미초기화: {issue['actual']:,}원 (예상: {issue['expected']:,}원)")
                elif issue['type'] == 'MARTIN_WRONG_PROGRESSION':
                    report.append(f"  - 잘못된 마틴 진행: {issue['actual_amount']:,}원 (예상: {issue['expected_amount']:,}원)")
            report.append("")
        
        # 이상 징후
        anomalies = analysis['anomalies']
        if anomalies:
            report.append("[이상 징후]")
            for anomaly in anomalies[-5:]:  # 최근 5개만
                report.append(f"  - {anomaly['description']} ({anomaly['timestamp']})")
            report.append("")
        
        # Qt 오류
        if analysis['qt_errors']:
            report.append(f"[Qt 오류] {len(analysis['qt_errors'])}건")
            report.append("")
        
        # 방 전환 통계
        room_transitions = analysis['room_transitions']
        entries = len([r for r in room_transitions if r['type'] == 'ENTRY'])
        exits = len([r for r in room_transitions if r['type'] == 'EXIT'])
        report.append(f"[방 전환] 입장 {entries}회, 나가기 {exits}회")
        
        if entries != exits:
            report.append(f"  [경고] 입장/나가기 불균형: {entries - exits}")
        
        return "\n".join(report)
    
    def save_report(self, report: str, filename: Optional[str] = None):
        """보고서 파일로 저장"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"log_analysis_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"분석 보고서 저장됨: {filename}")
        except Exception as e:
            print(f"보고서 저장 오류: {e}")

def analyze_current_log():
    """현재 로그 파일 분석 실행"""
    log_path = "C:\\Users\\user\\Desktop\\holdem-auto-trader\\log.txt"
    
    if not os.path.exists(log_path):
        print(f"로그 파일을 찾을 수 없습니다: {log_path}")
        return
    
    analyzer = LogAnalyzer(log_path)
    report = analyzer.generate_report()
    
    print(report)
    print("\n" + "="*50)
    
    # 보고서 저장
    analyzer.save_report(report)
    
    return report

if __name__ == "__main__":
    analyze_current_log()