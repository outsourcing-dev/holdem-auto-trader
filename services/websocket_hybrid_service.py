# services/websocket_hybrid_service.py - 필터링된 방만 로깅하는 완전한 버전
"""
JavaScript 하이브리드 웹소켓 서비스 - 필터링된 방 데이터 분석 전용
Evolution Gaming 웹소켓 메시지에서 filtered_room_mappings.json에 있는 방만 로깅
"""

import json
import time
import logging
import os
import sys
from typing import Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from datetime import datetime


class WebSocketHybridService(QObject):
    """JavaScript 하이브리드 웹소켓 서비스 - 필터링된 방 데이터 분석"""
    
    # Qt 시그널
    game_data_received = pyqtSignal(dict)
    connection_status_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, devtools, logger=None):
        super().__init__()
        self.devtools = devtools
        self.logger = logger or logging.getLogger(__name__)
        
        # 파일 로깅 설정
        self._setup_file_logging()
        
        # 필터링된 방 ID 목록 로드
        self._load_filtered_room_mappings()
        
        # 상태 관리
        self.is_active = False
        self.is_connected = False
        self.websocket_url = ""
        
        # 메시지 분석용 카운터
        self.message_count = 0
        self.json_message_count = 0
        self.text_message_count = 0
        self.room_related_count = 0
        self.filtered_room_count = 0  # 필터링된 방 카운터
        
        # 연결 상태 체크 타이머
        self.status_check_timer = QTimer()
        self.status_check_timer.timeout.connect(self._check_connection_status)
        
        self.logger.info("🔍 WebSocketHybridService 필터링된 방 분석 모드 초기화")
        self.file_logger.info("=== 필터링된 방 웹소켓 데이터 분석 세션 시작 ===")
        
    def _load_filtered_room_mappings(self):
        """필터링된 방 매핑 로드"""
        try:
            # 필터링 JSON 파일 경로 찾기
            if getattr(sys, 'frozen', False):
                # PyInstaller로 패키징된 경우
                base_dir = os.path.dirname(sys.executable)
                json_paths = [
                    os.path.join(base_dir, "filtered_room_mappings.json"),
                    os.path.join(base_dir, "_internal", "filtered_room_mappings.json")
                ]
            else:
                # 개발 환경
                base_dir = os.path.dirname(os.path.abspath(__file__))
                json_paths = [
                    os.path.join(base_dir, "..", "filtered_room_mappings.json"),
                    os.path.join(os.path.dirname(base_dir), "filtered_room_mappings.json")
                ]
            
            self.filtered_room_ids = set()
            self.room_mappings = {}
            
            # 파일 찾기 및 로드
            for json_path in json_paths:
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        room_mappings = data.get('room_mappings', {})
                        
                        self.filtered_room_ids = set(room_mappings.keys())
                        self.room_mappings = room_mappings
                        
                    self.logger.info(f"📋 필터링 방 목록 로드 완료: {len(self.filtered_room_ids)}개")
                    self.file_logger.info(f"필터링된 방 ID 목록: {list(self.filtered_room_ids)}")
                    
                    # 방 이름들도 로그
                    for room_id, room_name in room_mappings.items():
                        self.file_logger.info(f"  {room_id} → {room_name}")
                    
                    return
            
            # 파일을 찾지 못한 경우
            self.logger.warning("❌ filtered_room_mappings.json 파일을 찾을 수 없습니다.")
            self.filtered_room_ids = set()
            self.room_mappings = {}
            
        except Exception as e:
            self.logger.error(f"필터링 방 목록 로드 실패: {e}")
            self.filtered_room_ids = set()
            self.room_mappings = {}
        
    def _setup_file_logging(self):
        """파일 로깅 설정"""
        try:
            # 로그 디렉토리 생성
            if getattr(sys, 'frozen', False):
                # PyInstaller로 패키징된 경우
                log_dir = os.path.join(os.path.dirname(sys.executable), "logs")
            else:
                # 개발 환경
                log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
            
            os.makedirs(log_dir, exist_ok=True)
            
            # 타임스탬프가 포함된 파일명
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"websocket_filtered_analysis_{timestamp}.log"
            log_filepath = os.path.join(log_dir, log_filename)
            
            # 파일 로거 생성
            self.file_logger = logging.getLogger(f"websocket_filtered_{timestamp}")
            self.file_logger.setLevel(logging.INFO)
            
            # 기존 핸들러 제거 (중복 방지)
            for handler in self.file_logger.handlers[:]:
                self.file_logger.removeHandler(handler)
            
            # 파일 핸들러 추가
            file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
            file_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.file_logger.addHandler(file_handler)
            
            # 파일 경로 저장
            self.log_filepath = log_filepath
            
            self.logger.info(f"📁 필터링된 방 로그 파일: {log_filepath}")
            
        except Exception as e:
            self.logger.error(f"파일 로깅 설정 실패: {e}")
            # 파일 로깅 실패시 더미 로거 생성
            self.file_logger = logging.getLogger("dummy")
            self.log_filepath = None

    def start_websocket_connection(self, websocket_url: str) -> bool:
        """JavaScript 웹소켓 연결 시작"""
        try:
            self.logger.info(f"🔌 필터링된 방 분석용 웹소켓 연결 시작")
            self.logger.info(f"📍 URL: {websocket_url[:100]}...")
            
            if not self.devtools or not self.devtools.driver:
                self.logger.error("DevTools 연결이 없습니다")
                return False
            
            self.websocket_url = websocket_url
            
            # 필터링된 방 분석용 인터셉터 주입
            if not self._inject_filtered_room_interceptor():
                return False
            
            # 웹소켓 연결 시작
            if not self._start_javascript_websocket():
                return False
            
            # 연결 확인
            if not self._verify_connection():
                return False
            
            # 상태 체크 타이머 시작
            self.status_check_timer.start(3000)  # 3초마다 상태 체크
            
            self.is_active = True
            self.connection_status_changed.emit(True)
            
            self.logger.info("✅ 필터링된 방 분석용 웹소켓 연결 성공")
            return True
            
        except Exception as e:
            self.logger.error(f"웹소켓 연결 실패: {e}")
            self.error_occurred.emit(f"연결 실패: {str(e)}")
            return False

    def _inject_filtered_room_interceptor(self) -> bool:
        """필터링된 방 데이터 분석용 인터셉터 주입"""
        try:
            # 필터링된 방에 특화된 JavaScript 코드
            interceptor_script = """
            // 🎯 필터링된 방 데이터 분석 인터셉터
            (function() {
                console.log('🎯 필터링된 방 데이터 분석 모드 시작');
                
                // 분석용 저장소 초기화
                window.wsFilteredAnalysis = {
                    totalMessages: 0,
                    filteredMessages: 0,
                    roomData: new Map(),
                    messageTypes: {},
                    sampleMessages: []
                };
                
                // 원본 WebSocket 백업
                const OriginalWebSocket = window.WebSocket;
                
                // WebSocket 가로채기
                window.WebSocket = function(url, protocols) {
                    console.log('🔗 WebSocket 연결:', url);
                    
                    const ws = new OriginalWebSocket(url, protocols);
                    
                    if (url.includes('evo-games.com')) {
                        console.log('🎮 Evolution WebSocket 감지 - 필터링된 방 분석 모드 활성화');
                        window.gameWebSocket = ws;
                        
                        ws.addEventListener('message', function(event) {
                            const messageData = event.data;
                            window.wsFilteredAnalysis.totalMessages++;
                            
                            // 메시지 타입 분석
                            const msgType = typeof messageData;
                            window.wsFilteredAnalysis.messageTypes[msgType] = (window.wsFilteredAnalysis.messageTypes[msgType] || 0) + 1;
                            
                            let analysisResult = {
                                id: window.wsFilteredAnalysis.totalMessages,
                                timestamp: new Date().toISOString(),
                                type: msgType,
                                length: String(messageData).length,
                                rawData: messageData,
                                isJSON: false,
                                parsedData: null,
                                keys: [],
                                hasRoomInfo: false,
                                roomId: null,
                                roomData: null,
                                hasResults: false,
                                hasDealer: false,
                                hasSeats: false
                            };
                            
                            // JSON 파싱 시도
                            if (typeof messageData === 'string') {
                                try {
                                    if (messageData.trim().startsWith('{') || messageData.trim().startsWith('[')) {
                                        const parsed = JSON.parse(messageData);
                                        analysisResult.isJSON = true;
                                        analysisResult.parsedData = parsed;
                                        
                                        // 키 구조 분석
                                        if (typeof parsed === 'object' && parsed !== null) {
                                            if (Array.isArray(parsed)) {
                                                analysisResult.structure = 'array';
                                                analysisResult.keys = [`length:${parsed.length}`];
                                            } else {
                                                analysisResult.structure = 'object';
                                                analysisResult.keys = Object.keys(parsed);
                                            }
                                            
                                            // 방 데이터 추출 시도
                                            const roomDataResult = extractRoomData(parsed);
                                            if (roomDataResult) {
                                                analysisResult.hasRoomInfo = true;
                                                analysisResult.roomId = roomDataResult.roomId;
                                                analysisResult.roomData = roomDataResult.roomData;
                                                analysisResult.hasResults = roomDataResult.hasResults;
                                                analysisResult.hasDealer = roomDataResult.hasDealer;
                                                analysisResult.hasSeats = roomDataResult.hasSeats;
                                                
                                                // 방 ID를 roomName으로 설정 (기존 로직과 호환)
                                                analysisResult.roomName = roomDataResult.roomId;
                                            }
                                        }
                                        
                                        console.log(`📨 [${window.wsFilteredAnalysis.totalMessages}] JSON 메시지 분석 완료`);
                                        if (analysisResult.roomId) {
                                            console.log(`🏠 방 ID: ${analysisResult.roomId}`);
                                        }
                                    }
                                } catch (e) {
                                    console.log(`❌ [${window.wsFilteredAnalysis.totalMessages}] JSON 파싱 실패:`, e.message);
                                }
                            }
                            
                            // 샘플 메시지 저장 (최근 50개)
                            window.wsFilteredAnalysis.sampleMessages.push(analysisResult);
                            if (window.wsFilteredAnalysis.sampleMessages.length > 50) {
                                window.wsFilteredAnalysis.sampleMessages = window.wsFilteredAnalysis.sampleMessages.slice(-50);
                            }
                            
                            // Python으로 모든 분석 결과 전송 (필터링은 Python에서)
                            if (window.sendFilteredAnalysisResultToPython) {
                                try {
                                    window.sendFilteredAnalysisResultToPython(analysisResult);
                                } catch (error) {
                                    console.error('🚨 Python 전송 오류:', error);
                                }
                            }
                        });
                        
                        ws.addEventListener('open', function() {
                            console.log('✅ Evolution WebSocket 연결 성공');
                        });
                        
                        ws.addEventListener('close', function(event) {
                            console.log('❌ Evolution WebSocket 연결 종료');
                        });
                    }
                    
                    return ws;
                };
                
                // 방 ID 및 게임 데이터 추출 함수
                function extractRoomData(data) {
                    if (!data || typeof data !== 'object') return null;
                    
                    // args 객체에서 방 ID들 찾기
                    if (data.args && typeof data.args === 'object') {
                        const roomIds = Object.keys(data.args);
                        
                        for (const roomId of roomIds) {
                            const roomData = data.args[roomId];
                            
                            // 방 ID 자체를 반환 (딜러 이름 말고)
                            if (roomData && typeof roomData === 'object') {
                                const result = {
                                    roomId: roomId,
                                    roomData: roomData,
                                    hasResults: false,
                                    hasDealer: false,
                                    hasSeats: false
                                };
                                
                                // 게임 결과 데이터 확인
                                if (roomData.results && Array.isArray(roomData.results)) {
                                    result.hasResults = true;
                                    result.resultCount = roomData.results.length;
                                    result.latestResult = roomData.results[roomData.results.length - 1];
                                }
                                
                                // 딜러 정보 확인
                                if (roomData.dealer && roomData.dealer.name) {
                                    result.hasDealer = true;
                                    result.dealerName = roomData.dealer.name;
                                }
                                
                                // 좌석 정보 확인
                                if (roomData.occupied && Array.isArray(roomData.occupied)) {
                                    result.hasSeats = true;
                                    result.occupiedSeats = roomData.occupied.length;
                                }
                                
                                return result;
                            }
                        }
                        
                        // seats 특별 처리
                        if (data.args.seats && typeof data.args.seats === 'object') {
                            const seatRoomIds = Object.keys(data.args.seats);
                            if (seatRoomIds.length > 0) {
                                return {
                                    roomId: seatRoomIds[0], // 첫 번째 방 ID
                                    hasSeats: true,
                                    seatData: data.args.seats,
                                    totalRooms: seatRoomIds.length
                                };
                            }
                        }
                    }
                    
                    return null;
                }
                
                // 분석 결과 조회 함수들
                window.getFilteredAnalysisStats = function() {
                    return {
                        totalMessages: window.wsFilteredAnalysis.totalMessages,
                        filteredMessages: window.wsFilteredAnalysis.filteredMessages,
                        messageTypes: window.wsFilteredAnalysis.messageTypes,
                        roomDataCount: window.wsFilteredAnalysis.roomData.size
                    };
                };
                
                window.getFilteredSampleMessages = function(count = 10) {
                    return window.wsFilteredAnalysis.sampleMessages.slice(-count);
                };
                
                console.log('✅ 필터링된 방 데이터 분석 인터셉터 설치 완료');
            })();
            """
            
            # JavaScript 코드 실행
            result = self.devtools.driver.execute_script(interceptor_script)
            
            self.logger.info("✅ 필터링된 방 데이터 분석 인터셉터 주입 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"인터셉터 주입 실패: {e}")
            return False

    def _start_javascript_websocket(self) -> bool:
        """JavaScript 웹소켓 연결 시작"""
        try:
            callback_script = f"""
            // Python 분석 결과 콜백 함수 설정
            window.sendFilteredAnalysisResultToPython = function(analysisResult) {{
                console.log('📤 필터링 분석 결과 Python 전송:', analysisResult.id);
                
                const event = new CustomEvent('pythonFilteredAnalysisData', {{
                    detail: analysisResult
                }});
                document.dispatchEvent(event);
            }};
            
            document.addEventListener('pythonFilteredAnalysisData', function(event) {{
                window.lastFilteredAnalysisData = event.detail;
                window.lastFilteredAnalysisTimestamp = Date.now();
            }});
            
            // 실제 웹소켓 연결
            try {{
                console.log('🔌 Evolution 웹소켓 연결 시작');
                window.gameWebSocket = new WebSocket('{self.websocket_url}');
                console.log('✅ 웹소켓 연결 객체 생성 완료');
                return true;
            }} catch (wsError) {{
                console.error('🚨 웹소켓 연결 실패:', wsError);
                return false;
            }}
            """
            
            result = self.devtools.driver.execute_script(callback_script)
            
            if result:
                self.logger.info("✅ JavaScript 콜백 및 웹소켓 설정 성공")
                self._start_message_collection()
                return True
            else:
                self.logger.error("JavaScript 콜백 설정 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"JavaScript 웹소켓 시작 실패: {e}")
            return False

    def _start_message_collection(self):
        """메시지 수집 시작"""
        try:
            self.message_collection_timer = QTimer()
            self.message_collection_timer.timeout.connect(self._collect_and_analyze_messages)
            self.message_collection_timer.start(2000)  # 2초마다 수집
            
            self.logger.info("✅ 필터링된 방 메시지 수집 시작")
            
        except Exception as e:
            self.logger.error(f"메시지 수집 시작 오류: {e}")

    def _collect_and_analyze_messages(self):
        """메시지 수집 및 분석"""
        try:
            collection_script = """
            if (window.lastFilteredAnalysisData && window.lastFilteredAnalysisTimestamp) {
                const data = window.lastFilteredAnalysisData;
                const timestamp = window.lastFilteredAnalysisTimestamp;
                
                if (!window.processedFilteredAnalysisTimestamp || timestamp > window.processedFilteredAnalysisTimestamp) {
                    window.processedFilteredAnalysisTimestamp = timestamp;
                    return data;
                }
            }
            return null;
            """
            
            analysis_data = self.devtools.driver.execute_script(collection_script)
            
            if analysis_data:
                self._process_analysis_data(analysis_data)
                
        except Exception as e:
            self.logger.debug(f"메시지 수집 중 오류: {e}")

    def _process_analysis_data(self, analysis_data):
        """분석 데이터 처리 - 필터링된 방만 로깅"""
        try:
            self.message_count += 1
            msg_id = analysis_data.get('id', 0)
            msg_type = analysis_data.get('type', 'unknown')
            is_json = analysis_data.get('isJSON', False)
            has_room_info = analysis_data.get('hasRoomInfo', False)
            room_id = analysis_data.get('roomId')  # 방 ID 우선
            room_name = analysis_data.get('roomName')  # 기존 호환성
            keys = analysis_data.get('keys', [])
            
            # 추가 정보
            has_results = analysis_data.get('hasResults', False)
            has_dealer = analysis_data.get('hasDealer', False)
            has_seats = analysis_data.get('hasSeats', False)
            
            # 카운터 업데이트
            if is_json:
                self.json_message_count += 1
            else:
                self.text_message_count += 1
                
            if has_room_info:
                self.room_related_count += 1
            
            # ✅ 필터링된 방 ID인지 확인
            is_filtered_room = room_id and room_id in self.filtered_room_ids
            
            if is_filtered_room:
                self.filtered_room_count += 1
                # 매핑된 방 이름 가져오기
                mapped_room_name = self.room_mappings.get(room_id, room_id)
            
            # 콘솔 로그 - 필터링된 방만 출력
            if is_filtered_room:
                self.logger.info(f"🎯 [필터링된 방 {self.filtered_room_count}] 방 ID: {room_id}")
                self.logger.info(f"📍 매핑된 방 이름: {mapped_room_name}")
                
                # 게임 결과가 있는 경우 강조
                if has_results:
                    self.logger.info(f"🎮 게임 결과 데이터 발견! 방 ID: {room_id}")
                elif has_dealer:
                    self.logger.info(f"👨‍💼 딜러 정보 업데이트: {room_id}")
                elif has_seats:
                    self.logger.info(f"💺 좌석 정보 업데이트: {room_id}")
            else:
                # 필터링되지 않은 방은 간단한 로그만
                if room_id:
                    self.logger.debug(f"🔍 [기타] 방 ID: {room_id} (필터링 대상 아님)")
                else:
                    self.logger.debug(f"🔍 [분석 {self.message_count}] 일반 메시지")
            
            # 파일 로그 - 필터링된 방만 상세 저장
            if is_filtered_room:
                self.file_logger.info(f"=== 필터링된 방 메시지 분석 {self.filtered_room_count} ===")
                self.file_logger.info(f"메시지 ID: {msg_id}")
                self.file_logger.info(f"방 ID: {room_id}")
                self.file_logger.info(f"매핑된 방 이름: {mapped_room_name}")
                self.file_logger.info(f"메시지 타입: {msg_type}")
                self.file_logger.info(f"JSON 여부: {is_json}")
                self.file_logger.info(f"메시지 길이: {analysis_data.get('length', 0)}")
                self.file_logger.info(f"게임 결과: {has_results}, 딜러 정보: {has_dealer}, 좌석 정보: {has_seats}")
                
                if keys:
                    self.file_logger.info(f"데이터 키들: {', '.join(keys)}")
                
                # 원본 데이터 저장 (처음 200자만)
                raw_data = str(analysis_data.get('rawData', ''))
                self.file_logger.info(f"원본 데이터 (처음 200자): {raw_data[:200]}")
                
                # 중요한 메시지 타입별 처리
                parsed_data = analysis_data.get('parsedData')
                if parsed_data:
                    message_type = parsed_data.get('type', '')
                    
                    if message_type == 'lobby.historyUpdated' and has_results:
                        self.file_logger.info("🎯 게임 결과 업데이트 데이터 (lobby.historyUpdated):")
                        
                        # 게임 결과 개수 세기
                        room_data = parsed_data.get('args', {}).get(room_id, {})
                        results = room_data.get('results', [])
                        
                        self.file_logger.info(f"총 게임 결과 개수: {len(results)}개")
                        
                        # 최근 10개 결과만 추출
                        recent_results = []
                        for result in results[-10:]:  # 최근 10개만
                            if isinstance(result, dict) and 'c' in result:
                                recent_results.append(result['c'])
                        
                        self.file_logger.info(f"최근 10개 결과: {recent_results}")
                        self.file_logger.info(f"가장 최근 결과: {recent_results[-1] if recent_results else 'None'}")
                        
                        # 전체 JSON 저장
                        self.file_logger.info("전체 JSON 데이터:")
                        self.file_logger.info(json.dumps(parsed_data, indent=2, ensure_ascii=False))
                        
                        # 콘솔에도 결과 정보 출력
                        self.logger.info(f"🎯 중요! 게임 결과 업데이트: {room_id} ({len(results)}개 결과)")
                        self.logger.info(f"최근 결과: {recent_results}")
                        
                    elif message_type == 'lobby.infoUpdated' and has_dealer:
                        self.file_logger.info("👨‍💼 딜러 정보 업데이트 (lobby.infoUpdated):")
                        self.file_logger.info(json.dumps(parsed_data, indent=2, ensure_ascii=False))
                        
                    elif is_json and has_room_info:
                        # 기타 방 관련 JSON 데이터
                        json_str = json.dumps(parsed_data, ensure_ascii=False)
                        if len(json_str) > 1000:
                            self.file_logger.info(f"방 관련 JSON (처음 1000자): {json_str[:1000]}...")
                        else:
                            self.file_logger.info(f"방 관련 JSON: {json_str}")
                
                self.file_logger.info("-" * 60)
                
                # 필터링된 방 데이터를 별도 파일에도 저장
                self._save_filtered_room_data(analysis_data, mapped_room_name)
            
            # 3개 필터링된 메시지마다 통계 출력
            if self.filtered_room_count > 0 and self.filtered_room_count % 3 == 0:
                self._log_filtered_statistics()
                
        except Exception as e:
            self.logger.error(f"분석 데이터 처리 오류: {e}")
            self.file_logger.error(f"분석 데이터 처리 오류: {e}")

    def _save_filtered_room_data(self, analysis_data, mapped_room_name):
        """필터링된 방 데이터를 별도 파일에 저장"""
        try:
            if not self.log_filepath:
                return
                
            # 필터링된 방 데이터 전용 파일명
            filtered_log_path = self.log_filepath.replace('.log', '_filtered_rooms.json')
            
            room_data = {
                'timestamp': analysis_data.get('timestamp'),
                'message_id': analysis_data.get('id'),
                'room_id': analysis_data.get('roomId'),
                'mapped_room_name': mapped_room_name,  # 매핑된 한글 이름
                'message_type': analysis_data.get('parsedData', {}).get('type'),
                'has_results': analysis_data.get('hasResults', False),
                'has_dealer': analysis_data.get('hasDealer', False),
                'has_seats': analysis_data.get('hasSeats', False),
                'keys': analysis_data.get('keys'),
                'parsed_data': analysis_data.get('parsedData'),
                'raw_data': str(analysis_data.get('rawData', ''))[:500]  # 원본 500자만
            }
            
            # 게임 결과가 있는 경우 추가 정보 추출
            if analysis_data.get('hasResults'):
                parsed_data = analysis_data.get('parsedData', {})
                room_id = analysis_data.get('roomId')
                
                if parsed_data.get('args') and room_id in parsed_data['args']:
                    room_args = parsed_data['args'][room_id]
                    results = room_args.get('results', [])
                    
                    # 결과 개수와 최근 결과들 추출
                    room_data['total_results'] = len(results)
                    
                    # 최근 10개 결과 추출 (c 값만)
                    recent_results = []
                    for result in results[-10:]:
                        if isinstance(result, dict) and 'c' in result:
                            recent_results.append(result['c'])
                    
                    room_data['recent_10_results'] = recent_results
                    room_data['latest_result'] = recent_results[-1] if recent_results else None
                    
                    # 전체 결과 추출 (c 값만)
                    all_results = []
                    for result in results:
                        if isinstance(result, dict) and 'c' in result:
                            all_results.append(result['c'])
                    
                    room_data['all_results'] = all_results
            
            # 기존 파일이 있으면 읽어서 추가
            filtered_data_list = []
            if os.path.exists(filtered_log_path):
                try:
                    with open(filtered_log_path, 'r', encoding='utf-8') as f:
                        filtered_data_list = json.load(f)
                except:
                    filtered_data_list = []
            
            filtered_data_list.append(room_data)
            
            # 파일에 저장 (최대 100개까지)
            if len(filtered_data_list) > 100:
                filtered_data_list = filtered_data_list[-100:]
            
            with open(filtered_log_path, 'w', encoding='utf-8') as f:
                json.dump(filtered_data_list, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"📄 필터링된 방 데이터 저장: {analysis_data.get('roomId', '알 수 없음')}")
            
        except Exception as e:
            self.logger.error(f"필터링된 방 데이터 저장 실패: {e}")
    
    def _log_filtered_statistics(self):
        """필터링된 방 통계 로그 출력"""
        try:
            # 콘솔에는 간단한 통계만
            self.logger.info("📊 === 필터링된 방 통계 ===")
            self.logger.info(f"총 메시지: {self.message_count}개 | 필터링된 방: {self.filtered_room_count}개")
            self.logger.info(f"필터링 비율: {(self.filtered_room_count/self.message_count*100):.1f}%")
            
            # 파일에는 상세 통계
            self.file_logger.info("📊 === 상세 필터링 통계 ===")
            self.file_logger.info(f"총 메시지: {self.message_count}")
            self.file_logger.info(f"필터링된 방 메시지: {self.filtered_room_count}")
            self.file_logger.info(f"일반 방 메시지: {self.message_count - self.filtered_room_count}")
            self.file_logger.info(f"필터링 대상 방 개수: {len(self.filtered_room_ids)}")
            self.file_logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"필터링 통계 로그 출력 오류: {e}")
            self.file_logger.error(f"필터링 통계 로그 출력 오류: {e}")

    def _verify_connection(self) -> bool:
        """연결 확인"""
        try:
            max_wait_time = 10
            check_interval = 0.5
            
            for attempt in range(int(max_wait_time / check_interval)):
                verification_script = """
                if (window.gameWebSocket) {
                    return {
                        connected: window.gameWebSocket.readyState === 1,
                        readyState: window.gameWebSocket.readyState,
                        url: window.gameWebSocket.url
                    };
                }
                return { connected: false, readyState: -1 };
                """
                
                result = self.devtools.driver.execute_script(verification_script)
                
                if result and result.get('connected'):
                    self.is_connected = True
                    self.logger.info(f"✅ 웹소켓 연결 확인됨")
                    return True
                
                time.sleep(check_interval)
            
            self.logger.warning("❌ 웹소켓 연결 확인 실패")
            return False
                
        except Exception as e:
            self.logger.error(f"연결 확인 오류: {e}")
            return False

    def _check_connection_status(self):
        """주기적 연결 상태 체크"""
        try:
            status_script = """
            const stats = window.getFilteredAnalysisStats ? window.getFilteredAnalysisStats() : null;
            return {
                connected: window.gameWebSocket ? window.gameWebSocket.readyState === 1 : false,
                totalMessages: stats ? stats.totalMessages : 0,
                filteredMessages: stats ? stats.filteredMessages : 0
            };
            """
            
            status = self.devtools.driver.execute_script(status_script)
            
            if status:
                was_connected = self.is_connected
                self.is_connected = status.get('connected', False)
                
                if was_connected != self.is_connected:
                    self.connection_status_changed.emit(self.is_connected)
                
        except Exception as e:
            self.logger.debug(f"연결 상태 체크 오류: {e}")

    def get_detailed_analysis(self):
        """상세 분석 결과 반환 - 필터링된 방 중심"""
        try:
            analysis_script = """
            const stats = window.getFilteredAnalysisStats();
            const samples = window.getFilteredSampleMessages(10);
            
            return {
                statistics: stats,
                sampleMessages: samples
            };
            """
            
            result = self.devtools.driver.execute_script(analysis_script)
            
            if result:
                # 콘솔에는 요약만
                self.logger.info("📋 === 필터링된 방 분석 결과 요약 ===")
                
                stats = result.get('statistics', {})
                self.logger.info(f"총 메시지: {stats.get('totalMessages', 0)}")
                self.logger.info(f"필터링된 방: {self.filtered_room_count}")
                self.logger.info(f"로그 파일 확인: {self.log_filepath}")
                
                # 파일에는 전체 결과 저장
                self.file_logger.info("📋 === 최종 필터링된 방 분석 결과 ===")
                
                # 필터링된 방들의 상세 분석 결과
                filtered_stats = result.get('statistics', {})
                self.file_logger.info(f"총 메시지: {filtered_stats.get('totalMessages', 0)}")
                self.file_logger.info(f"필터링된 방 관련: {self.filtered_room_count}")
                
                # 필터링된 방 목록 요약
                self.file_logger.info("📋 필터링된 방 목록:")
                for room_id, room_name in self.room_mappings.items():
                    self.file_logger.info(f"  {room_id} → {room_name}")
                
                self.file_logger.info("=" * 80)
                self.file_logger.info("=== 필터링된 방 분석 세션 종료 ===")
                
                return result
            
        except Exception as e:
            self.logger.error(f"상세 분석 결과 조회 오류: {e}")
            self.file_logger.error(f"상세 분석 결과 조회 오류: {e}")
            return None

    def stop_websocket_connection(self):
        """웹소켓 연결 중지"""
        try:
            if not self.is_active:
                return
                
            self.logger.info("🛑 필터링된 방 분석용 웹소켓 연결 중지")
            
            # 타이머 중지
            if hasattr(self, 'status_check_timer'):
                self.status_check_timer.stop()
            
            if hasattr(self, 'message_collection_timer'):
                self.message_collection_timer.stop()
            
            # 최종 분석 결과 출력
            self.get_detailed_analysis()
            
            # JavaScript 정리
            cleanup_script = """
            if (window.gameWebSocket) {
                try {
                    window.gameWebSocket.close();
                } catch(e) {
                    console.log('WebSocket 정리 중 오류:', e);
                }
            }
            console.log('🛑 필터링된 방 데이터 분석 WebSocket 정리 완료');
            """
            
            self.devtools.driver.execute_script(cleanup_script)
            
            # 상태 초기화
            self.is_active = False
            self.is_connected = False
            
            self.connection_status_changed.emit(False)
            self.logger.info("✅ 필터링된 방 분석용 웹소켓 중지 완료")
            
        except Exception as e:
            self.logger.error(f"웹소켓 중지 중 오류: {e}")

    def get_connection_status(self) -> Dict[str, Any]:
        """연결 상태 정보 반환"""
        try:
            return {
                'active': self.is_active,
                'connected': self.is_connected,
                'websocket_url': self.websocket_url,
                'total_messages': self.message_count,
                'filtered_room_messages': self.filtered_room_count,
                'filtering_ratio': (self.filtered_room_count/self.message_count*100) if self.message_count > 0 else 0,
                'total_filtered_rooms': len(self.filtered_room_ids)
            }
            
        except Exception as e:
            self.logger.error(f"연결 상태 확인 오류: {e}")
            return {'active': self.is_active, 'connected': False, 'error': str(e)}

    def force_reconnect(self) -> bool:
        """강제 재연결"""
        try:
            self.logger.info("🔄 필터링된 방 분석용 웹소켓 강제 재연결")
            self.stop_websocket_connection()
            time.sleep(2)
            
            if self.websocket_url:
                return self.start_websocket_connection(self.websocket_url)
            else:
                self.logger.error("재연결할 URL이 없습니다")
                return False
                
        except Exception as e:
            self.logger.error(f"강제 재연결 오류: {e}")
            return False

    def get_filtered_room_file_path(self):
        """필터링된 방 데이터 파일 경로 반환"""
        if self.log_filepath:
            return self.log_filepath.replace('.log', '_filtered_rooms.json')
        return None

    def get_filtering_stats(self):
        """필터링 통계 반환"""
        return {
            'total_messages': self.message_count,
            'filtered_room_messages': self.filtered_room_count,
            'filtering_ratio': (self.filtered_room_count/self.message_count*100) if self.message_count > 0 else 0,
            'total_filtered_rooms': len(self.filtered_room_ids),
            'room_mappings': self.room_mappings
        }

    def get_log_file_path(self):
        """로그 파일 경로 반환"""
        return self.log_filepath
    
    def get_room_data_file_path(self):
        """방 데이터 파일 경로 반환 (호환성)"""
        return self.get_filtered_room_file_path()

    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            self.stop_websocket_connection()
        except:
            pass