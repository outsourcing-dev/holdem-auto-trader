import os
from datetime import datetime

def log_bet_to_file(bet_info: dict):
    desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
    log_file = os.path.join(desktop_path, 'betting_log.txt')

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if 'result' in bet_info:
        log_message = (
            f"[{timestamp}] 방:{bet_info['room']} | "
            f"예측:{bet_info['pick']} | 신뢰도:{bet_info['confidence']:.4f} | "
            f"정확도:{bet_info['accuracy']:.4f} | 베팅액:{bet_info['amount']} | "
            f"결과:{bet_info['result']} | 성공여부:{'O' if bet_info['is_win'] else 'X'}\n"
        )
    else:
        log_message = f"[{timestamp}] 방:{bet_info.get('room', 'Unknown')} | 결과 정보 없음\n"

    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_message)
