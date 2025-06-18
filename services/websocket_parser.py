# services/websocket_parser.py (Performance Logging 없는 버전)
import time
import json
import logging
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

class WebSocketParser:
    def __init__(self, devtools, logger=None):
        """WebSocketParser 초기화"""
        self.devtools = devtools
        self.logger = logger or logging.getLogger(__name__)
        
    def parse_websocket_url_from_lobby(self, timeout=60):
        """Performance Logging 없이 웹소켓 URL 파싱"""
        try:
            self.logger.info("🚀 Performance Logging 없는 웹소켓 URL 파싱 시작")
            
            # Step 1: 강력한 JavaScript 후킹 설정
            self._setup_comprehensive_websocket_hooks()
            
            # Step 2: 다양한 네트워크 활동으로 웹소켓 연결 유도
            websocket_url = self._trigger_websocket_connections(timeout)
            
            if websocket_url:
                self.logger.info(f"✅ 웹소켓 URL 추출 성공: {websocket_url[:100]}...")
                return websocket_url
            
            # Step 3: 최후의 수단 - 페이지 분석 및 패턴 매칭
            self.logger.info("🔍 최후의 수단: 페이지 분석 및 패턴 매칭")
            return self._extract_websocket_from_page_analysis()
            
        except Exception as e:
            self.logger.error(f"웹소켓 URL 파싱 중 오류: {e}", exc_info=True)
            return None

    def _setup_comprehensive_websocket_hooks(self):
        """포괄적인 웹소켓 후킹 설정"""
        try:
            comprehensive_hook_script = """
            // 포괄적인 웹소켓 감지 시스템 설정
            window.websocketCapture = window.websocketCapture || {
                urls: [],
                connections: [],
                originalMethods: {},
                hookSetup: false
            };
            
            if (!window.websocketCapture.hookSetup) {
                const capture = window.websocketCapture;
                
                // 1. WebSocket 생성자 후킹
                capture.originalMethods.WebSocket = window.WebSocket;
                window.WebSocket = function(url, protocols) {
                    console.log('🔗 WebSocket 후킹 감지:', url);
                    capture.urls.push(url);
                    
                    const ws = new capture.originalMethods.WebSocket(url, protocols);
                    capture.connections.push(ws);
                    
                    // 모든 이벤트 감지
                    ['open', 'close', 'error', 'message'].forEach(eventType => {
                        ws.addEventListener(eventType, function(event) {
                            console.log(`📡 WebSocket ${eventType}:`, url);
                            if (eventType === 'open') {
                                console.log('✅ WebSocket 연결 성공:', url);
                            }
                        });
                    });
                    
                    return ws;
                };
                
                // 2. XMLHttpRequest 후킹 (Upgrade 헤더 확인)
                capture.originalMethods.XMLHttpRequest = window.XMLHttpRequest;
                window.XMLHttpRequest = function() {
                    const xhr = new capture.originalMethods.XMLHttpRequest();
                    const originalOpen = xhr.open;
                    const originalSetRequestHeader = xhr.setRequestHeader;
                    
                    let requestUrl = '';
                    let hasUpgradeHeader = false;
                    
                    xhr.open = function(method, url, ...args) {
                        requestUrl = url;
                        return originalOpen.apply(this, [method, url, ...args]);
                    };
                    
                    xhr.setRequestHeader = function(header, value) {
                        if (header.toLowerCase() === 'upgrade' && value.toLowerCase() === 'websocket') {
                            hasUpgradeHeader = true;
                            console.log('🔄 WebSocket Upgrade 요청 감지:', requestUrl);
                            
                            // HTTP URL을 WebSocket URL로 변환
                            let wsUrl = requestUrl;
                            if (wsUrl.startsWith('http://')) {
                                wsUrl = wsUrl.replace('http://', 'ws://');
                            } else if (wsUrl.startsWith('https://')) {
                                wsUrl = wsUrl.replace('https://', 'wss://');
                            }
                            capture.urls.push(wsUrl);
                        }
                        return originalSetRequestHeader.apply(this, [header, value]);
                    };
                    
                    return xhr;
                };
                
                // 3. fetch API 후킹
                if (window.fetch) {
                    capture.originalMethods.fetch = window.fetch;
                    window.fetch = function(url, options = {}) {
                        if (typeof url === 'string') {
                            if (url.includes('ws://') || url.includes('wss://') || 
                                (options.headers && options.headers.upgrade === 'websocket')) {
                                console.log('🌐 fetch에서 WebSocket 관련 요청 감지:', url);
                                capture.urls.push(url);
                            }
                        }
                        return capture.originalMethods.fetch.apply(this, arguments);
                    };
                }
                
                // 4. EventSource 후킹 (Server-Sent Events)
                if (window.EventSource) {
                    capture.originalMethods.EventSource = window.EventSource;
                    window.EventSource = function(url, options) {
                        console.log('📡 EventSource 감지:', url);
                        // EventSource URL에서 WebSocket URL 추론
                        if (url.includes('evolution') || url.includes('evo')) {
                            let wsUrl = url.replace(/\\/sse|\\/events|\\/stream/gi, '/socket');
                            if (wsUrl.startsWith('http://')) {
                                wsUrl = wsUrl.replace('http://', 'ws://');
                            } else if (wsUrl.startsWith('https://')) {
                                wsUrl = wsUrl.replace('https://', 'wss://');
                            }
                            capture.urls.push(wsUrl);
                        }
                        return new capture.originalMethods.EventSource(url, options);
                    };
                }
                
                // 5. 글로벌 객체 모니터링
                const originalDefineProperty = Object.defineProperty;
                Object.defineProperty = function(obj, prop, descriptor) {
                    if (typeof descriptor.value === 'string' && 
                        (descriptor.value.includes('ws://') || descriptor.value.includes('wss://'))) {
                        console.log('🔍 Object.defineProperty에서 WebSocket URL 감지:', descriptor.value);
                        capture.urls.push(descriptor.value);
                    }
                    return originalDefineProperty.apply(this, arguments);
                };
                
                // 6. MutationObserver로 DOM 변화 감지
                const observer = new MutationObserver(function(mutations) {
                    mutations.forEach(function(mutation) {
                        if (mutation.type === 'childList') {
                            mutation.addedNodes.forEach(function(node) {
                                if (node.nodeType === Node.ELEMENT_NODE) {
                                    // script 태그의 내용 확인
                                    if (node.tagName === 'SCRIPT' && node.textContent) {
                                        const wsMatches = node.textContent.match(/wss?:\\/\\/[^\\s"']+/gi);
                                        if (wsMatches) {
                                            console.log('📜 Script 태그에서 WebSocket URL 발견:', wsMatches);
                                            capture.urls.push(...wsMatches);
                                        }
                                    }
                                    
                                    // data 속성 확인
                                    if (node.dataset) {
                                        Object.values(node.dataset).forEach(value => {
                                            if (value && (value.includes('ws://') || value.includes('wss://'))) {
                                                console.log('📊 Data 속성에서 WebSocket URL 발견:', value);
                                                capture.urls.push(value);
                                            }
                                        });
                                    }
                                }
                            });
                        }
                    });
                });
                
                observer.observe(document.body, {
                    childList: true,
                    subtree: true,
                    attributes: true,
                    attributeFilter: ['data-url', 'data-socket', 'data-websocket']
                });
                
                capture.hookSetup = true;
                console.log('🛠️ 포괄적인 WebSocket 후킹 시스템 설정 완료');
            }
            
            return 'WebSocket 후킹 활성화 완료';
            """
            
            result = self.devtools.driver.execute_script(comprehensive_hook_script)
            self.logger.info(f"포괄적인 WebSocket 후킹 설정: {result}")
            
        except Exception as e:
            self.logger.warning(f"WebSocket 후킹 설정 실패: {e}")

    def _trigger_websocket_connections(self, timeout):
        """다양한 방법으로 웹소켓 연결 유도"""
        try:
            start_time = time.time()
            
            # 1단계: 페이지 상호작용으로 웹소켓 연결 유도
            self._trigger_page_interactions()
            
            # 2단계: 주기적으로 URL 수집 및 검증
            while time.time() - start_time < timeout:
                # JavaScript에서 캡처된 URL들 확인
                captured_urls = self._get_captured_websocket_urls()
                
                # 에볼루션 웹소켓 URL 필터링
                for url in captured_urls:
                    if self.validate_websocket_url(url):
                        self.logger.info(f"✅ 유효한 에볼루션 웹소켓 발견: {url}")
                        return url
                
                # 5초마다 추가 상호작용 시도
                if int(time.time() - start_time) % 5 == 0:
                    self._additional_websocket_triggers()
                
                time.sleep(1)
            
            self.logger.warning("웹소켓 연결 유도 타임아웃")
            return None
            
        except Exception as e:
            self.logger.error(f"웹소켓 연결 유도 중 오류: {e}")
            return None

    def _trigger_page_interactions(self):
        """페이지와의 상호작용으로 웹소켓 연결 유도"""
        try:
            # 1. 페이지 새로고침
            current_url = self.devtools.driver.current_url
            if current_url and "data:" not in current_url:
                self.logger.info("페이지 새로고침으로 네트워크 활동 유도")
                self.devtools.driver.refresh()
                time.sleep(3)
            
            # 2. 안전한 요소들과 상호작용
            safe_interactions = [
                "button:not([onclick*='logout']):not([onclick*='exit'])",
                ".lobby-refresh, .refresh-button",
                ".casino-logo, .logo img",
                "[data-testid*='refresh']",
                ".game-lobby .game-item:first-child",
                ".live-casino-button"
            ]
            
            for selector in safe_interactions:
                try:
                    elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        element = elements[0]
                        if element.is_displayed() and element.is_enabled():
                            self.logger.info(f"상호작용 시도: {selector}")
                            element.click()
                            time.sleep(2)
                            break
                except Exception:
                    continue
            
            # 3. 스크롤 이벤트로 지연 로딩 콘텐츠 유도
            try:
                self.devtools.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                self.devtools.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
            except Exception:
                pass
                
        except Exception as e:
            self.logger.warning(f"페이지 상호작용 중 오류: {e}")

    def _additional_websocket_triggers(self):
        """추가 웹소켓 트리거 시도"""
        try:
            # 1. 강제 네트워크 이벤트 생성
            trigger_script = """
            // 강제 네트워크 활동 생성
            try {
                // 1. 이미지 로딩으로 네트워크 활동 유도
                const img = new Image();
                img.src = location.origin + '/favicon.ico?' + Date.now();
                
                // 2. 기존 스크립트들의 재실행 유도
                const scripts = document.querySelectorAll('script[src]');
                if (scripts.length > 0) {
                    const script = scripts[Math.floor(Math.random() * scripts.length)];
                    console.log('스크립트 재로드 시도:', script.src);
                }
                
                // 3. localStorage/sessionStorage 이벤트 유도
                if (window.localStorage) {
                    localStorage.setItem('_trigger', Date.now());
                    localStorage.removeItem('_trigger');
                }
                
                // 4. hashchange 이벤트 유도
                const currentHash = location.hash;
                location.hash = '#trigger_' + Date.now();
                setTimeout(() => {
                    location.hash = currentHash;
                }, 100);
                
                return 'Additional triggers executed';
            } catch(e) {
                return 'Trigger error: ' + e.message;
            }
            """
            
            result = self.devtools.driver.execute_script(trigger_script)
            self.logger.debug(f"추가 트리거 실행: {result}")
            
        except Exception as e:
            self.logger.warning(f"추가 트리거 실행 실패: {e}")

    def _get_captured_websocket_urls(self):
        """JavaScript에서 캡처된 웹소켓 URL들 가져오기"""
        try:
            urls = self.devtools.driver.execute_script("""
                return window.websocketCapture ? 
                    [...new Set(window.websocketCapture.urls)] : 
                    [];
            """)
            
            # 중복 제거 및 정리
            clean_urls = []
            for url in (urls or []):
                if url and isinstance(url, str) and len(url) > 10:
                    clean_urls.append(url.strip())
            
            return list(set(clean_urls))  # 중복 제거
            
        except Exception as e:
            self.logger.warning(f"캡처된 URL 가져오기 실패: {e}")
            return []

    def _extract_websocket_from_page_analysis(self):
        """페이지 분석을 통한 웹소켓 URL 추출 (최후의 수단)"""
        try:
            self.logger.info("🔍 페이지 전체 분석으로 웹소켓 URL 검색")
            
            # 1. 페이지 소스에서 패턴 검색
            page_source = self.devtools.driver.page_source
            
            # 강화된 정규식 패턴들
            websocket_patterns = [
                # 기본 웹소켓 URL 패턴
                r'wss://[^"\'\s\)]+evo-games\.com[^"\'\s\)]*',
                r'wss://[^"\'\s\)]+evolution[^"\'\s\)]*',
                r'wss://[^"\'\s\)]+skylinestart[^"\'\s\)]*',
                r'ws://[^"\'\s\)]+evo[^"\'\s\)]*',
                
                # JavaScript 변수 할당 패턴
                r'(?:websocket|socket|ws)(?:Url|_url|URL)\s*[=:]\s*["\']([wt]ss?://[^"\']+)["\']',
                r'(?:url|URL)\s*[=:]\s*["\']([wt]ss?://[^"\']*(?:evo|socket)[^"\']*)["\']',
                
                # 설정 객체 패턴
                r'["\']url["\']\s*:\s*["\']([wt]ss?://[^"\']*(?:evo|socket)[^"\']*)["\']',
                r'["\']websocket["\']\s*:\s*["\']([wt]ss?://[^"\']+)["\']',
                
                # HTML 속성 패턴
                r'data-(?:socket|ws|websocket)[^=]*=["\']([wt]ss?://[^"\']+)["\']',
                
                # 함수 호출 패턴
                r'(?:new\s+WebSocket|connect|createWebSocket)\s*\(\s*["\']([wt]ss?://[^"\']+)["\']'
            ]
            
            found_urls = []
            for pattern in websocket_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    url = match if isinstance(match, str) else match[0] if match else ''
                    if url:
                        found_urls.append(url)
                        self.logger.info(f"패턴 매칭으로 URL 발견: {url}")
            
            # 2. 스크립트 태그별 개별 분석
            script_analysis_result = self._analyze_script_tags()
            found_urls.extend(script_analysis_result)
            
            # 3. 네트워크 리소스 분석
            network_analysis_result = self._analyze_network_resources()
            found_urls.extend(network_analysis_result)
            
            # 4. 가장 적합한 URL 선택
            unique_urls = list(set(found_urls))
            for url in unique_urls:
                if self.validate_websocket_url(url):
                    self.logger.info(f"✅ 페이지 분석으로 유효한 웹소켓 발견: {url}")
                    return url
            
            # 5. 최후의 수단: 추론 기반 URL 생성
            return self._generate_inferred_websocket_url()
            
        except Exception as e:
            self.logger.error(f"페이지 분석 중 오류: {e}")
            return None

    def _analyze_script_tags(self):
        """스크립트 태그 개별 분석"""
        try:
            script_analysis = """
            const foundUrls = [];
            const scripts = document.querySelectorAll('script');
            
            scripts.forEach((script, index) => {
                try {
                    const content = script.textContent || script.innerHTML || '';
                    
                    // WebSocket URL 패턴 검색
                    const wsMatches = content.match(/wss?:\\/\\/[^\\s"'\\)]+/gi);
                    if (wsMatches) {
                        wsMatches.forEach(url => {
                            if (url.includes('evo') || url.includes('socket')) {
                                foundUrls.push(url);
                                console.log('Script ' + index + '에서 WebSocket URL 발견:', url);
                            }
                        });
                    }
                    
                    // 설정 객체에서 URL 검색
                    const configMatches = content.match(/["']url["']\\s*:\\s*["']([^"']+)["']/gi);
                    if (configMatches) {
                        configMatches.forEach(match => {
                            const urlMatch = match.match(/["']([^"']+)["']$/);
                            if (urlMatch && urlMatch[1] && 
                                (urlMatch[1].startsWith('ws') || urlMatch[1].includes('socket'))) {
                                foundUrls.push(urlMatch[1]);
                                console.log('Config에서 URL 발견:', urlMatch[1]);
                            }
                        });
                    }
                    
                } catch(e) {
                    console.log('Script 분석 오류:', e.message);
                }
            });
            
            return foundUrls;
            """
            
            return self.devtools.driver.execute_script(script_analysis) or []
            
        except Exception as e:
            self.logger.warning(f"스크립트 태그 분석 실패: {e}")
            return []

    def _analyze_network_resources(self):
        """네트워크 리소스 분석"""
        try:
            network_analysis = """
            const foundUrls = [];
            
            try {
                // Performance API를 통한 리소스 분석
                const entries = performance.getEntries();
                entries.forEach(entry => {
                    const name = entry.name || '';
                    if (name.includes('ws://') || name.includes('wss://')) {
                        foundUrls.push(name);
                        console.log('Performance API에서 WebSocket 발견:', name);
                    }
                    
                    // HTTP 리소스에서 WebSocket 단서 찾기
                    if ((name.includes('socket') || name.includes('evo')) && 
                        (name.includes('http://') || name.includes('https://'))) {
                        
                        let wsUrl = name.replace('http://', 'ws://').replace('https://', 'wss://');
                        if (wsUrl.includes('socket') || wsUrl.includes('evo')) {
                            foundUrls.push(wsUrl);
                            console.log('HTTP에서 WebSocket 추론:', wsUrl);
                        }
                    }
                });
                
                // 글로벌 변수들 검사
                for (const key in window) {
                    try {
                        const value = window[key];
                        if (typeof value === 'string' && 
                            (value.startsWith('ws://') || value.startsWith('wss://'))) {
                            foundUrls.push(value);
                            console.log('글로벌 변수에서 WebSocket 발견:', key, value);
                        } else if (typeof value === 'object' && value !== null) {
                            const str = JSON.stringify(value);
                            if (str.includes('ws://') || str.includes('wss://')) {
                                const matches = str.match(/wss?:\\/\\/[^"\\s]+/g);
                                if (matches) {
                                    foundUrls.push(...matches);
                                    console.log('객체에서 WebSocket 발견:', key, matches);
                                }
                            }
                        }
                    } catch(e) {
                        // 접근 불가능한 변수 무시
                    }
                }
                
            } catch(e) {
                console.log('Network 분석 오류:', e.message);
            }
            
            return foundUrls;
            """
            
            return self.devtools.driver.execute_script(network_analysis) or []
            
        except Exception as e:
            self.logger.warning(f"네트워크 리소스 분석 실패: {e}")
            return []

    def _generate_inferred_websocket_url(self):
        """추론 기반 웹소켓 URL 생성 (정말 최후의 수단)"""
        try:
            self.logger.info("🔮 추론 기반 웹소켓 URL 생성 시도")
            
            current_url = self.devtools.driver.current_url
            
            # 현재 URL에서 에볼루션 관련 정보 추출
            if 'evolution' in current_url.lower() or 'evo' in current_url.lower():
                from urllib.parse import urlparse
                parsed = urlparse(current_url)
                
                common_patterns = [
                    f"wss://{parsed.netloc}/public/lobby/socket/v2",
                    f"wss://babylonvg.evo-games.com/public/lobby/socket/v2",
                    f"wss://skylinestart.evo-games.com/public/lobby/socket/v2"
                ]
                
                # 각 패턴에 일반적인 파라미터 추가
                session_params = [
                    "?messageFormat=json&device=Desktop&features=opensAt%2CmultipleHero%2CshortThumbnails%2CskipInfosPublished%2Csmc%2CuniRouletteHistory%2CbacHistoryV2%2Cfilters%2CtableDecorations",
                    "?messageFormat=json&device=Tablet&features=opensAt%2CmultipleHero%2CshortThumbnails",
                    "?messageFormat=json&device=Mobile&features=opensAt%2CmultipleHero"
                ]
                
                inferred_urls = []
                for pattern in common_patterns:
                    inferred_urls.append(pattern)
                    for param in session_params:
                        inferred_urls.append(pattern + param)
                
                # 가장 가능성 높은 URL 반환
                for url in inferred_urls:
                    if self._is_plausible_evolution_websocket(url):
                        self.logger.info(f"🎯 추론된 웹소켓 URL: {url}")
                        return url
            
            return None
            
        except Exception as e:
            self.logger.error(f"추론 기반 URL 생성 실패: {e}")
            return None

    def _is_plausible_evolution_websocket(self, url):
        """추론된 URL이 그럴듯한 에볼루션 웹소켓인지 확인 - 정확한 로비 소켓만"""
        try:
            if not url or not url.startswith('wss://'):
                return False
            
            url_lower = url.lower()
            
            # 필수 조건: .evo-games.com 도메인
            if '.evo-games.com' not in url_lower:
                return False
            
            # 필수 조건: /public/lobby/socket/v2/ 경로
            if '/public/lobby/socket/v2/' not in url_lower:
                return False
            
            # 바람직한 조건들
            desirable_conditions = [
                'messageformat=json' in url_lower,
                'evosessionid=' in url_lower,
                'device=' in url_lower,
                'features=' in url_lower,
                len(url) > 100  # 충분히 긴 URL
            ]
            
            # 최소 2개 이상의 바람직한 조건 만족
            return sum(desirable_conditions) >= 2
            
        except:
            return False

    def validate_websocket_url(self, url):
        """웹소켓 URL 유효성 검증 - 강화된 버전 (정확한 에볼루션 로비 소켓만)"""
        try:
            if not url or not isinstance(url, str):
                return False
            
            url_lower = url.lower()
            
            # 기본 웹소켓 형식 확인
            if not (url_lower.startswith('ws://') or url_lower.startswith('wss://')):
                return False
            
            # 최소 길이 확인 (에볼루션 URL은 보통 100자 이상)
            if len(url) < 100:
                return False
            
            # ✅ 필수 패턴 확인: /public/lobby/socket/v2/
            if '/public/lobby/socket/v2/' not in url_lower:
                self.logger.debug(f"필수 패턴 '/public/lobby/socket/v2/' 없음: {url[:100]}...")
                return False
            
            # ✅ 에볼루션 도메인 확인
            evolution_domains = [
                '.evo-games.com',
                'babylonvg.evo-games.com',
                'skylinestart.evo-games.com'
            ]
            
            has_evo_domain = any(domain in url_lower for domain in evolution_domains)
            if not has_evo_domain:
                self.logger.debug(f"에볼루션 도메인 없음: {url[:100]}...")
                return False
            
            # ✅ 필수 파라미터 확인
            required_params = [
                'evosessionid',
                'messageformat=json',
                'device=',
                'features='
            ]
            
            param_count = sum(1 for param in required_params if param in url_lower)
            if param_count < 3:  # 최소 3개 이상의 필수 파라미터
                self.logger.debug(f"필수 파라미터 부족 ({param_count}/4): {url[:100]}...")
                return False
            
            # ✅ 잘못된 패턴 제외
            invalid_patterns = [
                '/akam/',  # CDN 관련
                '/akamai/',
                '/static/',
                '/assets/',
                '/cdn/',
                '/edge/',
                'test',
                'staging'
            ]
            
            has_invalid = any(pattern in url_lower for pattern in invalid_patterns)
            if has_invalid:
                self.logger.debug(f"잘못된 패턴 포함: {url[:100]}...")
                return False
            
            # ✅ 세션 ID 패턴 확인 (16자 이상의 영숫자)
            import re
            session_match = re.search(r'/socket/v2/([a-z0-9]{16,})', url_lower)
            if not session_match:
                self.logger.debug(f"유효한 세션 ID 패턴 없음: {url[:100]}...")
                return False
            
            # ✅ EVOSESSIONID 길이 확인 (충분히 긴 세션 ID여야 함)
            evosession_match = re.search(r'evosessionid=([a-z0-9]+)', url_lower)
            if evosession_match:
                evosession_id = evosession_match.group(1)
                if len(evosession_id) < 60:  # 에볼루션 세션 ID는 보통 60자 이상
                    self.logger.debug(f"EVOSESSIONID 너무 짧음 ({len(evosession_id)}자): {url[:100]}...")
                    return False
            
            # 모든 검증 통과
            self.logger.info(f"✅ 정확한 에볼루션 로비 웹소켓 URL 검증 통과: {url[:150]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"웹소켓 URL 검증 중 오류: {e}")
            return False