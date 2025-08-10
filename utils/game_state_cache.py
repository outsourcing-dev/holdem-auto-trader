# utils/game_state_cache.py
"""
중앙 게임 상태 캐시 관리자
여러 컴포넌트에서 게임 상태를 반복 조회하는 문제를 해결
"""

import time
import logging
from typing import Dict, Any, Optional, Callable


class GameStateCache:
    """중앙 게임 상태 캐시 - 중복 조회 방지 및 성능 최적화"""
    
    def __init__(self, default_timeout: float = 0.4, logger=None):
        """
        Args:
            default_timeout: 기본 캐시 타임아웃 (초)
            logger: 로거 인스턴스
        """
        self.cache = {}  # {room_id: (game_state, timestamp)}
        self.default_timeout = default_timeout
        self.logger = logger or logging.getLogger(__name__)
        
        # 통계
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_fetches = 0
        
    def get_or_fetch(self, room_id: str, fetch_func: Callable, 
                     timeout: Optional[float] = None, **fetch_kwargs) -> Optional[Dict[str, Any]]:
        """
        캐시에서 게임 상태를 가져오거나 없으면 fetch 함수 호출
        
        Args:
            room_id: 방 ID
            fetch_func: 게임 상태를 가져오는 함수
            timeout: 캐시 타임아웃 (None이면 default 사용)
            **fetch_kwargs: fetch_func에 전달할 추가 인자
            
        Returns:
            게임 상태 딕셔너리 또는 None
        """
        current_time = time.time()
        timeout = timeout or self.default_timeout
        
        # 캐시 확인
        if self.is_valid(room_id, timeout, current_time):
            self.cache_hits += 1
            cached_state, _ = self.cache[room_id]
            self.logger.debug(f"✅ 캐시 히트: room_id={room_id}, hits={self.cache_hits}")
            return cached_state
        
        # 캐시 미스 - fetch 실행
        self.cache_misses += 1
        self.total_fetches += 1
        
        try:
            self.logger.debug(f"🔄 캐시 미스 - 데이터 fetch: room_id={room_id}")
            game_state = fetch_func(**fetch_kwargs)
            
            if game_state:
                # 캐시 업데이트
                self.cache[room_id] = (game_state, current_time)
                self.logger.debug(f"📝 캐시 업데이트: room_id={room_id}")
            
            return game_state
            
        except Exception as e:
            self.logger.error(f"게임 상태 fetch 오류: {e}")
            return None
    
    def is_valid(self, room_id: str, timeout: Optional[float] = None, 
                 current_time: Optional[float] = None) -> bool:
        """
        캐시가 유효한지 확인
        
        Args:
            room_id: 방 ID
            timeout: 타임아웃 (None이면 default 사용)
            current_time: 현재 시간 (None이면 새로 측정)
            
        Returns:
            캐시가 유효하면 True
        """
        if room_id not in self.cache:
            return False
        
        _, timestamp = self.cache[room_id]
        current_time = current_time or time.time()
        timeout = timeout or self.default_timeout
        
        return (current_time - timestamp) < timeout
    
    def invalidate(self, room_id: Optional[str] = None):
        """
        캐시 무효화
        
        Args:
            room_id: 특정 방의 캐시만 무효화 (None이면 전체)
        """
        if room_id:
            if room_id in self.cache:
                del self.cache[room_id]
                self.logger.debug(f"🗑️ 캐시 무효화: room_id={room_id}")
        else:
            self.cache.clear()
            self.logger.debug("🗑️ 전체 캐시 무효화")
    
    def update(self, room_id: str, game_state: Dict[str, Any]):
        """
        캐시 직접 업데이트
        
        Args:
            room_id: 방 ID
            game_state: 게임 상태
        """
        self.cache[room_id] = (game_state, time.time())
        self.logger.debug(f"📝 캐시 직접 업데이트: room_id={room_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        캐시 통계 반환
        
        Returns:
            통계 정보 딕셔너리
        """
        hit_rate = 0
        if self.cache_hits + self.cache_misses > 0:
            hit_rate = self.cache_hits / (self.cache_hits + self.cache_misses) * 100
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'total_fetches': self.total_fetches,
            'cached_rooms': len(self.cache)
        }
    
    def log_stats(self):
        """캐시 통계 로깅"""
        stats = self.get_stats()
        self.logger.info(f"📊 캐시 통계: {stats}")
    
    def cleanup_old_entries(self, max_age: float = 60.0):
        """
        오래된 캐시 엔트리 정리
        
        Args:
            max_age: 최대 보관 시간 (초)
        """
        current_time = time.time()
        rooms_to_remove = []
        
        for room_id, (_, timestamp) in self.cache.items():
            if current_time - timestamp > max_age:
                rooms_to_remove.append(room_id)
        
        for room_id in rooms_to_remove:
            del self.cache[room_id]
        
        if rooms_to_remove:
            self.logger.debug(f"🧹 오래된 캐시 정리: {len(rooms_to_remove)}개 엔트리")