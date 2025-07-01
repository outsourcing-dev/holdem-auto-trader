# services/websocket_interceptor.py
"""
WebSocket Interceptor - 기존 웹소켓 연결의 메시지 가로채기
CDP Performance Logs와 Network Events를 통해 실시간 웹소켓 데이터 수집
"""

import json
import time
import logging
import threading
from typing import Dict, List, Optional, Callable, Set
from collections import deque
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication
import re

class WebSocketInterceptor(QObject):
    """웹소켓 메시지 인터셉터 - 기존 연결 모니터링"""
    
    # Qt 시그널
    websocket_message_received = pyqtSignal(dict)  # 웹소켓 메시지
    game_data_extracted = pyqtSignal(dict)  # 파싱된 게임 데이터
    connection_detected = pyqtSignal(str)  # 웹소켓 연결 감지
    error_occurred = pyqtSignal(str)  # 오류 발생
    
    def __init__(self, devtools, logger=None):
        super().__init__()
        self.logger = logger or logging.getLogger(__name__)
        self.devtools = devtools
        
        # 인터셉터 상태
        self.is_intercepting = False
        self.websocket_connections = {}  # 연결 추적
        self.message_buffer = deque(maxlen=500)  # 메시지 버퍼
        self.processed_message_ids = set()  # 중복 방지
        
        # 성능 로그 처리
        self.last_log_timestamp = 0
        self.performance_logs_enabled = False
        
        # 타이머 설정
        self.log_collection_timer = QTimer()
        self.log_collection_timer.timeout.connect(self._collect_performance_logs)
        
        # CDP 세션
        self.cdp_session_active = False
        
        self.logger.info("WebSocketInterceptor 초기화 완료")

    def start_intercepting(self):
        """웹소켓 인터셉팅 시작"""
        try:
            self.logger.info("🎯 웹소켓 인터셉팅 시작")
            
            # CDP 연결 확인
            if not self.devtools or not self.devtools.driver:
                raise Exception("DevTools 연결이 없습니다")
            
            # Performance Logs 활성화
            if not self._enable_performance_logging():
                self.logger.warning("Performance Logs 활성화 실패, CDP 방식으로 시도")
                
            # CDP Network 도메인 활성화
            self._enable_cdp_network()
            
            # 로그 수집 타이머 시작
            self.log_collection_timer.start(500)  # 500ms마다 수집
            
            self.is_intercepting = True
            self.logger.info("✅ 웹소켓 인터셉팅 활성화")
            
            return True
            
        except Exception as e:
            self.logger.error(f"웹소켓 인터셉팅 시작 실패: {e}")
            self.error_occurred.emit(f"인터셉팅 시작 실패: {str(e)}")
            return False

    def stop_intercepting(self):
        """웹소켓 인터셉팅 중지"""
        try:
            if not self.is_intercepting:
                return
                
            self.is_intercepting = False
            
            # 타이머 중지
            self.log_collection_timer.stop()
            
            # 마지막 로그 수집
            self._collect_performance_logs()
            
            # 버퍼 정리
            self.message_buffer.clear()
            self.processed_message_ids.clear()
            self.websocket_connections.clear()
            
            self.logger.info("🛑 웹소켓 인터셉팅 중지")
            
        except Exception as e:
            self.logger.error(f"웹소켓 인터셉팅 중지 오류: {e}")

    def _enable_performance_logging(self):
        """Performance Logging 활성화"""
        try:
            # 이미 활성화된 경우
            if self.performance_logs_enabled:
                return True
            
            # Chrome 옵션으로 Performance Logs 활성화 시도
            logs = self.devtools.driver.get_log('performance')
            if logs:
                self.performance_logs_enabled = True
                self.logger.info("✅ Performance Logs 활성화 성공")
                return True
                
        except Exception as e:
            self.logger.warning(f"Performance Logs 활성화 실패: {e}")
            
        return False

    def _enable_cdp_network(self):
        """CDP Network 도메인 활성화"""
        try:
            # Network 도메인 활성화
            self.devtools.driver.execute_cdp_cmd('Network.enable', {})
            
            # Runtime 도메인도 활성화 (콘솔 로그용)
            self.devtools.driver.execute_cdp_cmd('Runtime.enable', {})
            
            self.cdp_session_active = True
            self.logger.info("✅ CDP Network 도메인 활성화")
            
        except Exception as e:
            self.logger.warning(f"CDP Network 활성화 실패: {e}")

    def _collect_performance_logs(self):
        """Performance 로그 수집 및 처리"""
        try:
            if not self.is_intercepting:
                return
            
            # Performance 로그 가져오기
            performance_logs = self._get_performance_logs()
            
            # CDP 로그도 함께 수집
            browser_logs = self._get_browser_logs()
            
            # 로그 처리
            all_logs = performance_logs + browser_logs
            
            if all_logs:
                self._process_logs(all_logs)
                
        except Exception as e:
            self.logger.debug(f"로그 수집 중 오류: {e}")

    def _get_performance_logs(self):
        """Performance 로그 가져오기"""
        try:
            if not self.performance_logs_enabled:
                return []
                
            logs = self.devtools.driver.get_log('performance')
            return logs or []
            
        except Exception as e:
            self.logger.debug(f"Performance 로그 가져오기 실패: {e}")
            return []

    def _get_browser_logs(self):
        """브라우저 로그 가져오기"""
        try:
            logs = self.devtools.driver.get_log('browser')
            return logs or []
            
        except Exception as e:
            self.logger.debug(f"브라우저 로그 가져오기 실패: {e}")
            return []

    def _process_logs(self, logs):
        """로그 배치 처리"""
        try:
            websocket_messages = []
            
            for log_entry in logs:
                try:
                    # 로그 엔트리에서 웹소켓 메시지 추출
                    ws_messages = self._extract_websocket_from_log(log_entry)
                    websocket_messages.extend(ws_messages)
                    
                except Exception as e:
                    self.logger.debug(f"개별 로그 처리 오류: {e}")
                    continue
            
            # 추출된 웹소켓 메시지 처리
            for ws_message in websocket_messages:
                self._handle_websocket_message(ws_message)
                
        except Exception as e:
            self.logger.debug(f"로그 배치 처리 오류: {e}")

    def _extract_websocket_from_log(self, log_entry):
        """로그 엔트리에서 웹소켓 메시지 추출"""
        websocket_messages = []
        
        try:
            # 로그 메시지 파싱
            message_data = json.loads(log_entry.get('message', '{}'))
            
            if not isinstance(message_data, dict):
                return websocket_messages
            
            message = message_data.get('message', {})
            method = message.get('method', '')
            params = message.get('params', {})
            
            # 웹소켓 관련 이벤트 처리
            if method == 'Network.webSocketCreated':
                self._handle_websocket_created(params)
                
            elif method == 'Network.webSocketFrameReceived':
                ws_message = self._extract_received_frame(params)
                if ws_message:
                    websocket_messages.append(ws_message)
                    
            elif method == 'Network.webSocketFrameSent':
                ws_message = self._extract_sent_frame(params)
                if ws_message:
                    websocket_messages.append(ws_message)
                    
            elif method == 'Network.webSocketClosed':
                self._handle_websocket_closed(params)
                
        except json.JSONDecodeError:
            # JSON이 아닌 로그는 무시
            pass
        except Exception as e:
            self.logger.debug(f"웹소켓 메시지 추출 오류: {e}")
            
        return websocket_messages

    def _handle_websocket_created(self, params):
        """웹소켓 연결 생성 처리"""
        try:
            request_id = params.get('requestId')
            url = params.get('url', '')
            
            if self._is_evolution_websocket(url):
                self.websocket_connections[request_id] = {
                    'url': url,
                    'created_at': time.time(),
                    'active': True
                }
                
                self.connection_detected.emit(url)
                self.logger.info(f"🔌 Evolution 웹소켓 연결 감지: {url[:100]}...")
                
        except Exception as e:
            self.logger.debug(f"웹소켓 생성 처리 오류: {e}")

    def _extract_received_frame(self, params):
        """수신된 웹소켓 프레임 추출"""
        try:
            request_id = params.get('requestId')
            response = params.get('response', {})
            
            # Evolution 웹소켓인지 확인
            if request_id not in self.websocket_connections:
                return None
            
            payload_data = response.get('payloadData', '')
            if not payload_data:
                return None
            
            return {
                'direction': 'received',
                'request_id': request_id,
                'payload': payload_data,
                'timestamp': time.time(),
                'connection_info': self.websocket_connections[request_id]
            }
            
        except Exception as e:
            self.logger.debug(f"수신 프레임 추출 오류: {e}")
            return None

    def _extract_sent_frame(self, params):
        """전송된 웹소켓 프레임 추출"""
        try:
            request_id = params.get('requestId')
            response = params.get('response', {})
            
            # Evolution 웹소켓인지 확인
            if request_id not in self.websocket_connections:
                return None
            
            payload_data = response.get('payloadData', '')
            if not payload_data:
                return None
            
            return {
                'direction': 'sent',
                'request_id': request_id,
                'payload': payload_data,
                'timestamp': time.time(),
                'connection_info': self.websocket_connections[request_id]
            }
            
        except Exception as e:
            self.logger.debug(f"송신 프레임 추출 오류: {e}")
            return None

    def _handle_websocket_closed(self, params):
        """웹소켓 연결 종료 처리"""
        try:
            request_id = params.get('requestId')
            
            if request_id in self.websocket_connections:
                self.websocket_connections[request_id]['active'] = False
                self.logger.info(f"🔌❌ 웹소켓 연결 종료: {request_id}")
                
        except Exception as e:
            self.logger.debug(f"웹소켓 종료 처리 오류: {e}")

    def _handle_websocket_message(self, ws_message):
        """웹소켓 메시지 처리"""
        try:
            # 중복 메시지 방지
            message_id = f"{ws_message['request_id']}_{ws_message['timestamp']}"
            if message_id in self.processed_message_ids:
                return
            
            self.processed_message_ids.add(message_id)
            
            # 오래된 ID 정리 (메모리 효율성)
            if len(self.processed_message_ids) > 1000:
                self.processed_message_ids = set(list(self.processed_message_ids)[-500:])
            
            # 버퍼에 추가
            self.message_buffer.append(ws_message)
            
            # 시그널 발송
            self.websocket_message_received.emit(ws_message)
            
            # 바카라 게임 데이터 파싱
            game_data = self._parse_game_data(ws_message)
            if game_data:
                self.game_data_extracted.emit(game_data)
                
            # 로그 출력 (중요한 메시지만)
            if ws_message['direction'] == 'received':
                payload_preview = ws_message['payload'][:100] + '...' if len(ws_message['payload']) > 100 else ws_message['payload']
                self.logger.debug(f"📨 웹소켓 메시지 수신: {payload_preview}")
                
        except Exception as e:
            self.logger.debug(f"웹소켓 메시지 처리 오류: {e}")

    def _parse_game_data(self, ws_message):
        """웹소켓 메시지에서 게임 데이터 파싱"""
        try:
            payload = ws_message['payload']
            
            # JSON 파싱 시도
            if payload.startswith('{') or payload.startswith('['):
                data = json.loads(payload)
                return self._extract_baccarat_data_from_json(data, ws_message)
            else:
                # 텍스트 파싱
                return self._extract_baccarat_data_from_text(payload, ws_message)
                
        except json.JSONDecodeError:
            # JSON이 아닌 경우 텍스트 파싱
            return self._extract_baccarat_data_from_text(ws_message['payload'], ws_message)
        except Exception as e:
            self.logger.debug(f"게임 데이터 파싱 오류: {e}")
            return None

    def _extract_baccarat_data_from_json(self, data, ws_message):
        """JSON 데이터에서 바카라 정보 추출"""
        try:
            # 바카라 관련 키워드 확인
            data_str = str(data).lower()
            baccarat_keywords = ['baccarat', 'player', 'banker', 'tie', 'round', 'game', 'table']
            
            if not any(keyword in data_str for keyword in baccarat_keywords):
                return None
            
            # 게임 데이터 추출
            game_data = {
                'source': 'websocket_intercepted',
                'direction': ws_message['direction'],
                'timestamp': ws_message['timestamp'],
                'raw_data': data
            }
            
            # 다양한 키 패턴으로 데이터 추출
            extraction_patterns = {
                'room_name': ['table_name', 'room_name', 'table_id', 'roomName', 'tableName'],
                'round_number': ['round', 'game_number', 'round_number', 'gameNumber', 'roundNumber'],
                'latest_result': ['result', 'winner', 'game_result', 'outcome', 'lastResult'],
                'game_status': ['status', 'game_status', 'state', 'phase', 'gameState'],
                'player_cards': ['player_cards', 'playerCards', 'player', 'playerHand'],
                'banker_cards': ['banker_cards', 'bankerCards', 'banker', 'bankerHand']
            }
            
            for target_key, source_keys in extraction_patterns.items():
                value = self._find_value_in_nested_dict(data, source_keys)
                if value is not None:
                    game_data[target_key] = value
            
            # 결과 값 정규화
            if 'latest_result' in game_data:
                game_data['latest_result'] = self._normalize_result(game_data['latest_result'])
            
            # 최소 데이터가 있는 경우만 반환
            has_useful_data = any(key in game_data for key in ['room_name', 'latest_result', 'round_number'])
            
            return game_data if has_useful_data else None
            
        except Exception as e:
            self.logger.debug(f"JSON 바카라 데이터 추출 오류: {e}")
            return None

    def _extract_baccarat_data_from_text(self, payload, ws_message):
        """텍스트에서 바카라 정보 추출"""
        try:
            # 바카라 관련 키워드 확인
            payload_lower = payload.lower()
            baccarat_keywords = ['baccarat', 'player', 'banker', 'tie', 'round', 'game']
            
            if not any(keyword in payload_lower for keyword in baccarat_keywords):
                return None
            
            game_data = {
                'source': 'websocket_intercepted_text',
                'direction': ws_message['direction'],
                'timestamp': ws_message['timestamp'],
                'raw_text': payload
            }
            
            # 정규식 패턴으로 추출
            patterns = {
                'room_name': r'(?:room|table)[_\s]*[:\-]?\s*([^\s,\}]+)',
                'round_number': r'(?:round|game)[_\s]*[:\-]?\s*(\d+)',
                'latest_result': r'(?:result|winner)[_\s]*[:\-]?\s*([PBT])',
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, payload, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    if key == 'round_number':
                        game_data[key] = int(value)
                    elif key == 'latest_result':
                        game_data[key] = self._normalize_result(value)
                    else:
                        game_data[key] = value
            
            # 최소 데이터가 있는 경우만 반환
            has_useful_data = any(key in game_data for key in ['room_name', 'latest_result', 'round_number'])
            
            return game_data if has_useful_data else None
            
        except Exception as e:
            self.logger.debug(f"텍스트 바카라 데이터 추출 오류: {e}")
            return None

    def _find_value_in_nested_dict(self, data, keys):
        """중첩된 딕셔너리에서 키 찾기"""
        def search_recursive(obj, target_keys):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in target_keys:
                        return value
                    # 재귀적으로 중첩된 딕셔너리 검색
                    result = search_recursive(value, target_keys)
                    if result is not None:
                        return result
            elif isinstance(obj, list):
                for item in obj:
                    result = search_recursive(item, target_keys)
                    if result is not None:
                        return result
            return None
        
        return search_recursive(data, keys)

    def _normalize_result(self, result):
        """결과 값을 P, B, T로 정규화"""
        try:
            result_str = str(result).upper()
            
            if result_str in ['P', 'B', 'T']:
                return result_str
            
            # 키워드 매칭
            if 'PLAYER' in result_str:
                return 'P'
            elif 'BANKER' in result_str:
                return 'B'
            elif 'TIE' in result_str:
                return 'T'
            
            return result_str
            
        except Exception:
            return ""

    def _is_evolution_websocket(self, url):
        """Evolution 웹소켓인지 확인"""
        try:
            if not url:
                return False
            
            url_lower = url.lower()
            evolution_indicators = [
                'evo-games.com',
                'evolution',
                'lobby',
                'socket'
            ]
            
            return any(indicator in url_lower for indicator in evolution_indicators)
            
        except Exception:
            return False

    def get_interceptor_stats(self):
        """인터셉터 통계 반환"""
        try:
            return {
                'is_intercepting': self.is_intercepting,
                'performance_logs_enabled': self.performance_logs_enabled,
                'cdp_session_active': self.cdp_session_active,
                'websocket_connections': len(self.websocket_connections),
                'active_connections': sum(1 for conn in self.websocket_connections.values() 
                                        if conn.get('active', False)),
                'message_buffer_size': len(self.message_buffer),
                'processed_messages': len(self.processed_message_ids)
            }
        except Exception as e:
            self.logger.error(f"통계 수집 오류: {e}")
            return {}

    def get_recent_messages(self, count=10):
        """최근 메시지 반환"""
        try:
            recent_messages = list(self.message_buffer)[-count:]
            return recent_messages
        except Exception as e:
            self.logger.error(f"최근 메시지 가져오기 오류: {e}")
            return []

    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            self.stop_intercepting()
        except:
            pass