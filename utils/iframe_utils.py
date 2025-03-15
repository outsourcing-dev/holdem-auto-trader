# utils/iframe_utils.py
import logging
import time
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class IframeManager:
    """
    iframe을 관리하기 위한 유틸리티 클래스
    - 중첩된 iframe 처리
    - iframe 전환 및 복귀
    - iframe 내부 요소 검색
    """
    def __init__(self, driver):
        """
        IframeManager 초기화
        
        Args:
            driver: Selenium WebDriver 객체
        """
        self.driver = driver
        # iframe 스택 (중첩된 iframe 처리를 위한 스택)
        self.iframe_stack = []
        
    def switch_to_iframe(self, iframe_selector, timeout=10, reset_first=True):
        """
        지정된 iframe으로 전환
        
        Args:
            iframe_selector (str): iframe CSS 선택자
            timeout (int): 대기 시간(초)
            reset_first (bool): True이면 먼저 기본 컨텐츠로 복귀
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 기본 컨텐츠로 먼저 복귀 (선택적)
            if reset_first:
                self.driver.switch_to.default_content()
                self.iframe_stack = []  # 스택 초기화
            
            # iframe 요소 찾기
            iframe = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, iframe_selector))
            )
            
            # iframe으로 전환
            self.driver.switch_to.frame(iframe)
            
            # 스택에 추가
            self.iframe_stack.append(iframe_selector)
            logger.info(f"iframe으로 전환 성공: {iframe_selector}")
            return True
            
        except (NoSuchElementException, TimeoutException, StaleElementReferenceException) as e:
            logger.warning(f"iframe 전환 실패 ({iframe_selector}): {e}")
            return False
    
    def switch_to_nested_iframe(self, selectors, timeout=10):
        """
        중첩된 iframe을 순차적으로 전환
        
        Args:
            selectors (list): iframe CSS 선택자 목록 (순서대로)
            timeout (int): 대기 시간(초)
            
        Returns:
            bool: 성공 여부
        """
        # 기본 컨텐츠로 먼저 복귀
        self.driver.switch_to.default_content()
        self.iframe_stack = []  # 스택 초기화
        
        # 각 iframe으로 순차적으로 전환
        for selector in selectors:
            try:
                # iframe 요소 찾기
                iframe = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                
                # iframe으로 전환
                self.driver.switch_to.frame(iframe)
                
                # 스택에 추가
                self.iframe_stack.append(selector)
                logger.info(f"중첩 iframe으로 전환 성공: {selector}")
                
            except (NoSuchElementException, TimeoutException, StaleElementReferenceException) as e:
                logger.warning(f"중첩 iframe 전환 실패 ({selector}): {e}")
                # 실패 시 기본 컨텐츠로 복귀
                self.driver.switch_to.default_content()
                self.iframe_stack = []
                return False
        
        return True
    
    def find_and_switch_to_any_iframe(self, max_depth=2, timeout=3):
        """
        페이지 내 모든 iframe을 찾아 전환 시도 (중첩된 iframe 최대 max_depth까지)
        
        Args:
            max_depth (int): 최대 중첩 깊이
            timeout (int): 대기 시간(초)
            
        Returns:
            bool: 성공 여부
        """
        # 기본 컨텐츠로 먼저 복귀
        self.driver.switch_to.default_content()
        self.iframe_stack = []  # 스택 초기화
        
        return self._find_and_switch_recursive(depth=0, max_depth=max_depth, timeout=timeout)
    
    def _find_and_switch_recursive(self, depth=0, max_depth=2, timeout=3):
        """
        iframe을 재귀적으로 찾아 전환 (내부 메서드)
        
        Args:
            depth (int): 현재 깊이
            max_depth (int): 최대 중첩 깊이
            timeout (int): 대기 시간(초)
            
        Returns:
            bool: 성공 여부
        """
        # 최대 깊이 초과 시 종료
        if depth >= max_depth:
            return False
        
        try:
            # 현재 문서에서 모든 iframe 찾기
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            
            if not iframes:
                logger.info(f"깊이 {depth}에서 iframe을 찾을 수 없음")
                return False
            
            logger.info(f"깊이 {depth}에서 {len(iframes)}개의 iframe 발견")
            
            # 각 iframe에 대해 시도
            for i, iframe in enumerate(iframes):
                try:
                    # iframe으로 전환
                    self.driver.switch_to.frame(iframe)
                    
                    # 스택에 추가 (임시 식별자 사용)
                    iframe_id = iframe.get_attribute("id") or iframe.get_attribute("name") or f"iframe_{depth}_{i}"
                    self.iframe_stack.append(iframe_id)
                    
                    logger.info(f"깊이 {depth}의 iframe {iframe_id}로 전환 성공")
                    
                    # 중첩된 iframe이 있는지 재귀적으로 확인
                    nested_result = self._find_and_switch_recursive(depth + 1, max_depth, timeout)
                    
                    # 중첩된 iframe으로 전환 성공 시 현재 상태 유지
                    if nested_result:
                        return True
                    
                    # 실패 시 현재 iframe으로 다시 전환
                    self.driver.switch_to.default_content()
                    for j in range(len(self.iframe_stack) - 1):  # 마지막 항목 제외
                        selector = self.iframe_stack[j]
                        if selector.startswith("iframe_"):
                            # 임시 식별자인 경우 인덱스로 접근
                            parts = selector.split("_")
                            d, idx = int(parts[1]), int(parts[2])
                            frame = self.driver.find_elements(By.TAG_NAME, "iframe")[idx]
                            self.driver.switch_to.frame(frame)
                        else:
                            iframe = self.driver.find_element(By.CSS_SELECTOR, selector)
                            self.driver.switch_to.frame(iframe)
                    
                    # 스택에서 제거
                    self.iframe_stack.pop()
                    
                except (NoSuchElementException, TimeoutException, StaleElementReferenceException) as e:
                    logger.warning(f"iframe 전환 중 오류: {e}")
                    # 기본 컨텐츠로 복귀하고 다시 현재 깊이까지 전환
                    self.driver.switch_to.default_content()
                    self.iframe_stack = []
                    continue
            
            # 모든 iframe 시도 후 실패 시 부모로 복귀
            if len(self.iframe_stack) > 0:
                self.driver.switch_to.default_content()
                for i in range(len(self.iframe_stack) - 1):
                    selector = self.iframe_stack[i]
                    if selector.startswith("iframe_"):
                        # 임시 식별자인 경우 인덱스로 접근
                        parts = selector.split("_")
                        d, idx = int(parts[1]), int(parts[2])
                        frame = self.driver.find_elements(By.TAG_NAME, "iframe")[idx]
                        self.driver.switch_to.frame(frame)
                    else:
                        iframe = self.driver.find_element(By.CSS_SELECTOR, selector)
                        self.driver.switch_to.frame(iframe)
            
            return False
            
        except Exception as e:
            logger.error(f"iframe 재귀 검색 중 오류: {e}")
            # 기본 컨텐츠로 복귀
            self.driver.switch_to.default_content()
            self.iframe_stack = []
            return False
    
    def return_to_default_content(self):
        """
        기본 컨텐츠로 복귀
        """
        try:
            self.driver.switch_to.default_content()
            self.iframe_stack = []
            logger.info("기본 컨텐츠로 복귀 완료")
            return True
        except Exception as e:
            logger.error(f"기본 컨텐츠 복귀 중 오류: {e}")
            return False
    
    def return_to_parent_iframe(self):
        """
        부모 iframe으로 복귀
        
        Returns:
            bool: 성공 여부
        """
        try:
            # iframe 스택이 비어있으면 할 일 없음
            if not self.iframe_stack:
                logger.info("현재 iframe 스택이 비어있어 복귀할 필요 없음")
                return True
            
            # 마지막 iframe 제거
            self.iframe_stack.pop()
            
            # 기본 컨텐츠로 먼저 복귀
            self.driver.switch_to.default_content()
            
            # 스택에 남아있는 iframe이 있으면 순차적으로 전환
            for selector in self.iframe_stack:
                if selector.startswith("iframe_"):
                    # 임시 식별자인 경우 처리 불가능
                    logger.warning(f"임시 식별자({selector})로는 복귀할 수 없음. 기본 컨텐츠로 복귀합니다.")
                    self.iframe_stack = []
                    return False
                
                iframe = self.driver.find_element(By.CSS_SELECTOR, selector)
                self.driver.switch_to.frame(iframe)
            
            logger.info("부모 iframe으로 복귀 완료")
            return True
            
        except Exception as e:
            logger.error(f"부모 iframe 복귀 중 오류: {e}")
            # 오류 시 기본 컨텐츠로 복귀
            self.driver.switch_to.default_content()
            self.iframe_stack = []
            return False
    
    def find_element_in_iframes(self, by, value, max_depth=2, timeout=3):
        """
        모든 iframe을 순회하며 요소 찾기
        
        Args:
            by: 찾을 방식 (By.ID, By.CSS_SELECTOR 등)
            value: 찾을 값
            max_depth (int): 최대 중첩 깊이
            timeout (int): 대기 시간(초)
            
        Returns:
            tuple: (성공 여부, 요소 객체 또는 None)
        """
        # 기존 iframe 스택 백업
        original_stack = self.iframe_stack.copy()
        
        # 기본 컨텐츠로 복귀
        self.driver.switch_to.default_content()
        self.iframe_stack = []
        
        try:
            # 먼저 기본 컨텐츠에서 요소 찾기 시도
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
                logger.info(f"기본 컨텐츠에서 요소 발견: {value}")
                return True, element
            except (NoSuchElementException, TimeoutException):
                pass
            
            # 모든 iframe 찾기
            result = self._find_element_recursive(by, value, depth=0, max_depth=max_depth, timeout=timeout)
            
            # 요소를 찾았으면 현재 iframe 상태 유지
            if result[0]:
                logger.info(f"iframe 내에서 요소 발견: {value}")
                return result
            
            # 요소를 찾지 못했으면 원래 iframe 상태로 복원
            self.driver.switch_to.default_content()
            self.iframe_stack = []
            
            for selector in original_stack:
                if selector.startswith("iframe_"):
                    # 임시 식별자인 경우 복원 불가능
                    logger.warning(f"임시 식별자({selector})로는 복원할 수 없음")
                    break
                
                iframe = self.driver.find_element(By.CSS_SELECTOR, selector)
                self.driver.switch_to.frame(iframe)
            
            logger.warning(f"어떤 iframe에서도 요소를 찾을 수 없음: {value}")
            return False, None
            
        except Exception as e:
            logger.error(f"iframe 내 요소 검색 중 오류: {e}")
            
            # 오류 시 원래 iframe 상태로 복원 시도
            try:
                self.driver.switch_to.default_content()
                self.iframe_stack = []
                
                for selector in original_stack:
                    if selector.startswith("iframe_"):
                        # 임시 식별자인 경우 복원 불가능
                        break
                    
                    iframe = self.driver.find_element(By.CSS_SELECTOR, selector)
                    self.driver.switch_to.frame(iframe)
            except:
                # 복원 실패 시 기본 컨텐츠로 복귀
                self.driver.switch_to.default_content()
                self.iframe_stack = []
            
            return False, None
    
    def _find_element_recursive(self, by, value, depth=0, max_depth=2, timeout=1):
        """
        iframe을 재귀적으로 순회하며 요소 찾기 (내부 메서드)
        
        Args:
            by: 찾을 방식 (By.ID, By.CSS_SELECTOR 등)
            value: 찾을 값
            depth (int): 현재 깊이
            max_depth (int): 최대 중첩 깊이
            timeout (int): 대기 시간(초)
            
        Returns:
            tuple: (성공 여부, 요소 객체 또는 None)
        """
        # 최대 깊이 초과 시 종료
        if depth >= max_depth:
            return False, None
        
        try:
            # 현재 문서에서 요소 찾기 시도
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
                return True, element
            except (NoSuchElementException, TimeoutException):
                pass
            
            # 현재 문서에서 모든 iframe 찾기
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            
            # 각 iframe에 대해 시도
            for i, iframe in enumerate(iframes):
                try:
                    # iframe으로 전환
                    self.driver.switch_to.frame(iframe)
                    
                    # 스택에 추가 (임시 식별자 사용)
                    iframe_id = iframe.get_attribute("id") or iframe.get_attribute("name") or f"iframe_{depth}_{i}"
                    self.iframe_stack.append(iframe_id)
                    
                    # 현재 iframe에서 요소 찾기 시도
                    try:
                        element = WebDriverWait(self.driver, timeout).until(
                            EC.presence_of_element_located((by, value))
                        )
                        return True, element
                    except (NoSuchElementException, TimeoutException):
                        pass
                    
                    # 중첩된 iframe 내부에서 재귀적으로 요소 찾기
                    result = self._find_element_recursive(by, value, depth + 1, max_depth, timeout)
                    
                    # 요소를 찾았으면 현재 상태 유지하고 반환
                    if result[0]:
                        return result
                    
                    # 요소를 찾지 못했으면 부모 iframe으로 복귀
                    self.driver.switch_to.default_content()
                    for j in range(len(self.iframe_stack) - 1):  # 마지막 항목 제외
                        selector = self.iframe_stack[j]
                        if selector.startswith("iframe_"):
                            # 임시 식별자인 경우 인덱스로 접근
                            parts = selector.split("_")
                            d, idx = int(parts[1]), int(parts[2])
                            frame = self.driver.find_elements(By.TAG_NAME, "iframe")[idx]
                            self.driver.switch_to.frame(frame)
                        else:
                            iframe = self.driver.find_element(By.CSS_SELECTOR, selector)
                            self.driver.switch_to.frame(iframe)
                    
                    # 스택에서 제거
                    self.iframe_stack.pop()
                    
                except Exception as e:
                    logger.warning(f"iframe 처리 중 오류: {e}")
                    # 부모 iframe으로 복귀
                    self.driver.switch_to.default_content()
                    for j in range(len(self.iframe_stack) - 1):  # 마지막 항목 제외
                        selector = self.iframe_stack[j]
                        if selector.startswith("iframe_"):
                            # 임시 식별자인 경우 인덱스로 접근
                            parts = selector.split("_")
                            d, idx = int(parts[1]), int(parts[2])
                            frame = self.driver.find_elements(By.TAG_NAME, "iframe")[idx]
                            self.driver.switch_to.frame(frame)
                        else:
                            iframe = self.driver.find_element(By.CSS_SELECTOR, selector)
                            self.driver.switch_to.frame(iframe)
                    
                    # 스택에서 제거
                    if self.iframe_stack:
                        self.iframe_stack.pop()
            
            # 모든 iframe을 확인했지만 요소를 찾지 못함
            return False, None
            
        except Exception as e:
            logger.error(f"재귀적 요소 검색 중 오류: {e}")
            return False, None

# 유틸리티 함수: 기존 코드에 쉽게 통합하기 위한 함수들

def switch_to_iframe_with_retry(driver, max_retries=3, max_depth=2):
    """
    iframe 전환 시도 (중첩된 iframe 처리)
    
    Args:
        driver: Selenium WebDriver 객체
        max_retries (int): 최대 재시도 횟수
        max_depth (int): 최대 중첩 깊이
        
    Returns:
        bool: 성공 여부
    """
    iframe_manager = IframeManager(driver)
    
    # 기본 컨텐츠로 복귀
    driver.switch_to.default_content()
    
    for retry in range(max_retries):
        try:
            # 1. 단일 iframe 시도
            iframe = driver.find_elements(By.CSS_SELECTOR, "iframe")
            if iframe:
                driver.switch_to.frame(iframe[0])
                logger.info(f"단일 iframe 전환 성공 (시도 {retry+1}/{max_retries})")
                
                # 1.1 중첩된 iframe 확인
                nested_iframe = driver.find_elements(By.TAG_NAME, "iframe")
                if nested_iframe:
                    try:
                        driver.switch_to.frame(nested_iframe[0])
                        logger.info("중첩된 iframe 발견 및 전환 성공")
                        return True
                    except:
                        logger.info("중첩된 iframe 전환 실패, 단일 iframe 상태 유지")
                
                return True
            
            # 2. IframeManager로 자동 검색 시도
            if iframe_manager.find_and_switch_to_any_iframe(max_depth=max_depth):
                logger.info(f"IframeManager로 iframe 전환 성공 (시도 {retry+1}/{max_retries})")
                return True
            
            # 재시도 전 대기
            time.sleep(1)
            
        except Exception as e:
            logger.warning(f"iframe 전환 실패 (시도 {retry+1}/{max_retries}): {e}")
            driver.switch_to.default_content()
            time.sleep(1)
    
    logger.error(f"최대 재시도 횟수({max_retries}) 초과로 iframe 전환 실패")
    return False

def find_element_in_iframes(driver, by, value, max_depth=2):
    """
    모든 iframe을 확인하며 요소 찾기
    
    Args:
        driver: Selenium WebDriver 객체
        by: 찾을 방식 (By.ID, By.CSS_SELECTOR 등)
        value: 찾을 값
        max_depth (int): 최대 중첩 깊이
        
    Returns:
        tuple: (성공 여부, 요소 객체 또는 None)
    """
    iframe_manager = IframeManager(driver)
    return iframe_manager.find_element_in_iframes(by, value, max_depth=max_depth)

def get_safe_iframe_content(driver, max_depth=2):
    """
    모든 iframe을 순회하며 내용 가져오기
    
    Args:
        driver: Selenium WebDriver 객체
        max_depth (int): 최대 중첩 깊이
        
    Returns:
        dict: 각 iframe의 내용
    """
    iframe_manager = IframeManager(driver)
    results = {}
    
    # 기본 컨텐츠 저장
    default_content = driver.page_source
    results["default"] = default_content
    
    # 모든 iframe 찾기
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    
    for i, iframe in enumerate(iframes):
        try:
            # iframe으로 전환
            driver.switch_to.frame(iframe)
            
            # iframe 내용 저장
            iframe_content = driver.page_source
            results[f"iframe_{i}"] = iframe_content
            
            # 중첩된 iframe 찾기
            nested_iframes = driver.find_elements(By.TAG_NAME, "iframe")
            
            for j, nested_iframe in enumerate(nested_iframes):
                try:
                    # 중첩된 iframe으로 전환
                    driver.switch_to.frame(nested_iframe)
                    
                    # 중첩된 iframe 내용 저장
                    nested_content = driver.page_source
                    results[f"iframe_{i}_nested_{j}"] = nested_content
                    
                    # 기본 iframe으로 복귀
                    driver.switch_to.parent_frame()
                    
                except Exception as e:
                    logger.warning(f"중첩된 iframe_{i}_nested_{j} 접근 실패: {e}")
            
            # 기본 컨텐츠로 복귀
            driver.switch_to.default_content()
            
        except Exception as e:
            logger.warning(f"iframe_{i} 접근 실패: {e}")
            driver.switch_to.default_content()
    
    return results