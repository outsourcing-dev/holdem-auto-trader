# services/websocket_hybrid_service.py
"""
JavaScript + Python 하이브리드 웹소켓 서비스
- 기존 DevTools 구조 유지
- JavaScript로 웹소켓 직접 연결
- 실시간 데이터를 Python으로 전달
"""

import json
import time
import logging
import asyncio
from typing import Dict, List, Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication

class WebSocketHybridService(QObject):
    """JavaScript + Python 하이브리드 웹소켓 서비스"""
    
    # Qt 시그널
    game_data_received = pyqtSignal(dict)  # 게임 데이터
    connection_status_changed = pyqtSignal(bool)  # 연결 상태
    error_occurred = pyqtSignal(str)  # 오류
    
    def __init__(self, devtools, logger=None):
        super().__init__()
        self.logger = logger or logging.getLogger(__name__)
        self.devtools = devtools
        
        # 상태 관리
        self.is_active = False
        self.websocket_url = None
        self.message_count = 0
        self.connection_id = None
        
        # 데이터 수집 타이머
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self._collect_javascript_data)
        
        self.logger.info("WebSocketHybridService 초기화 완료")

    def start_websocket_connection(self, websocket_url: str) -> bool:
        """JavaScript 웹소켓 연결 시작"""
        try:
            self.websocket_url = websocket_url
            self.logger.info(f"🔌 JavaScript 웹소켓 연결 시작: {websocket_url[:100]}...")
            
            # 1. JavaScript 인터셉터 코드 주입
            if not self._inject_websocket_interceptor():
                return False
            
            # 2. 웹소켓 직접 연결
            if not self._connect_websocket_javascript(websocket_url):
                return False
            
            # 3. 데이터 수집 시작
            self.is_active = True
            self.data_timer.start(500)  # 500ms마다 데이터 수집
            
            self.connection_status_changed.emit(True)
            self.logger.info("✅ JavaScript 웹소켓 연결 성공")
            
            return True
            
        except Exception as e:
            self.logger.error(f"JavaScript 웹소켓 연결 실패: {e}")
            self.error_occurred.emit(f"웹소켓 연결 실패: {str(e)}")
            return False

    def _inject_websocket_interceptor(self) -> bool:
            """JavaScript 웹소켓 인터셉터 주입"""
            try:
                interceptor_script = r"""
                // 웹소켓 데이터 저장소
                window.evolutionWebSocketData = {
                    messages: [],
                    gameData: [],
                    connectionStatus: 'disconnected',
                    lastMessageTime: 0,
                    currentWebSocket: null,
                    messageCount: 0,
                    debugMode: true
                };
                
                // 웹소켓 인터셉터 함수
                window.startEvolutionWebSocketInterceptor = function(wsUrl) {
                    console.log('🎯 Evolution 웹소켓 인터셉터 시작:', wsUrl);
                    
                    try {
                        // 기존 연결 종료
                        if (window.evolutionWebSocketData.currentWebSocket) {
                            window.evolutionWebSocketData.currentWebSocket.close();
                        }
                        
                        // 새 웹소켓 연결
                        const ws = new WebSocket(wsUrl);
                        window.evolutionWebSocketData.currentWebSocket = ws;
                        
                        ws.onopen = function(event) {
                            console.log('✅ Evolution 웹소켓 연결 성공');
                            window.evolutionWebSocketData.connectionStatus = 'connected';
                        };
                        
                        ws.onmessage = function(event) {
                            const timestamp = Date.now();
                            window.evolutionWebSocketData.lastMessageTime = timestamp;
                            window.evolutionWebSocketData.messageCount++;
                            
                            console.log(`📨 메시지 #${window.evolutionWebSocketData.messageCount} (${event.data.length}자):`, event.data.substring(0, 100));
                            
                            // 메시지 저장
                            const messageData = {
                                data: event.data,
                                timestamp: timestamp,
                                type: 'received'
                            };
                            
                            window.evolutionWebSocketData.messages.push(messageData);
                            
                            // 버퍼 크기 제한 (최대 50개)
                            if (window.evolutionWebSocketData.messages.length > 50) {
                                window.evolutionWebSocketData.messages = 
                                    window.evolutionWebSocketData.messages.slice(-25);
                            }
                            
                            // 모든 메시지를 게임 데이터로 처리 (키워드 필터링 없음)
                            try {
                                const gameData = createGameDataFromMessage(event.data, timestamp);
                                if (gameData) {
                                    window.evolutionWebSocketData.gameData.push(gameData);
                                    console.log('🎮 게임 데이터 추가:', gameData);
                                    
                                    // 게임 데이터 버퍼 제한
                                    if (window.evolutionWebSocketData.gameData.length > 50) {
                                        window.evolutionWebSocketData.gameData = 
                                            window.evolutionWebSocketData.gameData.slice(-25);
                                    }
                                }
                            } catch (e) {
                                console.warn('게임 데이터 처리 오류:', e);
                            }
                        };
                        
                        ws.onerror = function(error) {
                            console.error('❌ Evolution 웹소켓 에러:', error);
                            window.evolutionWebSocketData.connectionStatus = 'error';
                        };
                        
                        ws.onclose = function(event) {
                            console.log('🔌 Evolution 웹소켓 연결 종료:', event.code);
                            window.evolutionWebSocketData.connectionStatus = 'disconnected';
                        };
                        
                        return true;
                        
                    } catch (error) {
                        console.error('웹소켓 연결 중 오류:', error);
                        window.evolutionWebSocketData.connectionStatus = 'error';
                        return false;
                    }
                };
                
                // 모든 메시지를 게임 데이터로 변환 (필터링 없음)
                function createGameDataFromMessage(rawData, timestamp) {
                    try {
                        const gameData = {
                            timestamp: timestamp,
                            source: 'websocket_javascript',
                            raw_data: rawData,
                            data_length: rawData.length,
                            data_type: typeof rawData
                        };
                        
                        // JSON 파싱 시도
                        if (typeof rawData === 'string' && (rawData.includes('{') || rawData.includes('['))) {
                            try {
                                const parsed = JSON.parse(rawData);
                                gameData.parsed_json = parsed;
                                gameData.is_json = true;
                                
                                // JSON 구조 정보 추가
                                if (typeof parsed === 'object' && parsed !== null) {
                                    gameData.json_keys = Object.keys(parsed);
                                }
                            } catch (e) {
                                gameData.json_parse_error = e.message;
                                gameData.is_json = false;
                            }
                        } else {
                            gameData.is_json = false;
                        }
                        
                        // 데이터 미리보기 추가
                        gameData.preview = rawData.length > 200 ? rawData.substring(0, 200) + '...' : rawData;
                        
                        return gameData;
                        
                    } catch (error) {
                        console.warn('게임 데이터 생성 오류:', error);
                        return null;
                    }
                }
                
                // 데이터 가져오기 함수들
                window.getEvolutionWebSocketStatus = function() {
                    return {
                        status: window.evolutionWebSocketData.connectionStatus,
                        messageCount: window.evolutionWebSocketData.messageCount,
                        gameDataCount: window.evolutionWebSocketData.gameData.length,
                        lastMessageTime: window.evolutionWebSocketData.lastMessageTime,
                        isConnected: window.evolutionWebSocketData.connectionStatus === 'connected'
                    };
                };
                
                window.getEvolutionNewMessages = function() {
                    const messages = window.evolutionWebSocketData.messages.splice(0);
                    return messages;
                };
                
                window.getEvolutionNewGameData = function() {
                    const gameData = window.evolutionWebSocketData.gameData.splice(0);
                    return gameData;
                };
                
                // 디버그 함수들
                window.getEvolutionAllData = function() {
                    return {
                        messages: window.evolutionWebSocketData.messages,
                        gameData: window.evolutionWebSocketData.gameData,
                        status: window.getEvolutionWebSocketStatus()
                    };
                };
                
                window.clearEvolutionData = function() {
                    window.evolutionWebSocketData.messages = [];
                    window.evolutionWebSocketData.gameData = [];
                    window.evolutionWebSocketData.messageCount = 0;
                    console.log('🧹 Evolution 데이터 버퍼 초기화됨');
                };
                
                console.log('✅ Evolution 웹소켓 인터셉터 코드 주입 완료 (전체 데이터 수집 모드)');
                return true;
                """
                
                self.devtools.driver.execute_script(interceptor_script)
                self.logger.info("✅ JavaScript 인터셉터 코드 주입 완료")
                return True
                
            except Exception as e:
                self.logger.error(f"JavaScript 코드 주입 실패: {e}")
                return False
            
    def _connect_websocket_javascript(self, websocket_url: str) -> bool:
        """JavaScript로 웹소켓 연결"""
        try:
            connect_script = f"""
            return window.startEvolutionWebSocketInterceptor('{websocket_url}');
            """
            
            result = self.devtools.driver.execute_script(connect_script)
            
            if result:
                self.logger.info("✅ JavaScript 웹소켓 연결 시작 성공")
                
                # 연결 상태 확인 (최대 10초 대기)
                for i in range(20):  # 0.5초씩 20번 = 10초
                    time.sleep(0.5)
                    status = self._get_javascript_connection_status()
                    
                    if status.get('isConnected'):
                        self.logger.info(f"✅ JavaScript 웹소켓 연결 확인됨 ({i * 0.5:.1f}초 소요)")
                        return True
                    elif status.get('status') == 'error':
                        self.logger.error("❌ JavaScript 웹소켓 연결 에러")
                        return False
                
                self.logger.warning("⚠️ JavaScript 웹소켓 연결 타임아웃")
                return False
            else:
                self.logger.error("❌ JavaScript 웹소켓 연결 시작 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"JavaScript 웹소켓 연결 오류: {e}")
            return False

    def _get_javascript_connection_status(self) -> dict:
        """JavaScript 연결 상태 확인"""
        try:
            status_script = "return window.getEvolutionWebSocketStatus();"
            result = self.devtools.driver.execute_script(status_script)
            return result or {}
        except Exception as e:
            self.logger.debug(f"연결 상태 확인 오류: {e}")
            return {}

    def _collect_javascript_data(self):
        """JavaScript에서 데이터 수집"""
        try:
            if not self.is_active:
                return
            
            # 새 메시지 가져오기
            new_messages = self._get_new_messages()
            
            # 새 게임 데이터 가져오기
            new_game_data = self._get_new_game_data()
            
            # 메시지 카운트 업데이트
            self.message_count += len(new_messages)
            
            # 게임 데이터 처리
            for game_data in new_game_data:
                self._process_game_data(game_data)
            
            # 연결 상태 확인
            status = self._get_javascript_connection_status()
            if not status.get('isConnected') and status.get('status') != 'connected':
                self.logger.warning(f"연결 상태 이상: {status}")
                
        except Exception as e:
            self.logger.debug(f"데이터 수집 중 오류: {e}")

    def _get_new_messages(self) -> list:
        """새 메시지 가져오기"""
        try:
            messages_script = "return window.getEvolutionNewMessages();"
            messages = self.devtools.driver.execute_script(messages_script)
            return messages or []
        except Exception as e:
            self.logger.debug(f"메시지 가져오기 오류: {e}")
            return []

    def _get_new_game_data(self) -> list:
        """새 게임 데이터 가져오기"""
        try:
            game_data_script = "return window.getEvolutionNewGameData();"
            game_data = self.devtools.driver.execute_script(game_data_script)
            return game_data or []
        except Exception as e:
            self.logger.debug(f"게임 데이터 가져오기 오류: {e}")
            return []

    def _process_game_data(self, game_data: dict):
        """게임 데이터 처리 및 시그널 발송"""
        try:
            # 필수 필드 추가
            if 'timestamp' not in game_data:
                game_data['timestamp'] = time.time()
            
            # 게임 데이터 시그널 발송
            self.game_data_received.emit(game_data)
            
            # 로깅
            room_name = game_data.get('room_name', '')
            round_number = game_data.get('round_number', '')
            latest_result = game_data.get('latest_result', '')
            
            if latest_result:
                self.logger.info(f"🎮 JavaScript 게임 데이터: {room_name} - 라운드 {round_number}, 결과: {latest_result}")
                
        except Exception as e:
            self.logger.error(f"게임 데이터 처리 오류: {e}")

    def stop_websocket_connection(self):
        """웹소켓 연결 중지"""
        try:
            if not self.is_active:
                return
                
            self.logger.info("🛑 JavaScript 웹소켓 연결 중지")
            
            # 데이터 수집 중지
            self.is_active = False
            self.data_timer.stop()
            
            # JavaScript 웹소켓 연결 종료
            close_script = """
            if (window.evolutionWebSocketData && window.evolutionWebSocketData.currentWebSocket) {
                window.evolutionWebSocketData.currentWebSocket.close();
                window.evolutionWebSocketData.connectionStatus = 'disconnected';
                return true;
            }
            return false;
            """
            
            try:
                self.devtools.driver.execute_script(close_script)
            except Exception as e:
                self.logger.warning(f"JavaScript 연결 종료 중 오류: {e}")
            
            # 상태 초기화
            self.websocket_url = None
            self.message_count = 0
            self.connection_id = None
            
            self.connection_status_changed.emit(False)
            self.logger.info("✅ JavaScript 웹소켓 연결 중지 완료")
            
        except Exception as e:
            self.logger.error(f"웹소켓 연결 중지 오류: {e}")

    def get_connection_status(self) -> dict:
        """연결 상태 정보 반환"""
        try:
            js_status = self._get_javascript_connection_status()
            
            return {
                'active': self.is_active,
                'websocket_url': self.websocket_url,
                'message_count': self.message_count,
                'javascript_status': js_status,
                'connected': js_status.get('isConnected', False)
            }
            
        except Exception as e:
            self.logger.error(f"연결 상태 확인 오류: {e}")
            return {'active': False, 'connected': False, 'error': str(e)}

    def force_reconnect(self):
        """강제 재연결"""
        try:
            if self.websocket_url:
                self.logger.info("🔄 JavaScript 웹소켓 강제 재연결")
                self.stop_websocket_connection()
                time.sleep(1)
                return self.start_websocket_connection(self.websocket_url)
            else:
                self.logger.warning("재연결할 웹소켓 URL이 없습니다")
                return False
                
        except Exception as e:
            self.logger.error(f"강제 재연결 오류: {e}")
            return False

    def debug_javascript_state(self):
        """JavaScript 상태 디버그"""
        try:
            debug_script = """
            return {
                webSocketExists: typeof window.evolutionWebSocketData !== 'undefined',
                interceptorExists: typeof window.startEvolutionWebSocketInterceptor === 'function',
                currentStatus: window.getEvolutionWebSocketStatus ? window.getEvolutionWebSocketStatus() : null,
                webSocketConstructor: typeof WebSocket !== 'undefined'
            };
            """
            
            result = self.devtools.driver.execute_script(debug_script)
            
            self.logger.info("🔍 JavaScript 상태 디버그:")
            for key, value in result.items():
                self.logger.info(f"  - {key}: {value}")
                
            return result
            
        except Exception as e:
            self.logger.error(f"JavaScript 상태 디버그 오류: {e}")
            return {}

    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            self.stop_websocket_connection()
        except:
            pass