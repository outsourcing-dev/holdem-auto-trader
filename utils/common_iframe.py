"""
공통 iframe 네비게이션 유틸리티
기존 중복된 iframe 로직을 통합하여 성능 최적화
"""
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class IframeNavigator:
    """iframe 네비게이션 및 요소 찾기 통합 클래스"""
    
    def __init__(self, driver, logger=None, default_timeout=10):
        if driver is None:
            raise ValueError("Driver cannot be None")
        
        self.driver = driver
        self.logger = logger or logging.getLogger(__name__)
        self.default_timeout = default_timeout
        self._element_cache = {}
        self._cache_timeout = 5  # 5초 캐시
        self._last_cache_time = {}
        
        # driver 유효성 체크
        self._validate_driver()
    
    def _validate_driver(self):
        """driver 유효성 검사"""
        try:
            if self.driver is None:
                raise ValueError("Driver is None")
            
            # driver가 활성 상태인지 확인
            self.driver.current_url
            return True
            
        except Exception as e:
            self.logger.error(f"Driver 유효성 검사 실패: {e}")
            raise
    
    def _is_driver_active(self):
        """driver가 활성 상태인지 확인"""
        try:
            if self.driver is None:
                return False
            
            self.driver.current_url
            return True
            
        except Exception:
            return False
    
    def wait_for_element(self, by, value, timeout=None):
        """요소 대기 (WebDriverWait 사용)"""
        if not self._is_driver_active():
            self.logger.error("Driver가 비활성 상태입니다")
            return None
            
        timeout = timeout or self.default_timeout
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            self.logger.warning(f"요소를 찾을 수 없음: {by}={value} (timeout: {timeout}s)")
            return None
        except Exception as e:
            self.logger.error(f"요소 대기 중 오류: {e}")
            return None
    
    def wait_for_clickable(self, by, value, timeout=None):
        """클릭 가능한 요소 대기"""
        timeout = timeout or self.default_timeout
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            return element
        except TimeoutException:
            self.logger.warning(f"클릭 가능한 요소를 찾을 수 없음: {by}={value}")
            return None
    
    def switch_to_game_iframe(self, iframe_selector="iframe"):
        """게임 iframe으로 전환 (fallback 로직 포함)"""
        if not self._is_driver_active():
            self.logger.error("iframe 전환 실패: Driver가 비활성 상태")
            return False
            
        # 다양한 iframe selector 패턴 시도
        iframe_patterns = [
            iframe_selector,  # 기본 패턴
            "iframe[src*='game']",
            "iframe[name*='game']",
            "iframe[id*='game']",
            "frame[src*='game']",
            "frame[name*='game']",
            ".game-iframe",
            "#game-frame",
            "iframe",  # 모든 iframe
            "frame"    # 모든 frame
        ]
        
        for pattern in iframe_patterns:
            try:
                # 기본 프레임으로 전환
                self.driver.switch_to.default_content()
                
                # iframe 대기 후 전환
                iframe = self.wait_for_element(By.CSS_SELECTOR, pattern, timeout=3)
                if iframe:
                    self.driver.switch_to.frame(iframe)
                    self.logger.info(f"게임 iframe으로 전환 완료: {pattern}")
                    return True
                    
            except Exception as e:
                self.logger.debug(f"iframe 패턴 '{pattern}' 실패: {e}")
                continue
        
        # 모든 패턴 실패
        self.logger.error("모든 iframe 패턴에서 전환 실패")
        return False
    
    def switch_to_nested_iframe(self, outer_iframe, inner_iframe):
        """중첩 iframe 전환 (fallback 로직 포함)"""
        if not self._is_driver_active():
            self.logger.error("중첩 iframe 전환 실패: Driver가 비활성 상태")
            return False
        
        # 다양한 iframe 조합 패턴 시도
        outer_patterns = [outer_iframe, "iframe", "frame"]
        inner_patterns = [inner_iframe, "iframe", "frame"]
        
        for outer_pattern in outer_patterns:
            for inner_pattern in inner_patterns:
                try:
                    self.driver.switch_to.default_content()
                    
                    # 외부 iframe
                    outer = self.wait_for_element(By.CSS_SELECTOR, outer_pattern, timeout=2)
                    if not outer:
                        continue
                    self.driver.switch_to.frame(outer)
                    
                    # 내부 iframe
                    inner = self.wait_for_element(By.CSS_SELECTOR, inner_pattern, timeout=2)
                    if not inner:
                        continue
                    self.driver.switch_to.frame(inner)
                    
                    self.logger.info(f"중첩 iframe 전환 완료: {outer_pattern} -> {inner_pattern}")
                    return True
                    
                except Exception as e:
                    self.logger.debug(f"중첩 iframe 패턴 실패 ({outer_pattern}->{inner_pattern}): {e}")
                    continue
        
        self.logger.error("모든 중첩 iframe 패턴에서 전환 실패")
        return False
    
    def find_element_with_retry(self, by, value, max_retries=3, retry_delay=1):
        """재시도를 포함한 요소 찾기"""
        for attempt in range(max_retries):
            try:
                element = self.driver.find_element(by, value)
                if element:
                    return element
            except NoSuchElementException:
                if attempt < max_retries - 1:
                    self.logger.debug(f"요소 찾기 재시도 {attempt + 1}/{max_retries}: {by}={value}")
                    time.sleep(retry_delay)
                else:
                    self.logger.warning(f"요소를 찾을 수 없음 (최종): {by}={value}")
        return None
    
    def get_cached_element(self, by, value, cache_key=None):
        """캐시된 요소 반환 (성능 최적화용)"""
        cache_key = cache_key or f"{by}:{value}"
        current_time = time.time()
        
        # 캐시 확인
        if (cache_key in self._element_cache and 
            cache_key in self._last_cache_time and
            current_time - self._last_cache_time[cache_key] < self._cache_timeout):
            
            try:
                # 캐시된 요소가 여전히 유효한지 확인
                element = self._element_cache[cache_key]
                element.is_displayed()  # 유효성 검사
                return element
            except:
                # 캐시된 요소가 더 이상 유효하지 않음
                del self._element_cache[cache_key]
                del self._last_cache_time[cache_key]
        
        # 새로 요소 찾기
        element = self.wait_for_element(by, value)
        if element:
            self._element_cache[cache_key] = element
            self._last_cache_time[cache_key] = current_time
        
        return element
    
    def clear_cache(self):
        """요소 캐시 클리어"""
        self._element_cache.clear()
        self._last_cache_time.clear()
    
    def safe_click(self, by, value, timeout=None):
        """안전한 클릭 (대기 + 클릭)"""
        element = self.wait_for_clickable(by, value, timeout)
        if element:
            try:
                element.click()
                return True
            except Exception as e:
                self.logger.error(f"클릭 실패: {e}")
                return False
        return False
    
    def get_text_with_wait(self, by, value, timeout=None):
        """텍스트 추출 (요소 대기 후)"""
        element = self.wait_for_element(by, value, timeout)
        if element:
            try:
                return element.text.strip()
            except Exception as e:
                self.logger.error(f"텍스트 추출 실패: {e}")
        return ""


