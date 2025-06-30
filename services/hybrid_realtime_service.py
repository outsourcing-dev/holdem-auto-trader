# services/hybrid_realtime_service.py
"""
하이브리드 실시간 모니터링 서비스
- 논블로킹 서버 통신
- 실시간 웹소켓 데이터 수집
- 빠른 조건 방 탐지 및 즉시 입장
"""
import asyncio
import aiohttp
import json
import time
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from collections import deque
import threading
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication

@dataclass
class RoomCondition:
    """방 조건 데이터"""
    room_name: str
    streak_count: int
    last_results: List[str]
    confidence: float
    timestamp: float

@dataclass
class ServerResponse:
    """서버 응답 데이터"""
    status: str
    room_recommendations: List[RoomCondition]
    should_enter: bool
    message: str = ""

class HybridRealtimeService(QObject):
    """하이브리드 실시간 모니터링 서비스"""
    
    # Qt 시그널 정의
    room_found = pyqtSignal(str, int, float)  # room_name, streak_count, confidence
    enter_room_now = pyqtSignal(str)  # room_name
    monitoring_status_changed = pyqtSignal(bool)  # is_active
    error_occurred = pyqtSignal(str)  # error_message
    
    def __init__(self, server_client, user_id: str, logger=None):
        super().__init__()
        self.logger = logger or logging.getLogger(__name__)
        self.server_client = server_client
        self.user_id = user_id
        
        # 상태 관리
        self.is_monitoring = False
        self.websocket_url = None
        self.session = None
        self.monitoring_task = None
        
        # 데이터 버퍼 (논블로킹 처리용)
        self.data_buffer = deque(maxlen=100)
        self.pending_requests = {}  # request_id -> timestamp
        self.response_queue = deque(maxlen=50)
        
        # 타이밍 설정
        self.batch_send_interval = 0.5  # 500ms마다 배치 전송
        self.response_check_interval = 0.3  # 300ms마다 응답 체크
        self.cleanup_interval = 5.0  # 5초마다 타임아웃 정리
        
        # 스레드 풀
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="hybrid")
        
        # 비동기 이벤트 루프
        self.loop = None
        self.loop_thread = None
        
        # Qt 타이머들
        self.response_timer = QTimer()
        self.response_timer.timeout.connect(self._check_server_responses)
        
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self._cleanup_expired_requests)

    async def start_monitoring(self, websocket_url: str) -> bool:
        """하이브리드 모니터링 시작"""
        try:
            self.websocket_url = websocket_url
            self.logger.info("🚀 하이브리드 실시간 모니터링 시작")
            
            # 비동기 세션 생성
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=aiohttp.TCPConnector(
                    limit=10,
                    limit_per_host=5,
                    keepalive_timeout=30
                )
            )
            
            # 서버에 웹소켓 설정 전송
            if not await self._send_websocket_config():
                return False
            
            # 모니터링 태스크 시작
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            # Qt 타이머 시작
            self.response_timer.start(int(self.response_check_interval * 1000))
            self.cleanup_timer.start(int(self.cleanup_interval * 1000))
            
            self.is_monitoring = True
            self.monitoring_status_changed.emit(True)
            
            self.logger.info("✅ 하이브리드 모니터링 시작 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"모니터링 시작 실패: {e}")
            self.error_occurred.emit(f"모니터링 시작 실패: {str(e)}")
            return False

    async def stop_monitoring(self):
        """모니터링 중지"""
        try:
            self.is_monitoring = False
            self.logger.info("하이브리드 모니터링 중지 중...")
            
            # Qt 타이머 중지
            self.response_timer.stop()
            self.cleanup_timer.stop()
            
            # 모니터링 태스크 취소
            if self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            # 세션 정리
            if self.session and not self.session.closed:
                await self.session.close()
            
            # 버퍼 정리
            self.data_buffer.clear()
            self.pending_requests.clear()
            self.response_queue.clear()
            
            self.monitoring_status_changed.emit(False)
            self.logger.info("하이브리드 모니터링 중지 완료")
            
        except Exception as e:
            self.logger.error(f"모니터링 중지 중 오류: {e}")

    async def _send_websocket_config(self) -> bool:
        """서버에 웹소켓 설정 전송"""
        try:
            config_data = self._extract_websocket_config()
            if not config_data:
                return False
            
            payload = {
                "user_id": self.user_id,
                "websocket_config": config_data,
                "monitoring_mode": "hybrid"
            }
            
            async with self.session.post(
                f"{self.server_client.base_url}/api/baccarat/config",
                json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("status") == "success":
                        self.logger.info("웹소켓 설정 전송 성공")
                        return True
                
                self.logger.error(f"웹소켓 설정 전송 실패: {response.status}")
                return False
                
        except Exception as e:
            self.logger.error(f"웹소켓 설정 전송 오류: {e}")
            return False

    def _extract_websocket_config(self) -> Optional[Dict]:
        """웹소켓 URL에서 설정 정보 추출"""
        try:
            from urllib.parse import urlparse, parse_qs
            
            parsed_url = urlparse(self.websocket_url)
            query_params = parse_qs(parsed_url.query)
            
            config = {
                "session_id": query_params.get('EVOSESSIONID', [''])[0],
                "bare_session_id": parsed_url.path.split('/')[-1],
                "instance": query_params.get('instance', [''])[0].split('-')[0],
                "client_version": query_params.get('client_version', [''])[0]
            }
            
            if all(config.values()):
                return config
            else:
                self.logger.error("웹소켓 설정 추출 실패")
                return None
                
        except Exception as e:
            self.logger.error(f"웹소켓 설정 추출 오류: {e}")
            return None

    async def _monitoring_loop(self):
        """메인 모니터링 루프"""
        self.logger.info("🔄 모니터링 루프 시작")
        
        last_batch_send = 0
        last_status_log = 0
        
        try:
            while self.is_monitoring:
                current_time = time.time()
                
                # 배치 데이터 전송 (논블로킹)
                if current_time - last_batch_send >= self.batch_send_interval:
                    if self.data_buffer:
                        asyncio.create_task(self._send_batch_data())
                        last_batch_send = current_time
                
                # 상태 로그 (10초마다)
                if current_time - last_status_log >= 10:
                    self._log_monitoring_status()
                    last_status_log = current_time
                
                # 짧은 대기 (논블로킹 유지)
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            self.logger.info("모니터링 루프 취소됨")
        except Exception as e:
            self.logger.error(f"모니터링 루프 오류: {e}")
            self.error_occurred.emit(f"모니터링 오류: {str(e)}")

    async def _send_batch_data(self):
        """배치 데이터 비동기 전송 (논블로킹)"""
        if not self.data_buffer or not self.session:
            return
            
        try:
            # 버퍼에서 데이터 추출 (최대 20개)
            batch_data = []
            for _ in range(min(20, len(self.data_buffer))):
                if self.data_buffer:
                    batch_data.append(self.data_buffer.popleft())
            
            if not batch_data:
                return
            
            # 요청 ID 생성
            request_id = f"batch_{int(time.time() * 1000)}"
            
            payload = {
                "request_id": request_id,
                "user_id": self.user_id,
                "batch_data": batch_data,
                "timestamp": time.time()
            }
            
            # 요청 기록 (타임아웃 관리용)
            self.pending_requests[request_id] = time.time()
            
            # 비동기 전송 (응답 대기하지 않음)
            asyncio.create_task(self._send_data_no_wait(payload))
            
            self.logger.debug(f"배치 데이터 전송: {len(batch_data)}개 (ID: {request_id})")
            
        except Exception as e:
            self.logger.warning(f"배치 데이터 전송 오류: {e}")

    async def _send_data_no_wait(self, payload: Dict):
        """데이터 전송 (응답 대기 없음)"""
        try:
            async with self.session.post(
                f"{self.server_client.base_url}/api/baccarat/realtime-data",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                # 응답을 큐에 저장 (메인 스레드에서 처리)
                if response.status == 200:
                    result = await response.json()
                    self.response_queue.append({
                        "request_id": payload["request_id"],
                        "response": result,
                        "timestamp": time.time()
                    })
                
        except asyncio.TimeoutError:
            self.logger.debug(f"요청 타임아웃: {payload.get('request_id')}")
        except Exception as e:
            self.logger.debug(f"데이터 전송 오류: {e}")

    def _check_server_responses(self):
        """서버 응답 체크 (Qt 타이머에서 호출)"""
        try:
            processed_count = 0
            
            while self.response_queue and processed_count < 10:
                response_data = self.response_queue.popleft()
                self._process_server_response(response_data)
                processed_count += 1
                
                # UI 블로킹 방지
                QApplication.processEvents()
            
        except Exception as e:
            self.logger.error(f"응답 체크 오류: {e}")

    def _process_server_response(self, response_data: Dict):
        """서버 응답 처리"""
        try:
            request_id = response_data["request_id"]
            response = response_data["response"]
            
            # 요청 기록에서 제거
            self.pending_requests.pop(request_id, None)
            
            # 응답 처리
            if response.get("status") == "success":
                self._handle_successful_response(response)
            else:
                self.logger.debug(f"서버 응답 오류: {response.get('message')}")
                
        except Exception as e:
            self.logger.error(f"응답 처리 오류: {e}")

    def _handle_successful_response(self, response: Dict):
        """성공적인 응답 처리"""
        try:
            # 방 추천이 있는 경우
            recommendations = response.get("room_recommendations", [])
            
            for rec in recommendations:
                room_name = rec.get("room_name", "")
                streak_count = rec.get("streak_count", 0)
                confidence = rec.get("confidence", 0.0)
                
                if confidence > 0.8:  # 높은 신뢰도
                    self.logger.info(f"🎯 고신뢰도 방 발견: {room_name} (연패: {streak_count}, 신뢰도: {confidence:.2f})")
                    self.room_found.emit(room_name, streak_count, confidence)
                    
                    # 즉시 입장 조건
                    if confidence > 0.9 and streak_count >= 3:
                        self.logger.info(f"🚀 즉시 입장 신호: {room_name}")
                        self.enter_room_now.emit(room_name)
            
            # 기타 서버 지시사항 처리
            if response.get("action") == "ENTER_ROOM_NOW":
                target_room = response.get("room_name", "")
                if target_room:
                    self.enter_room_now.emit(target_room)
                    
        except Exception as e:
            self.logger.error(f"응답 처리 오류: {e}")

    def _cleanup_expired_requests(self):
        """만료된 요청들 정리 (Qt 타이머에서 호출)"""
        try:
            current_time = time.time()
            expired_requests = []
            
            for request_id, timestamp in self.pending_requests.items():
                if current_time - timestamp > 10:  # 10초 타임아웃
                    expired_requests.append(request_id)
            
            for request_id in expired_requests:
                self.pending_requests.pop(request_id, None)
            
            if expired_requests:
                self.logger.debug(f"만료된 요청 정리: {len(expired_requests)}개")
                
        except Exception as e:
            self.logger.error(f"요청 정리 오류: {e}")

    def _log_monitoring_status(self):
        """모니터링 상태 로깅"""
        try:
            status = {
                "버퍼_크기": len(self.data_buffer),
                "대기중_요청": len(self.pending_requests),
                "응답_큐": len(self.response_queue),
                "세션_상태": "활성" if self.session and not self.session.closed else "비활성"
            }
            
            self.logger.info(f"📊 모니터링 상태: {status}")
            
        except Exception as e:
            self.logger.debug(f"상태 로깅 오류: {e}")

    def add_room_data(self, room_data: Dict):
        """방 데이터 추가 (웹소켓에서 받은 데이터)"""
        try:
            if self.is_monitoring and len(self.data_buffer) < 100:
                enriched_data = {
                    **room_data,
                    "timestamp": time.time(),
                    "user_id": self.user_id
                }
                self.data_buffer.append(enriched_data)
                
        except Exception as e:
            self.logger.error(f"방 데이터 추가 오류: {e}")

    def get_monitoring_stats(self) -> Dict:
        """모니터링 통계 반환"""
        return {
            "is_monitoring": self.is_monitoring,
            "buffer_size": len(self.data_buffer),
            "pending_requests": len(self.pending_requests),
            "response_queue_size": len(self.response_queue),
            "session_active": self.session and not self.session.closed if self.session else False
        }

    async def request_immediate_analysis(self, room_name: str) -> Optional[Dict]:
        """특정 방에 대한 즉시 분석 요청"""
        try:
            if not self.session:
                return None
            
            payload = {
                "user_id": self.user_id,
                "room_name": room_name,
                "analysis_type": "immediate",
                "timestamp": time.time()
            }
            
            async with self.session.post(
                f"{self.server_client.base_url}/api/baccarat/immediate-analysis",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=3)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.logger.info(f"즉시 분석 결과: {room_name}")
                    return result
                
                return None
                
        except Exception as e:
            self.logger.error(f"즉시 분석 요청 오류: {e}")
            return None

    def __del__(self):
        """소멸자"""
        try:
            if self.executor:
                self.executor.shutdown(wait=False)
        except:
            pass