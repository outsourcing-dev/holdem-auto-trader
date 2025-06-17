# services/websocket_parser.py - 실용적 접근 방식
import json
import time
import logging
import re
from typing import Optional, Dict, Any, List
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedAlertPresentException


class WebSocketParser:
    """에볼루션 로비에서 웹소켓 URL을 자동으로 파싱하는 서비스 - 실용적 접근"""
    
    def __init__(self, devtools):
        self.devtools = devtools
        self.driver = devtools.driver
        self.logger = logging.getLogger(__name__)
        self.websocket_url = None
        
    def parse_websocket_url_from_lobby(self, timeout=30) -> Optional[str]:
        """
        에볼루션 로비에서 웹소켓 URL을 자동으로 파싱합니다.
        
        Args:
            timeout (int): 타임아웃 시간 (초)
            
        Returns:
            Optional[str]: 파싱된 웹소켓 URL 또는 None
        """
        try:
            self.logger.info("웹소켓 URL 자동 파싱 시작")
            
            # 1. 가장 확실한 방법: 개발자 도구 콘솔에서 직접 실행
            websocket_url = self._extract_with_console_injection()
            if websocket_url:
                return websocket_url
            
            # 2. WebSocket 생성 감지를 위한 고급 JavaScript 주입
            websocket_url = self._advanced_javascript_monitoring(timeout)
            if websocket_url:
                return websocket_url
            
            # 3. 네트워크 계층에서 직접 감지
            websocket_url = self._network_layer_detection()
            if websocket_url:
                return websocket_url
            
            # 4. 페이지의 모든 script 태그에서 검색
            websocket_url = self._search_in_script_tags()
            if websocket_url:
                return websocket_url
            
            # 5. 에볼루션 특화 패턴으로 전체 DOM 검색
            websocket_url = self._evolution_specific_search()
            if websocket_url:
                return websocket_url
            
            self.logger.warning("모든 방법으로 웹소켓 URL을 찾을 수 없습니다.")
            return None
                
        except Exception as e:
            self.logger.error(f"웹소켓 URL 파싱 중 오류: {e}")
            return None
    
    def _extract_with_console_injection(self) -> Optional[str]:
        """콘솔에 WebSocket 감지 스크립트 주입"""
        try:
            self.logger.info("콘솔 스크립트 주입으로 웹소켓 URL 검색 중...")
            
            # 매우 강력한 WebSocket 감지 스크립트
            detection_script = """
            (function() {
                // 기존 WebSocket 연결들 검색
                function findExistingConnections() {
                    var foundUrls = [];
                    
                    // Performance API에서 WebSocket 검색
                    try {
                        var entries = performance.getEntriesByType('resource');
                        for (var i = 0; i < entries.length; i++) {
                            var entry = entries[i];
                            if (entry.name && (entry.name.indexOf('ws://') === 0 || entry.name.indexOf('wss://') === 0)) {
                                if (entry.name.indexOf('evo-games.com') !== -1 || 
                                    entry.name.indexOf('skylinestart') !== -1 ||
                                    entry.name.indexOf('EVOSESSIONID') !== -1) {
                                    foundUrls.push(entry.name);
                                }
                            }
                        }
                    } catch (e) {}
                    
                    return foundUrls;
                }
                
                // 현재 활성화된 WebSocket 인스턴스 검색
                function findActiveWebSockets() {
                    var foundUrls = [];
                    
                    // window 객체에서 WebSocket 인스턴스 검색
                    function searchObject(obj, visited) {
                        if (visited.has(obj) || !obj || typeof obj !== 'object') return;
                        visited.add(obj);
                        
                        try {
                            for (var key in obj) {
                                if (key && obj[key]) {
                                    if (obj[key] instanceof WebSocket) {
                                        var url = obj[key].url;
                                        if (url && (url.indexOf('evo-games.com') !== -1 || 
                                                   url.indexOf('skylinestart') !== -1 ||
                                                   url.indexOf('EVOSESSIONID') !== -1)) {
                                            foundUrls.push(url);
                                        }
                                    } else if (typeof obj[key] === 'object') {
                                        searchObject(obj[key], visited);
                                    }
                                }
                            }
                        } catch (e) {}
                    }
                    
                    searchObject(window, new Set());
                    return foundUrls;
                }
                
                // 모든 iframe에서도 검색
                function searchInFrames() {
                    var foundUrls = [];
                    
                    try {
                        for (var i = 0; i < window.frames.length; i++) {
                            try {
                                var frame = window.frames[i];
                                if (frame && frame.WebSocket) {
                                    // iframe 내부의 WebSocket 인스턴스 검색
                                    var frameEntries = frame.performance ? frame.performance.getEntriesByType('resource') : [];
                                    for (var j = 0; j < frameEntries.length; j++) {
                                        var entry = frameEntries[j];
                                        if (entry.name && (entry.name.indexOf('ws://') === 0 || entry.name.indexOf('wss://') === 0)) {
                                            if (entry.name.indexOf('evo-games.com') !== -1 || 
                                                entry.name.indexOf('skylinestart') !== -1 ||
                                                entry.name.indexOf('EVOSESSIONID') !== -1) {
                                                foundUrls.push(entry.name);
                                            }
                                        }
                                    }
                                }
                            } catch (e) {}
                        }
                    } catch (e) {}
                    
                    return foundUrls;
                }
                
                // 모든 방법으로 검색
                var allUrls = [];
                allUrls = allUrls.concat(findExistingConnections());
                allUrls = allUrls.concat(findActiveWebSockets());
                allUrls = allUrls.concat(searchInFrames());
                
                // 중복 제거
                var uniqueUrls = [];
                for (var i = 0; i < allUrls.length; i++) {
                    if (uniqueUrls.indexOf(allUrls[i]) === -1) {
                        uniqueUrls.push(allUrls[i]);
                    }
                }
                
                return uniqueUrls;
            })();
            """
            
            # 스크립트 실행
            found_urls = self.driver.execute_script(detection_script)
            
            if found_urls and isinstance(found_urls, list):
                for url in found_urls:
                    if self._is_evolution_websocket(url):
                        self.logger.info(f"콘솔 스크립트로 웹소켓 URL 발견: {url}")
                        return url
            
            return None
            
        except Exception as e:
            self.logger.warning(f"콘솔 스크립트 주입 실패: {e}")
            return None
    
    def _advanced_javascript_monitoring(self, timeout=30) -> Optional[str]:
        """고급 JavaScript 모니터링"""
        try:
            self.logger.info("고급 JavaScript 모니터링 시작")
            
            # WebSocket 생성자를 완전히 대체하는 스크립트
            monitoring_script = """
            if (!window._websocketMonitor) {
                window._websocketMonitor = {
                    capturedUrls: [],
                    originalWebSocket: window.WebSocket,
                    
                    install: function() {
                        var self = this;
                        
                        // WebSocket 생성자 완전 대체
                        window.WebSocket = function(url, protocols) {
                            console.log('WebSocket 생성 감지:', url);
                            
                            // URL 저장
                            self.capturedUrls.push(url);
                            
                            // 원본 WebSocket 생성
                            var ws = new self.originalWebSocket(url, protocols);
                            
                            // 이벤트 리스너 추가하여 연결 상태 모니터링
                            ws.addEventListener('open', function() {
                                console.log('WebSocket 연결 열림:', url);
                            });
                            
                            ws.addEventListener('close', function() {
                                console.log('WebSocket 연결 닫힘:', url);
                            });
                            
                            return ws;
                        };
                        
                        // 원본 프로토타입과 상수들 복사
                        window.WebSocket.prototype = self.originalWebSocket.prototype;
                        window.WebSocket.CONNECTING = self.originalWebSocket.CONNECTING;
                        window.WebSocket.OPEN = self.originalWebSocket.OPEN;
                        window.WebSocket.CLOSING = self.originalWebSocket.CLOSING;
                        window.WebSocket.CLOSED = self.originalWebSocket.CLOSED;
                    },
                    
                    getUrls: function() {
                        return this.capturedUrls;
                    },
                    
                    reset: function() {
                        this.capturedUrls = [];
                    }
                };
                
                window._websocketMonitor.install();
            }
            
            window._websocketMonitor.reset();
            return true;
            """
            
            # 모니터링 스크립트 설치
            self.driver.execute_script(monitoring_script)
            
            # 페이지 새로고침하여 WebSocket 연결 유도
            self.logger.info("페이지 새로고침하여 WebSocket 연결 유도")
            self.driver.refresh()
            time.sleep(3)
            
            # 일정 시간 동안 모니터링
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # 감지된 URL 확인
                    detected_urls = self.driver.execute_script("return window._websocketMonitor ? window._websocketMonitor.getUrls() : [];")
                    
                    if detected_urls:
                        for url in detected_urls:
                            if self._is_evolution_websocket(url):
                                self.logger.info(f"고급 JavaScript 모니터링으로 웹소켓 URL 발견: {url}")
                                return url
                    
                    time.sleep(2)
                    
                except Exception as e:
                    self.logger.warning(f"모니터링 중 오류: {e}")
                    time.sleep(2)
            
            return None
            
        except Exception as e:
            self.logger.warning(f"고급 JavaScript 모니터링 실패: {e}")
            return None
    
    def _network_layer_detection(self) -> Optional[str]:
        """네트워크 계층에서 직접 감지"""
        try:
            self.logger.info("네트워크 계층 감지 시작")
            
            # Chrome DevTools Protocol 사용 (다른 접근법)
            network_script = """
            // 모든 가능한 네트워크 정보 수집
            var networkInfo = {
                performance: [],
                navigation: [],
                timing: []
            };
            
            try {
                // Performance entries
                var perfEntries = performance.getEntriesByType('resource');
                for (var i = 0; i < perfEntries.length; i++) {
                    var entry = perfEntries[i];
                    if (entry.name && entry.name.length > 0) {
                        networkInfo.performance.push(entry.name);
                    }
                }
                
                // Navigation entries
                var navEntries = performance.getEntriesByType('navigation');
                for (var i = 0; i < navEntries.length; i++) {
                    var entry = navEntries[i];
                    if (entry.name && entry.name.length > 0) {
                        networkInfo.navigation.push(entry.name);
                    }
                }
                
                // Timing entries (experimental)
                try {
                    var timingEntries = performance.getEntriesByType('measure');
                    for (var i = 0; i < timingEntries.length; i++) {
                        var entry = timingEntries[i];
                        if (entry.name && entry.name.length > 0) {
                            networkInfo.timing.push(entry.name);
                        }
                    }
                } catch (e) {}
                
            } catch (e) {
                console.error('Network info collection error:', e);
            }
            
            return networkInfo;
            """
            
            network_info = self.driver.execute_script(network_script)
            
            # 모든 네트워크 정보에서 WebSocket URL 검색
            all_urls = []
            if isinstance(network_info, dict):
                for category, urls in network_info.items():
                    if isinstance(urls, list):
                        all_urls.extend(urls)
            
            for url in all_urls:
                if isinstance(url, str) and self._is_evolution_websocket(url):
                    self.logger.info(f"네트워크 계층에서 웹소켓 URL 발견: {url}")
                    return url
            
            return None
            
        except Exception as e:
            self.logger.warning(f"네트워크 계층 감지 실패: {e}")
            return None
    
    def _search_in_script_tags(self) -> Optional[str]:
        """모든 script 태그에서 WebSocket URL 검색"""
        try:
            self.logger.info("Script 태그에서 웹소켓 URL 검색 중...")
            
            # 모든 script 태그의 내용 가져오기
            script_contents = self.driver.execute_script("""
                var scripts = document.getElementsByTagName('script');
                var contents = [];
                
                for (var i = 0; i < scripts.length; i++) {
                    var script = scripts[i];
                    if (script.innerHTML && script.innerHTML.length > 0) {
                        contents.push(script.innerHTML);
                    }
                    if (script.src && script.src.length > 0) {
                        contents.push(script.src);
                    }
                }
                
                return contents;
            """)
            
            if script_contents:
                for content in script_contents:
                    if isinstance(content, str):
                        websocket_url = self._extract_websocket_from_text(content)
                        if websocket_url:
                            self.logger.info(f"Script 태그에서 웹소켓 URL 발견: {websocket_url}")
                            return websocket_url
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Script 태그 검색 실패: {e}")
            return None
    
    def _evolution_specific_search(self) -> Optional[str]:
        """에볼루션 특화 패턴으로 전체 DOM 검색"""
        try:
            self.logger.info("에볼루션 특화 검색 시작")
            
            # 에볼루션 게임에서 사용하는 특정 패턴 검색
            evolution_search_script = """
            var foundUrls = [];
            
            // 1. 모든 data 속성에서 검색
            var allElements = document.querySelectorAll('*');
            for (var i = 0; i < allElements.length; i++) {
                var element = allElements[i];
                var attributes = element.attributes;
                
                for (var j = 0; j < attributes.length; j++) {
                    var attr = attributes[j];
                    if (attr.value && (attr.value.indexOf('wss://') === 0 || attr.value.indexOf('ws://') === 0)) {
                        if (attr.value.indexOf('evo-games.com') !== -1 || 
                            attr.value.indexOf('skylinestart') !== -1 ||
                            attr.value.indexOf('EVOSESSIONID') !== -1) {
                            foundUrls.push(attr.value);
                        }
                    }
                }
            }
            
            // 2. window 객체의 모든 프로퍼티에서 검색
            function searchWindowProperties(obj, depth) {
                if (depth > 3 || !obj || typeof obj !== 'object') return;
                
                try {
                    for (var key in obj) {
                        if (typeof obj[key] === 'string') {
                            if ((obj[key].indexOf('wss://') === 0 || obj[key].indexOf('ws://') === 0) &&
                                (obj[key].indexOf('evo-games.com') !== -1 || 
                                 obj[key].indexOf('skylinestart') !== -1 ||
                                 obj[key].indexOf('EVOSESSIONID') !== -1)) {
                                foundUrls.push(obj[key]);
                            }
                        } else if (typeof obj[key] === 'object' && obj[key] !== null) {
                            searchWindowProperties(obj[key], depth + 1);
                        }
                    }
                } catch (e) {}
            }
            
            searchWindowProperties(window, 0);
            
            // 3. 모든 iframe에서도 검색
            var iframes = document.querySelectorAll('iframe');
            for (var i = 0; i < iframes.length; i++) {
                try {
                    var iframeDoc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                    if (iframeDoc) {
                        var iframeElements = iframeDoc.querySelectorAll('*');
                        for (var j = 0; j < iframeElements.length; j++) {
                            var element = iframeElements[j];
                            var attributes = element.attributes;
                            
                            for (var k = 0; k < attributes.length; k++) {
                                var attr = attributes[k];
                                if (attr.value && (attr.value.indexOf('wss://') === 0 || attr.value.indexOf('ws://') === 0)) {
                                    if (attr.value.indexOf('evo-games.com') !== -1 || 
                                        attr.value.indexOf('skylinestart') !== -1 ||
                                        attr.value.indexOf('EVOSESSIONID') !== -1) {
                                        foundUrls.push(attr.value);
                                    }
                                }
                            }
                        }
                    }
                } catch (e) {}
            }
            
            // 중복 제거
            var uniqueUrls = [];
            for (var i = 0; i < foundUrls.length; i++) {
                if (uniqueUrls.indexOf(foundUrls[i]) === -1) {
                    uniqueUrls.push(foundUrls[i]);
                }
            }
            
            return uniqueUrls;
            """
            
            found_urls = self.driver.execute_script(evolution_search_script)
            
            if found_urls and isinstance(found_urls, list):
                for url in found_urls:
                    if self._is_evolution_websocket(url):
                        self.logger.info(f"에볼루션 특화 검색으로 웹소켓 URL 발견: {url}")
                        return url
            
            return None
            
        except Exception as e:
            self.logger.warning(f"에볼루션 특화 검색 실패: {e}")
            return None
    
    def _extract_websocket_from_text(self, text: str) -> Optional[str]:
        """텍스트에서 웹소켓 URL 추출"""
        try:
            # 더 정확한 에볼루션 웹소켓 URL 패턴
            patterns = [
                r'wss://[^\s"\'<>]+\.evo-games\.com[^\s"\'<>]*EVOSESSIONID[^\s"\'<>]*',
                r'wss://skylinestart[^\s"\'<>]*EVOSESSIONID[^\s"\'<>]*',
                r'wss://[^\s"\'<>]*skylinestart[^\s"\'<>]*',
                r'wss://[^\s"\'<>]+/public/lobby/socket[^\s"\'<>]*'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if self._is_evolution_websocket(match):
                        return match
            
            return None
            
        except Exception as e:
            self.logger.warning(f"텍스트에서 웹소켓 URL 추출 실패: {e}")
            return None
    
    def _is_evolution_websocket(self, url: str) -> bool:
        """에볼루션 웹소켓 URL인지 확인 - 더 엄격한 검증"""
        try:
            if not url or not isinstance(url, str):
                return False
            
            url_lower = url.lower()
            
            # 웹소켓 프로토콜 확인
            if not (url_lower.startswith('ws://') or url_lower.startswith('wss://')):
                return False
            
            # 필수 패턴들
            required_patterns = [
                ('evo-games.com', 'skylinestart'),  # 도메인 패턴 중 하나
                'evosessionid'  # 세션 ID 필수
            ]
            
            # 첫 번째 그룹: 도메인 패턴 중 하나는 반드시 있어야 함
            domain_found = any(pattern in url_lower for pattern in required_patterns[0])
            
            # 두 번째: 세션 ID 필수
            session_found = required_patterns[1] in url_lower
            
            # 추가 검증: URL 길이와 파라미터
            has_params = '?' in url and '&' in url
            sufficient_length = len(url) > 80
            
            return domain_found and session_found and has_params and sufficient_length
            
        except Exception as e:
            self.logger.warning(f"웹소켓 URL 검증 중 오류: {e}")
            return False
    
    def validate_websocket_url(self, url: str) -> bool:
        """웹소켓 URL 유효성 검증"""
        return self._is_evolution_websocket(url)
    
    def get_websocket_url_with_manual_help(self) -> Optional[str]:
        """수동 도움 없이 추가 시도"""
        try:
            self.logger.info("추가 검색 방법 시도")
            
            # 마지막 시도: 매우 광범위한 검색
            final_attempt_script = """
            var allPossibleUrls = [];
            
            // 1. 전역 객체의 모든 문자열 검색
            function deepSearch(obj, visited, depth) {
                if (depth > 5 || !obj || visited.has(obj)) return;
                visited.add(obj);
                
                try {
                    if (typeof obj === 'string') {
                        if (obj.indexOf('wss://') === 0 || obj.indexOf('ws://') === 0) {
                            allPossibleUrls.push(obj);
                        }
                    } else if (typeof obj === 'object' && obj !== null) {
                        Object.keys(obj).forEach(function(key) {
                            try {
                                deepSearch(obj[key], visited, depth + 1);
                            } catch (e) {}
                        });
                    }
                } catch (e) {}
            }
            
            deepSearch(window, new Set(), 0);
            
            // 2. 모든 전역 변수 검색
            Object.keys(window).forEach(function(key) {
                try {
                    var value = window[key];
                    if (typeof value === 'string' && (value.indexOf('wss://') === 0 || value.indexOf('ws://') === 0)) {
                        allPossibleUrls.push(value);
                    }
                } catch (e) {}
            });
            
            // 3. 모든 이벤트 리스너에서 검색
            try {
                var allElements = document.querySelectorAll('*');
                for (var i = 0; i < allElements.length; i++) {
                    var element = allElements[i];
                    if (element.onclick && element.onclick.toString) {
                        var funcStr = element.onclick.toString();
                        var wsMatches = funcStr.match(/wss?:\/\/[^\s"']+/g);
                        if (wsMatches) {
                            allPossibleUrls = allPossibleUrls.concat(wsMatches);
                        }
                    }
                }
            } catch (e) {}
            
            return allPossibleUrls;
            """
            
            found_urls = self.driver.execute_script(final_attempt_script)
            
            if found_urls:
                for url in found_urls:
                    if self._is_evolution_websocket(url):
                        self.logger.info(f"최종 시도로 웹소켓 URL 발견: {url}")
                        return url
            
            return None
            
        except Exception as e:
            self.logger.error(f"최종 시도 실패: {e}")
            return None