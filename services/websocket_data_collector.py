# services/websocket_data_collector.py
"""
실시간 웹소켓 데이터 수집 서비스
- CDP/Performance Logs에서 웹소켓 데이터 추출
- 하이브리드 서비스에 실시간 전송
- 논블로킹 처리로 UI 영향 최소화
"""
import json
import time
import logging
import threading
import asyncio
from typing import Dict, List, Optional, Callable
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication
import re

class WebSocketDataCollector(QObject):
    """웹소켓 데이터 실시간 수집 및 전송 서비스"""
    
    # Qt 신호
    data_collected = pyqtSignal(dict)  # 수집된 데이터 신호
    connection_status_changed = pyqtSignal(bool)  # 연결 상태 변경
    error_occurred = pyqtSignal(str)  # 오류 발생
    
    def __init__(self, devtools, hybrid_service=None, logger=None):
        super().__init__()
        self.logger = logger or logging.getLogger(__name__)
        self.devtools = devtools
        self.hybrid_service = hybrid_service
        
        # 수집 상태
        self.is_collecting = False
        self.last_message_id = 0
        self.websocket_connections = {}  # 웹소켓 연결 추적
        
        # 데이터 버퍼
        self.data_buffer = deque(maxlen=1000)
        self.processed_messages = set()  # 중복 메시지 방지
        
        # 스레드 풀
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ws_collector")
        
        # 타이머들
        self.collection_timer = QTimer()
        self.collection_timer.timeout.connect(self._collect_websocket_data)
        
        self.send_timer = QTimer()
        self.send_timer.timeout.connect(self._send_buffered_data)
        
        # 성능 최적화 설정
        self.collection_interval = 500  # 500ms마다 수집
        self.send_interval = 1000  # 1초마다 전송
        self.batch_size = 20  # 한 번에 처리할 로그 수
        
        self.logger.info("WebSocketDataCollector 초기화 완료")

    def start_collection(self):
        """웹소켓 데이터 수집 시작"""
        try:
            if self.is_collecting:
                self.logger.warning("이미 데이터 수집이 진행 중입니다.")
                return True
            
            # CDP 설정 확인
            if not self._setup_cdp():
                return False
            
            self.is_collecting = True
            
            # 타이머 시작
            self.collection_timer.start(self.collection_interval)
            self.send_timer.start(self.send_interval)
            
            self.connection_status_changed.emit(True)
            self.logger.info("웹소켓 데이터 수집 시작")
            
            return True
            
        except Exception as e:
            self.logger.error(f"데이터 수집 시작 실패: {e}")
            self.error_occurred.emit(f"수집 시작 실패: {str(e)}")
            return False

    def stop_collection(self):
        """웹소켓 데이터 수집 중지"""
        try:
            if not self.is_collecting:
                return
            
            self.is_collecting = False
            
            # 타이머 중지
            self.collection_timer.stop()
            self.send_timer.stop()
            
            # 남은 데이터 전송
            self._send_buffered_data()
            
            # 버퍼 정리
            self.data_buffer.clear()
            self.processed_messages.clear()
            self.websocket_connections.clear()
            
            self.connection_status_changed.emit(False)
            self.logger.info("웹소켓 데이터 수집 중지")
            
        except Exception as e:
            self.logger.error(f"데이터 수집 중지 중 오류: {e}")

    def _setup_cdp(self):
        """CDP 설정 및 활성화"""
        try:
            if not self.devtools or not self.devtools.driver:
                self.logger.error("DevTools 또는 driver가 없습니다.")
                return False
            
            # Runtime 및 Network 도메인 활성화
            try:
                self.devtools.driver.execute_cdp_cmd('Runtime.enable', {})
                self.devtools.driver.execute_cdp_cmd('Network.enable', {})
                self.logger.info("CDP Runtime 및 Network 도메인 활성화 완료")
            except Exception as e:
                self.logger.warning(f"CDP 도메인 활성화 실패 (계속 진행): {e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"CDP 설정 실패: {e}")
            return False

    def _collect_websocket_data(self):
        """웹소켓 데이터 수집 (타이머에서 호출)"""
        try:
            if not self.is_collecting:
                return
            
            # Performance 로그에서 웹소켓 메시지 수집
            self._collect_from_performance_logs()
            
            # CDP에서 Network 이벤트 수집 (가능한 경우)
            self._collect_from_network_events()
            
        except Exception as e:
            self.logger.warning(f"데이터 수집 중 오류: {e}")

    def _collect_from_performance_logs(self):
        """Performance 로그에서 웹소켓 데이터 수집"""
        try:
            # Performance 로그 가져오기
            logs = self.devtools.get_performance_logs()
            if not logs:
                return
            
            # 최근 로그만 처리 (성능 최적화)
            recent_logs = logs[-self.batch_size:] if len(logs) > self.batch_size else logs
            
            for log_entry in recent_logs:
                try:
                    self._process_performance_log(log_entry)
                except Exception as e:
                    self.logger.debug(f"로그 처리 중 오류: {e}")
                    continue
                    
        except Exception as e:
            # Performance 로그가 지원되지 않는 경우 (Chrome 137+)
            self.logger.debug(f"Performance 로그 수집 실패: {e}")

    def _process_performance_log(self, log_entry):
        """개별 Performance 로그 처리"""
        try:
            message = log_entry.get('message', {})
            if not isinstance(message, dict):
                return
            
            method = message.get('method', '')
            params = message.get('params', {})
            
            # 웹소켓 관련 이벤트만 처리
            if 'WebSocket' in method or 'webSocket' in method:
                self._handle_websocket_event(method, params, log_entry)
            elif method == 'Network.webSocketFrameReceived':
                self._handle_websocket_frame_received(params)
            elif method == 'Network.webSocketFrameSent':
                self._handle_websocket_frame_sent(params)
                
        except Exception as e:
            self.logger.debug(f"Performance 로그 처리 오류: {e}")

    def _collect_from_network_events(self):
        """CDP Network 이벤트에서 웹소켓 데이터 수집"""
        try:
            # CDP를 통한 실시간 이벤트 수집 (가능한 경우)
            # 이 부분은 브라우저 지원에 따라 다르게 동작할 수 있음
            pass
            
        except Exception as e:
            self.logger.debug(f"Network 이벤트 수집 실패: {e}")

    def _handle_websocket_event(self, method, params, log_entry):
        """웹소켓 이벤트 처리"""
        try:
            timestamp = log_entry.get('timestamp', time.time() * 1000)
            
            if method == 'Network.webSocketCreated':
                # 웹소켓 연결 생성
                request_id = params.get('requestId')
                url = params.get('url', '')
                
                if self._is_evolution_websocket(url):
                    self.websocket_connections[request_id] = {
                        'url': url,
                        'created_at': timestamp,
                        'active': True
                    }
                    self.logger.info(f"Evolution 웹소켓 연결 감지: {url}")
                    
        except Exception as e:
            self.logger.debug(f"웹소켓 이벤트 처리 오류: {e}")

    def _handle_websocket_frame_received(self, params):
        """수신된 웹소켓 프레임 처리"""
        try:
            request_id = params.get('requestId')
            response = params.get('response', {})
            
            # Evolution 웹소켓인지 확인
            if request_id not in self.websocket_connections:
                return
            
            # 페이로드 추출
            payload_data = response.get('payloadData', '')
            if not payload_data:
                return
            
            # 바카라 게임 데이터인지 확인 및 파싱
            game_data = self._parse_baccarat_data(payload_data)
            if game_data:
                self._add_to_buffer(game_data)
                
        except Exception as e:
            self.logger.debug(f"웹소켓 프레임 처리 오류: {e}")

    def _handle_websocket_frame_sent(self, params):
        """전송된 웹소켓 프레임 처리 (필요한 경우)"""
        try:
            # 클라이언트에서 서버로 보내는 메시지도 필요하면 처리
            pass
            
        except Exception as e:
            self.logger.debug(f"전송 프레임 처리 오류: {e}")

    def _is_evolution_websocket(self, url):
        """Evolution 웹소켓인지 확인"""
        try:
            if not url:
                return False
            
            url_lower = url.lower()
            evolution_keywords = [
                'evo-games.com',
                'evolution',
                'lobby',
                'baccarat'
            ]
            
            return any(keyword in url_lower for keyword in evolution_keywords)
            
        except Exception as e:
            self.logger.debug(f"Evolution 웹소켓 확인 오류: {e}")
            return False

    def _parse_baccarat_data(self, payload_data):
        """바카라 게임 데이터 파싱"""
        try:
            # JSON 파싱 시도
            if payload_data.startswith('{') or payload_data.startswith('['):
                data = json.loads(payload_data)
            else:
                # 다른 형식의 데이터인 경우 텍스트 파싱
                data = self._parse_text_payload(payload_data)
            
            if not data:
                return None
            
            # 바카라 게임 관련 데이터인지 확인
            if self._is_baccarat_game_data(data):
                return self._extract_room_data(data)
            
            return None
            
        except json.JSONDecodeError:
            # JSON이 아닌 경우 텍스트 파싱 시도
            return self._parse_text_payload(payload_data)
        except Exception as e:
            self.logger.debug(f"데이터 파싱 오류: {e}")
            return None

    def _parse_text_payload(self, payload_data):
        """텍스트 형태의 페이로드 파싱"""
        try:
            # 바카라 게임 관련 키워드 검색
            baccarat_keywords = ['baccarat', 'player', 'banker', 'tie', 'game_result']
            
            if not any(keyword in payload_data.lower() for keyword in baccarat_keywords):
                return None
            
            # 간단한 패턴 매칭으로 데이터 추출
            room_pattern = r'room[_\s]*name["\s:]*([^,"\s]+)'
            result_pattern = r'result["\s:]*([PBT])'
            round_pattern = r'round["\s:]*(\d+)'
            
            room_match = re.search(room_pattern, payload_data, re.IGNORECASE)
            result_match = re.search(result_pattern, payload_data, re.IGNORECASE)
            round_match = re.search(round_pattern, payload_data, re.IGNORECASE)
            
            if room_match:
                return {
                    'room_name': room_match.group(1),
                    'latest_result': result_match.group(1) if result_match else None,
                    'round': int(round_match.group(1)) if round_match else None,
                    'timestamp': time.time(),
                    'source': 'websocket_text'
                }
            
            return None
            
        except Exception as e:
            self.logger.debug(f"텍스트 파싱 오류: {e}")
            return None

    def _is_baccarat_game_data(self, data):
        """바카라 게임 데이터인지 확인"""
        try:
            if not isinstance(data, dict):
                return False
            
            # 바카라 게임 데이터 특성 확인
            baccarat_indicators = [
                'game_type',
                'table_id',
                'room_name',
                'game_result',
                'player_cards',
                'banker_cards',
                'baccarat'
            ]
            
            data_str = str(data).lower()
            return any(indicator in data_str for indicator in baccarat_indicators)
            
        except Exception as e:
            self.logger.debug(f"바카라 데이터 확인 오류: {e}")
            return False

    def _extract_room_data(self, data):
        """방 데이터 추출"""
        try:
            room_data = {
                'timestamp': time.time(),
                'source': 'websocket_json',
                'raw_data': data
            }
            
            # 다양한 키 이름으로 데이터 추출 시도
            possible_keys = {
                'room_name': ['room_name', 'table_name', 'table_id', 'roomName'],
                'latest_result': ['result', 'game_result', 'outcome', 'winner'],
                'round': ['round', 'game_number', 'round_number', 'gameNumber'],
                'player_cards': ['player_cards', 'playerCards', 'player'],
                'banker_cards': ['banker_cards', 'bankerCards', 'banker']
            }
            
            for target_key, source_keys in possible_keys.items():
                for source_key in source_keys:
                    if source_key in data:
                        room_data[target_key] = data[source_key]
                        break
            
            # 필수 데이터가 있는지 확인
            if 'room_name' in room_data or 'latest_result' in room_data:
                return room_data
            
            return None
            
        except Exception as e:
            self.logger.debug(f"방 데이터 추출 오류: {e}")
            return None

    def _add_to_buffer(self, game_data):
        """수집된 데이터를 버퍼에 추가"""
        try:
            # 중복 데이터 방지
            data_hash = hash(str(sorted(game_data.items())))
            if data_hash in self.processed_messages:
                return
            
            self.processed_messages.add(data_hash)
            
            # 오래된 해시 정리 (메모리 효율성)
            if len(self.processed_messages) > 1000:
                # 최근 500개만 유지
                recent_hashes = list(self.processed_messages)[-500:]
                self.processed_messages = set(recent_hashes)
            
            # 버퍼에 추가
            self.data_buffer.append(game_data)
            
            # 신호 발송
            self.data_collected.emit(game_data)
            
            self.logger.debug(f"데이터 버퍼에 추가: {game_data.get('room_name', 'Unknown')}")
            
        except Exception as e:
            self.logger.debug(f"버퍼 추가 오류: {e}")

    def _send_buffered_data(self):
        """버퍼된 데이터를 하이브리드 서비스에 전송"""
        try:
            if not self.data_buffer or not self.hybrid_service:
                return
            
            # 버퍼에서 데이터 추출 (최대 50개)
            batch_data = []
            max_batch = min(50, len(self.data_buffer))
            
            for _ in range(max_batch):
                if self.data_buffer:
                    batch_data.append(self.data_buffer.popleft())
            
            if not batch_data:
                return
            
            # 하이브리드 서비스에 전송
            for data in batch_data:
                try:
                    self.hybrid_service.add_room_data(data)
                except Exception as e:
                    self.logger.warning(f"하이브리드 서비스 전송 실패: {e}")
            
            self.logger.debug(f"하이브리드 서비스에 {len(batch_data)}개 데이터 전송")
            
        except Exception as e:
            self.logger.warning(f"데이터 전송 중 오류: {e}")

    def set_hybrid_service(self, hybrid_service):
        """하이브리드 서비스 설정"""
        self.hybrid_service = hybrid_service
        self.logger.info("하이브리드 서비스 연결 설정")

    def get_collection_stats(self):
        """수집 통계 반환"""
        try:
            return {
                'is_collecting': self.is_collecting,
                'buffer_size': len(self.data_buffer),
                'processed_messages': len(self.processed_messages),
                'websocket_connections': len(self.websocket_connections),
                'active_connections': sum(1 for conn in self.websocket_connections.values() if conn.get('active', False))
            }
        except Exception as e:
            self.logger.error(f"통계 수집 오류: {e}")
            return {}

    def force_collect_data(self):
        """수동 데이터 수집 트리거"""
        try:
            if not self.is_collecting:
                self.logger.warning("데이터 수집이 비활성화된 상태입니다.")
                return False
            
            self._collect_websocket_data()
            self._send_buffered_data()
            
            self.logger.info("수동 데이터 수집 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"수동 데이터 수집 오류: {e}")
            return False

    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            self.stop_collection()
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=False)
        except:
            pass