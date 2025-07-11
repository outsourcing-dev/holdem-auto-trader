# services/websocket_hybrid_service.py
"""
JavaScript 하이브리드 웹소켓 서비스 - 모든 메시지 출력 버전
Evolution Gaming 웹소켓 메시지를 JavaScript로 가로채서 Python으로 전달
"""

import json
import time
import logging
from typing import Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from datetime import datetime


class WebSocketHybridService(QObject):
    """JavaScript 하이브리드 웹소켓 서비스"""
    
    # Qt 시그널
    game_data_received = pyqtSignal(dict)
    connection_status_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, devtools, logger=None):
        super().__init__()
        self.devtools = devtools
        self.logger = logger or logging.getLogger(__name__)
        
        # 상태 관리
        self.is_active = False
        self.is_connected = False
        self.websocket_url = ""
        
        # 메시지 카운터
        self.message_count = 0
        self.received_message_count = 0
        
        # 연결 상태 체크 타이머
        self.status_check_timer = QTimer()
        self.status_check_timer.timeout.connect(self._check_connection_status)
        
        self.logger.info("WebSocketHybridService 초기화 완료")

    def start_websocket_connection(self, websocket_url: str) -> bool:
        """JavaScript 웹소켓 연결 시작"""
        try:
            self.logger.info(f"🔌 JavaScript 웹소켓 연결 시작: {websocket_url[:100]}...")
            
            if not self.devtools or not self.devtools.driver:
                self.logger.error("DevTools 연결이 없습니다")
                return False
            
            self.websocket_url = websocket_url
            
            # JavaScript 인터셉터 주입
            if not self._inject_websocket_interceptor():
                return False
            
            # 웹소켓 연결 시작
            if not self._start_javascript_websocket():
                return False
            
            # 연결 확인
            if not self._verify_connection():
                return False
            
            # 상태 체크 타이머 시작
            self.status_check_timer.start(5000)  # 5초마다 상태 체크
            
            self.is_active = True
            self.connection_status_changed.emit(True)
            
            self.logger.info("✅ JavaScript 웹소켓 연결 성공")
            return True
            
        except Exception as e:
            self.logger.error(f"JavaScript 웹소켓 연결 실패: {e}")
            self.error_occurred.emit(f"연결 실패: {str(e)}")
            return False

    def _inject_websocket_interceptor(self) -> bool:
        """웹소켓 인터셉터 주입 - 모든 메시지 출력 버전"""
        try:
            # 모든 메시지를 로깅하는 JavaScript 코드
            interceptor_script = """
            // 웹소켓 메시지 전체 로깅 인터셉터
            (function() {
                console.log('🎯 웹소켓 메시지 전체 로깅 시작');
                
                // 메시지 카운터 및 저장소
                window.webSocketMessageCount = window.webSocketMessageCount || 0;
                window.gameDataCount = window.gameDataCount || 0;
                window.allWebSocketMessages = window.allWebSocketMessages || [];
                
                // 원본 WebSocket 클래스 백업
                const OriginalWebSocket = window.WebSocket;
                
                // WebSocket 가로채기
                window.WebSocket = function(url, protocols) {
                    console.log('🔗 새 WebSocket 연결:', url);
                    
                    const ws = new OriginalWebSocket(url, protocols);
                    
                    // Evolution 웹소켓인지 확인
                    if (url.includes('evo-games.com')) {
                        console.log('🎮 Evolution WebSocket 감지 - 전체 메시지 로깅 활성화');
                        window.gameWebSocket = ws;
                        
                        // 메시지 수신 이벤트 - 모든 메시지 상세 로깅
                        ws.addEventListener('message', function(event) {
                            window.webSocketMessageCount++;
                            
                            const messageData = event.data;
                            const timestamp = new Date().toISOString();
                            const messageId = window.webSocketMessageCount;
                            
                            // 콘솔에 상세 정보 출력
                            console.log(`\\n📡 [${messageId.toString().padStart(4, '0')}] ${timestamp}`);
                            console.log(`📏 메시지 길이: ${String(messageData).length}자`);
                            console.log(`📝 메시지 타입: ${typeof messageData}`);
                            console.log('🔍 메시지 전체 내용:');
                            console.log('='.repeat(80));
                            console.log(messageData);
                            console.log('='.repeat(80));
                            
                            // JSON 파싱 시도
                            let parsedData = null;
                            if (typeof messageData === 'string') {
                                try {
                                    if (messageData.trim().startsWith('{') || messageData.trim().startsWith('[')) {
                                        parsedData = JSON.parse(messageData);
                                        console.log('🔍 JSON 파싱 결과:');
                                        console.log(parsedData);
                                        
                                        // JSON 키 구조 출력
                                        if (typeof parsedData === 'object' && parsedData !== null) {
                                            if (Array.isArray(parsedData)) {
                                                console.log(`📊 배열 길이: ${parsedData.length}`);
                                                if (parsedData.length > 0) {
                                                    console.log(`📊 첫번째 요소 타입: ${typeof parsedData[0]}`);
                                                }
                                            } else {
                                                console.log(`📊 JSON 키들: [${Object.keys(parsedData).join(', ')}]`);
                                            }
                                        }
                                    }
                                } catch (e) {
                                    console.log('⚠️ JSON 파싱 실패:', e.message);
                                }
                            }
                            
                            console.log('─'.repeat(80));
                            
                            // 메시지 저장 (최근 100개만)
                            const messageInfo = {
                                id: messageId,
                                timestamp: timestamp,
                                data: messageData,
                                parsedData: parsedData,
                                length: String(messageData).length,
                                type: typeof messageData
                            };
                            
                            window.allWebSocketMessages.push(messageInfo);
                            if (window.allWebSocketMessages.length > 100) {
                                window.allWebSocketMessages = window.allWebSocketMessages.slice(-100);
                            }
                            
                            // Python으로 데이터 전송
                            if (window.sendGameDataToPython) {
                                try {
                                    const gameData = {
                                        source: 'websocket_full_message',
                                        timestamp: Date.now(),
                                        message_id: messageId,
                                        raw_message: messageData,
                                        parsed_data: parsedData,
                                        message_type: typeof messageData,
                                        message_length: String(messageData).length
                                    };
                                    
                                    window.sendGameDataToPython(gameData);
                                } catch (error) {
                                    console.error('🚨 Python 전송 오류:', error);
                                }
                            }
                        });
                        
                        // 연결 상태 이벤트 로깅
                        ws.addEventListener('open', function() {
                            console.log('✅ Evolution WebSocket 연결 성공');
                        });
                        
                        ws.addEventListener('close', function(event) {
                            console.log('❌ Evolution WebSocket 연결 종료:', event.code, event.reason);
                        });
                        
                        ws.addEventListener('error', function(error) {
                            console.log('🚨 Evolution WebSocket 오류:', error);
                        });
                    }
                    
                    return ws;
                };
                
                // 디버깅 도우미 함수들
                window.getMessageCount = function() {
                    return window.webSocketMessageCount;
                };
                
                window.getGameDataCount = function() {
                    return window.gameDataCount;
                };
                
                window.getRecentMessages = function(count = 10) {
                    return window.allWebSocketMessages.slice(-count);
                };
                
                window.getAllMessages = function() {
                    return window.allWebSocketMessages;
                };
                
                window.clearMessageLog = function() {
                    window.allWebSocketMessages = [];
                    window.webSocketMessageCount = 0;
                    window.gameDataCount = 0;
                    console.log('🗑️ 메시지 로그 초기화 완료');
                };
                
                window.getWebSocketStats = function() {
                    return {
                        messageCount: window.webSocketMessageCount,
                        gameDataCount: window.gameDataCount,
                        recentCount: window.allWebSocketMessages.length,
                        connected: window.gameWebSocket ? window.gameWebSocket.readyState === 1 : false,
                        url: window.gameWebSocket ? window.gameWebSocket.url : null
                    };
                };
                
                console.log('✅ 웹소켓 메시지 전체 로깅 인터셉터 설치 완료');
            })();
            """
            
            # JavaScript 코드 실행
            result = self.devtools.driver.execute_script(interceptor_script)
            
            self.logger.info("✅ JavaScript 웹소켓 전체 메시지 로깅 인터셉터 주입 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"웹소켓 인터셉터 주입 실패: {e}")
            return False

    def _start_javascript_websocket(self) -> bool:
        """JavaScript 웹소켓 연결 시작"""
        try:
            # Python에서 JavaScript로 데이터를 받기 위한 콜백 함수 설정
            callback_script = f"""
            // Python 콜백 함수 설정
            window.sendGameDataToPython = function(gameData) {{
                // 브라우저 콘솔에 추가 정보 출력
                console.log('📤 Python으로 데이터 전송:', gameData);
                
                // DOM 이벤트를 통해 Python으로 데이터 전달
                const event = new CustomEvent('pythonGameData', {{
                    detail: gameData
                }});
                document.dispatchEvent(event);
            }};
            
            // DOM 이벤트 리스너 설정 (Python에서 감지할 수 있도록)
            document.addEventListener('pythonGameData', function(event) {{
                window.lastGameData = event.detail;
                window.lastGameDataTimestamp = Date.now();
            }});
            
            // 실제 웹소켓 연결 생성 (가장 중요한 부분!)
            try {{
                console.log('🔌 실제 Evolution 웹소켓 연결 시작:', '{self.websocket_url}');
                window.gameWebSocket = new WebSocket('{self.websocket_url}');
                
                window.gameWebSocket.onopen = function() {{
                    console.log('✅ Evolution 웹소켓 연결 성공');
                }};
                
                window.gameWebSocket.onclose = function(event) {{
                    console.log('❌ Evolution 웹소켓 연결 종료:', event.code, event.reason);
                }};
                
                window.gameWebSocket.onerror = function(error) {{
                    console.log('🚨 Evolution 웹소켓 오류:', error);
                }};
                
                console.log('✅ Python 콜백 함수 및 웹소켓 연결 설정 완료');
                return true;
                
            }} catch (wsError) {{
                console.error('🚨 웹소켓 연결 생성 실패:', wsError);
                return false;
            }}
            """
            
            result = self.devtools.driver.execute_script(callback_script)
            
            if result:
                self.logger.info("✅ JavaScript 콜백 함수 및 웹소켓 연결 설정 성공")
                
                # 메시지 수집 시작
                self._start_message_collection()
                
                return True
            else:
                self.logger.error("JavaScript 콜백 함수 설정 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"JavaScript 웹소켓 시작 실패: {e}")
            return False

    def _start_message_collection(self):
        """메시지 수집 시작"""
        try:
            # 메시지 수집 타이머 시작
            self.message_collection_timer = QTimer()
            self.message_collection_timer.timeout.connect(self._collect_javascript_messages)
            self.message_collection_timer.start(1000)  # 1초마다 수집
            
            self.logger.info("✅ JavaScript 메시지 수집 시작")
            
        except Exception as e:
            self.logger.error(f"메시지 수집 시작 오류: {e}")

    def _collect_javascript_messages(self):
        """JavaScript에서 메시지 수집"""
        try:
            # JavaScript에서 새로운 메시지 가져오기
            collection_script = """
            if (window.lastGameData && window.lastGameDataTimestamp) {
                const data = window.lastGameData;
                const timestamp = window.lastGameDataTimestamp;
                
                // 이미 처리한 메시지인지 확인 (중복 방지)
                if (!window.processedMessageTimestamp || timestamp > window.processedMessageTimestamp) {
                    window.processedMessageTimestamp = timestamp;
                    return data;
                }
            }
            return null;
            """
            
            message_data = self.devtools.driver.execute_script(collection_script)
            
            if message_data:
                self._on_javascript_message(message_data)
                
        except Exception as e:
            self.logger.debug(f"메시지 수집 중 오류: {e}")

    def _on_javascript_message(self, message_data):
        """JavaScript 메시지 처리 - 전체 메시지 로깅"""
        try:
            self.message_count += 1
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            
            # 메시지 전체 내용 Python 로그로 출력
            self.logger.info(f"🎮 [{self.message_count:04d}] {timestamp} - JavaScript 메시지 수신")
            self.logger.info(f"📏 메시지 길이: {len(str(message_data))}자")
            self.logger.info(f"📝 메시지 타입: {type(message_data).__name__}")
            
            # 메시지 ID 출력
            message_id = message_data.get('message_id', 0)
            self.logger.info(f"🆔 메시지 ID: {message_id}")
            
            # 원본 메시지 출력
            raw_message = message_data.get('raw_message', '')
            self.logger.info("🔍 원본 메시지:")
            self.logger.info("=" * 80)
            self.logger.info(str(raw_message))
            self.logger.info("=" * 80)
            
            # 파싱된 데이터가 있으면 출력
            parsed_data = message_data.get('parsed_data')
            if parsed_data:
                self.logger.info("🔍 파싱된 JSON 데이터:")
                self.logger.info(json.dumps(parsed_data, indent=2, ensure_ascii=False))
            
            self.logger.info("─" * 80)
            
            # 게임 데이터로 변환하여 시그널 발송
            game_data = self._convert_to_game_data(message_data)
            if game_data:
                self.game_data_received.emit(game_data)
            
            return True
            
        except Exception as e:
            self.logger.error(f"JavaScript 메시지 처리 오류: {e}")
            return False

    def _convert_to_game_data(self, message_data):
        """메시지 데이터를 게임 데이터로 변환"""
        try:
            # 일단 원본 메시지를 그대로 전달 (나중에 파싱 로직 추가)
            return {
                'source': 'websocket_hybrid',
                'timestamp': message_data.get('timestamp', int(time.time() * 1000)),
                'message_id': message_data.get('message_id', 0),
                'raw_message': message_data.get('raw_message', ''),
                'parsed_data': message_data.get('parsed_data'),
                'message_type': message_data.get('message_type', 'unknown'),
                'message_length': message_data.get('message_length', 0),
                
                # 임시 게임 데이터 (실제 메시지 분석 후 수정 필요)
                'room_name': 'Unknown',
                'round_number': 0,
                'latest_result': '',
                'game_status': 'Unknown'
            }
            
        except Exception as e:
            self.logger.debug(f"게임 데이터 변환 오류: {e}")
            return None

    def _verify_connection(self) -> bool:
        """연결 확인"""
        try:
            # 연결이 완료될 때까지 최대 10초 대기
            max_wait_time = 10
            check_interval = 0.5
            
            for attempt in range(int(max_wait_time / check_interval)):
                verification_script = """
                if (window.gameWebSocket) {
                    return {
                        connected: window.gameWebSocket.readyState === 1,
                        url: window.gameWebSocket.url,
                        readyState: window.gameWebSocket.readyState,
                        readyStateText: ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED'][window.gameWebSocket.readyState] || 'UNKNOWN'
                    };
                }
                return { connected: false, readyState: -1, readyStateText: 'NO_WEBSOCKET' };
                """
                
                result = self.devtools.driver.execute_script(verification_script)
                
                if result and result.get('connected'):
                    self.is_connected = True
                    elapsed_time = attempt * check_interval
                    self.logger.info(f"✅ JavaScript 웹소켓 연결 확인됨 ({elapsed_time:.1f}초 소요)")
                    return True
                elif result:
                    # 연결 중이거나 다른 상태인 경우 로깅
                    state_text = result.get('readyStateText', 'UNKNOWN')
                    if attempt == 0:  # 첫 시도에만 로깅
                        self.logger.info(f"🔄 웹소켓 상태: {state_text} - 연결 대기 중...")
                
                time.sleep(check_interval)
            
            # 최종 상태 확인
            final_result = self.devtools.driver.execute_script(verification_script)
            if final_result:
                state_text = final_result.get('readyStateText', 'UNKNOWN')
                self.logger.warning(f"❌ JavaScript 웹소켓 연결 확인 실패 - 최종 상태: {state_text}")
            else:
                self.logger.warning("❌ JavaScript 웹소켓 연결 확인 실패 - 웹소켓 객체 없음")
            
            return False
                
        except Exception as e:
            self.logger.error(f"연결 확인 오류: {e}")
            return False

    def _check_connection_status(self):
        """주기적 연결 상태 체크"""
        try:
            status_script = """
            return {
                connected: window.gameWebSocket ? window.gameWebSocket.readyState === 1 : false,
                messageCount: window.webSocketMessageCount || 0,
                gameDataCount: window.gameDataCount || 0,
                recentMessagesCount: window.allWebSocketMessages ? window.allWebSocketMessages.length : 0
            };
            """
            
            status = self.devtools.driver.execute_script(status_script)
            
            if status:
                was_connected = self.is_connected
                self.is_connected = status.get('connected', False)
                
                # 연결 상태 변경 시 시그널 발송
                if was_connected != self.is_connected:
                    self.connection_status_changed.emit(self.is_connected)
                
                # 상태 로그 (간단히)
                js_msg_count = status.get('messageCount', 0)
                if self.received_message_count != js_msg_count:
                    self.received_message_count = js_msg_count
                    self.logger.debug(f"📊 JavaScript 메시지 상태: {js_msg_count}개 수신")
                
        except Exception as e:
            self.logger.debug(f"연결 상태 체크 오류: {e}")

    def stop_websocket_connection(self):
        """웹소켓 연결 중지"""
        try:
            if not self.is_active:
                return
                
            self.logger.info("🛑 JavaScript 웹소켓 연결 중지")
            
            # 타이머 중지
            if hasattr(self, 'status_check_timer'):
                self.status_check_timer.stop()
            
            if hasattr(self, 'message_collection_timer'):
                self.message_collection_timer.stop()
            
            # JavaScript 정리
            cleanup_script = """
            if (window.gameWebSocket) {
                try {
                    window.gameWebSocket.close();
                } catch(e) {
                    console.log('WebSocket 정리 중 오류:', e);
                }
            }
            
            // 메시지 로그 초기화
            if (window.clearMessageLog) {
                window.clearMessageLog();
            }
            
            console.log('🛑 JavaScript 웹소켓 정리 완료');
            """
            
            self.devtools.driver.execute_script(cleanup_script)
            
            # 상태 초기화
            self.is_active = False
            self.is_connected = False
            self.message_count = 0
            self.received_message_count = 0
            
            self.connection_status_changed.emit(False)
            self.logger.info("✅ JavaScript 웹소켓 중지 완료")
            
        except Exception as e:
            self.logger.error(f"웹소켓 중지 중 오류: {e}")

    def get_connection_status(self) -> Dict[str, Any]:
        """연결 상태 정보 반환"""
        try:
            # JavaScript 상태 가져오기
            js_status_script = """
            return window.getWebSocketStats ? window.getWebSocketStats() : {
                messageCount: window.webSocketMessageCount || 0,
                gameDataCount: window.gameDataCount || 0,
                recentCount: window.allWebSocketMessages ? window.allWebSocketMessages.length : 0,
                connected: window.gameWebSocket ? window.gameWebSocket.readyState === 1 : false
            };
            """
            
            js_status = self.devtools.driver.execute_script(js_status_script)
            
            return {
                'active': self.is_active,
                'connected': self.is_connected,
                'websocket_url': self.websocket_url,
                'message_count': self.message_count,
                'javascript_status': js_status or {}
            }
            
        except Exception as e:
            self.logger.error(f"연결 상태 확인 오류: {e}")
            return {
                'active': self.is_active,
                'connected': False,
                'error': str(e)
            }

    def force_reconnect(self) -> bool:
        """강제 재연결"""
        try:
            self.logger.info("🔄 JavaScript 웹소켓 강제 재연결 시도")
            
            # 기존 연결 정리
            self.stop_websocket_connection()
            time.sleep(2)
            
            # 재연결
            if self.websocket_url:
                return self.start_websocket_connection(self.websocket_url)
            else:
                self.logger.error("재연결할 URL이 없습니다")
                return False
                
        except Exception as e:
            self.logger.error(f"강제 재연결 오류: {e}")
            return False

    def debug_javascript_state(self) -> Dict[str, Any]:
        """JavaScript 상태 디버깅"""
        try:
            debug_script = """
            return {
                webSocketExists: typeof window.WebSocket !== 'undefined',
                gameWebSocketExists: typeof window.gameWebSocket !== 'undefined',
                gameWebSocketState: window.gameWebSocket ? window.gameWebSocket.readyState : -1,
                messageCount: window.webSocketMessageCount || 0,
                gameDataCount: window.gameDataCount || 0,
                recentMessagesCount: window.allWebSocketMessages ? window.allWebSocketMessages.length : 0,
                callbackExists: typeof window.sendGameDataToPython === 'function',
                helperFunctionsExist: {
                    getMessageCount: typeof window.getMessageCount === 'function',
                    getWebSocketStats: typeof window.getWebSocketStats === 'function',
                    clearMessageLog: typeof window.clearMessageLog === 'function'
                }
            };
            """
            
            return self.devtools.driver.execute_script(debug_script)
            
        except Exception as e:
            self.logger.error(f"JavaScript 상태 디버깅 오류: {e}")
            return {'error': str(e)}

    def _debug_javascript_messages(self):
        """JavaScript 메시지 디버깅"""
        try:
            debug_script = """
            console.log('🔍 JavaScript 메시지 디버깅:');
            console.log('- 총 메시지 수:', window.webSocketMessageCount || 0);
            console.log('- 게임 데이터 수:', window.gameDataCount || 0);
            console.log('- 저장된 메시지 수:', window.allWebSocketMessages ? window.allWebSocketMessages.length : 0);
            
            if (window.allWebSocketMessages && window.allWebSocketMessages.length > 0) {
                console.log('- 최근 3개 메시지:');
                const recent = window.allWebSocketMessages.slice(-3);
                recent.forEach((msg, index) => {
                    console.log(`  [${msg.id}] 길이: ${msg.length}, 타입: ${msg.type}`);
                    console.log(`  내용 미리보기: ${String(msg.data).substring(0, 100)}...`);
                });
            }
            
            return {
                messageCount: window.webSocketMessageCount || 0,
                gameDataCount: window.gameDataCount || 0,
                recentCount: window.allWebSocketMessages ? window.allWebSocketMessages.length : 0
            };
            """
            
            result = self.devtools.driver.execute_script(debug_script)
            self.logger.info(f"🔍 JavaScript 디버깅 결과: {result}")
            
        except Exception as e:
            self.logger.error(f"JavaScript 메시지 디버깅 오류: {e}")

    def show_recent_messages(self, count=5):
        """최근 메시지 표시"""
        try:
            script = f"""
            if (window.getRecentMessages) {{
                return window.getRecentMessages({count});
            }}
            return null;
            """
            
            messages = self.devtools.driver.execute_script(script)
            
            if messages:
                self.logger.info(f"📋 최근 {count}개 메시지:")
                for msg in messages:
                    self.logger.info(f"[{msg.get('id', 0)}] {msg.get('timestamp', '')} - 길이: {msg.get('length', 0)}")
                    preview = str(msg.get('data', ''))[:200]
                    self.logger.info(f"내용: {preview}...")
                    self.logger.info("─" * 40)
            else:
                self.logger.warning("최근 메시지가 없습니다")
                
        except Exception as e:
            self.logger.error(f"최근 메시지 표시 오류: {e}")

    def clear_message_log(self):
        """메시지 로그 초기화"""
        try:
            script = "if (window.clearMessageLog) { window.clearMessageLog(); }"
            self.devtools.driver.execute_script(script)
            self.message_count = 0
            self.received_message_count = 0
            self.logger.info("🗑️ 메시지 로그 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"메시지 로그 초기화 오류: {e}")

    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            self.stop_websocket_connection()
        except:
            pass