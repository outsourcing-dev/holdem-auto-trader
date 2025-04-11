import os
from datetime import datetime

def log_bet_to_file(bet_info: dict):
    """
    베팅 정보를 로그 파일에 기록합니다.
    
    Args:
        bet_info: 베팅 관련 정보가 담긴 딕셔너리
    """
    desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
    log_file = os.path.join(desktop_path, 'betting_log.txt')
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 베팅 정보 포맷팅
    log_message = f"[{timestamp}] 방:{bet_info['room']} | "
    log_message += f"예측:{bet_info['pick']} | 신뢰도:{bet_info['confidence']:.4f} | "
    log_message += f"정확도:{bet_info['accuracy']:.4f} | 베팅액:{bet_info['amount']} | "
    
    # 결과가 있는 경우에만 추가
    if 'result' in bet_info:
        log_message += f"결과:{bet_info['result']} | 성공여부:{'O' if bet_info['is_win'] else 'X'}"
    
    log_message += "\n"
    
    # 파일에 로그 추가
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_message)