class GameIframeManager(IframeNavigator):
    """게임 특화 iframe 관리자"""
    
    def __init__(self, driver, logger=None):
        super().__init__(driver, logger)
        self.game_iframe_selector = "iframe"
        self.game_container_selector = "#game-container"
    
    def ensure_in_game_iframe(self):
        """게임 iframe 내부인지 확인하고 필요시 전환"""
        try:
            # 게임 컨테이너가 있는지 확인
            self.driver.find_element(By.CSS_SELECTOR, self.game_container_selector)
            return True
        except NoSuchElementException:
            # 게임 iframe으로 전환 시도
            return self.switch_to_game_iframe(self.game_iframe_selector)
    
    def get_game_state(self):
        """게임 상태 정보 추출"""
        if not self.ensure_in_game_iframe():
            return None
        
        try:
            # 게임 상태 요소들 찾기 (캐시 사용)
            state_elements = {
                'round': self.get_cached_element(By.CSS_SELECTOR, ".round-info"),
                'balance': self.get_cached_element(By.CSS_SELECTOR, ".balance-info"),
                'cards': self.get_cached_element(By.CSS_SELECTOR, ".card-container")
            }
            
            # 상태 정보 추출
            game_state = {}
            for key, element in state_elements.items():
                if element:
                    game_state[key] = element.text.strip()
            
            return game_state
            
        except Exception as e:
            self.logger.error(f"게임 상태 추출 실패: {e}")
            return None