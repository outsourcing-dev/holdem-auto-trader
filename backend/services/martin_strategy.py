"""
마틴 전략 서비스
"""
import logging
from typing import List
from pathlib import Path
import json

logger = logging.getLogger(__name__)

class MartinStrategy:
    """마틴게일 베팅 전략"""
    
    def __init__(self):
        self.settings = self.load_settings()
        self.martin_amounts = self.settings.get("martin_amounts", [10000, 20000, 40000])
        self.martin_count = self.settings.get("martin_count", 3)
        
    def load_settings(self) -> dict:
        """설정 로드"""
        settings_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
        try:
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
        
        return {
            "martin_count": 3,
            "martin_amounts": [10000, 20000, 40000]
        }
    
    def get_bet_amount(self, step: int) -> int:
        """현재 마틴 단계에 따른 베팅 금액"""
        if step >= len(self.martin_amounts):
            return self.martin_amounts[-1]  # 마지막 금액
        return self.martin_amounts[step]
    
    def should_change_room(self, step: int) -> bool:
        """방 변경 여부 결정"""
        # 마틴 한계 도달 또는 승리 시
        return step >= self.martin_count or step == 0
    
    def reset(self):
        """마틴 상태 초기화"""
        # 필요시 구현
        pass