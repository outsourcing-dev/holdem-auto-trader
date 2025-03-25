# utils/excel_cleanup.py
"""
Excel 프로세스 정리 유틸리티
- 실행 중인 Excel 프로세스를 안전하게 종료
- 프로그램 시작 시 호출하여 Excel 관련 문제 방지
"""
import os
import subprocess
import time
import logging
import psutil
import sys

# COM 지원 확인
try:
    import win32com.client
    import pythoncom
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def find_excel_processes():
    """
    실행 중인 Excel 프로세스를 찾아 반환합니다.
    
    Returns:
        list: 실행 중인 Excel 프로세스 목록 (psutil.Process 객체)
    """
    excel_processes = []
    
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'excel' in proc.info['name'].lower():
                excel_processes.append(proc)
                logger.info(f"실행 중인 Excel 프로세스 발견: PID {proc.info['pid']}, 이름: {proc.info['name']}")
    except Exception as e:
        logger.error(f"Excel 프로세스 검색 중 오류: {e}")
    
    return excel_processes

def safe_close_excel_files(files_to_check=None):
    """
    COM 인터페이스를 사용하여 열려 있는 Excel 파일을 안전하게 닫습니다.
    
    Args:
        files_to_check (list, optional): 확인할 Excel 파일 경로 목록
    
    Returns:
        bool: 성공 여부
    """
    if not HAS_WIN32COM:
        logger.info("COM 인터페이스를 사용할 수 없어 Excel 파일 저장 및 닫기를 건너뜁니다.")
        return False
        
    if files_to_check is None:
        files_to_check = ["AUTO.xlsx"]
    
    abs_paths = [os.path.abspath(file) for file in files_to_check]
    
    try:
        # COM 스레드 초기화 - 이 함수 내에서만 사용
        pythoncom.CoInitialize()
        
        # GetActiveObject 대신 GetObject 사용 (더 안정적)
        try:
            excel = win32com.client.GetObject(Class="Excel.Application")
        except:
            logger.info("활성 Excel 애플리케이션이 없습니다.")
            pythoncom.CoUninitialize()
            return False
        
        # 열린 워크북 확인
        wb_count = 0
        if excel.Workbooks.Count > 0:
            for i in range(excel.Workbooks.Count):
                try:
                    workbook = excel.Workbooks.Item(i+1)  # 1부터 시작
                    wb_path = os.path.abspath(workbook.FullName)
                    logger.info(f"열린 Excel 파일 발견: {wb_path}")
                    
                    # 확인할 파일 목록에 있는지 확인
                    if any(path in wb_path for path in abs_paths):
                        logger.info(f"대상 파일 닫기 시도: {wb_path}")
                        workbook.Save()  # 저장 먼저 시도
                        workbook.Close(True)  # 저장 후 닫기
                        logger.info(f"파일 저장 및 닫기 성공: {wb_path}")
                        wb_count += 1
                except Exception as e:
                    logger.warning(f"워크북 닫기 중 오류: {e}")
        
        # 남은 워크북이 없으면 Excel 종료
        if excel.Workbooks.Count == 0:
            excel.Quit()
            logger.info("Excel 애플리케이션 종료 성공")
        
        pythoncom.CoUninitialize()
        return wb_count > 0
        
    except Exception as e:
        logger.info(f"Excel COM 객체 접근 오류: {e}")
        try:
            pythoncom.CoUninitialize()
        except:
            pass
        return False

def terminate_excel_processes(save_first=True):
    """
    실행 중인 모든 Excel 프로세스를 강제로 종료합니다.
    
    Args:
        save_first (bool): 먼저 파일 저장을 시도할지 여부
    
    Returns:
        int: 종료된 프로세스 수
    """
    # 먼저 COM을 통해 저장 후 종료 시도
    if save_first and HAS_WIN32COM:
        safe_close_excel_files()
    
    # Excel 프로세스 찾기
    excel_processes = find_excel_processes()
    
    if not excel_processes:
        logger.info("종료할 Excel 프로세스가 없습니다.")
        return 0
    
    terminated_count = 0
    
    # 1. 먼저 일반 종료 시도
    for proc in excel_processes:
        try:
            proc_name = proc.name()
            proc_pid = proc.pid
            
            # 일반 종료 시도
            proc.terminate()
            logger.info(f"Excel 프로세스 종료 요청: PID {proc_pid}")
            
            # 2초간 종료 대기
            gone, alive = psutil.wait_procs([proc], timeout=2)
            
            if proc in alive:
                # 강제 종료
                logger.warning(f"Excel 프로세스 (PID: {proc_pid})가 종료되지 않아 강제 종료합니다.")
                proc.kill()
                # 1초 더 대기
                gone, alive = psutil.wait_procs([proc], timeout=1)
                if proc in alive:
                    logger.error(f"Excel 프로세스 강제 종료 실패: PID {proc_pid}")
                else:
                    terminated_count += 1
                    logger.info(f"Excel 프로세스 강제 종료 성공: PID {proc_pid}")
            else:
                terminated_count += 1
                logger.info(f"Excel 프로세스 정상 종료 성공: PID {proc_pid}")
                
        except Exception as e:
            logger.error(f"Excel 프로세스 종료 중 오류: {e}")
    
    # 모든 프로세스 처리 후 가비지 컬렉션 강제 실행
    import gc
    gc.collect()
    
    # 약간의 대기 시간
    time.sleep(0.5)
    
    return terminated_count

def cleanup_excel_on_startup():
    """
    프로그램 시작 시 Excel 인스턴스를 정리합니다.
    """
    logger.info("프로그램 시작 시 Excel 프로세스 정리 중...")
    
    # Windows 환경인지 확인
    is_windows = sys.platform.startswith('win')
    
    if not is_windows:
        logger.info("Windows 환경이 아니므로 Excel 프로세스 정리를 건너뜁니다.")
        return False
    
    # 먼저 COM 인터페이스를 통해 안전하게 닫기 시도
    com_success = safe_close_excel_files()
    
    # 여전히 실행 중인 프로세스 강제 종료
    terminated_count = terminate_excel_processes(save_first=False)
    
    if com_success or terminated_count > 0:
        # 잠시 대기하여 시스템이 처리할 시간 제공
        time.sleep(1)
        logger.info(f"Excel 정리 완료: COM 종료 성공={com_success}, 강제 종료 수={terminated_count}")
        return True
    else:
        logger.info("정리할 Excel 프로세스가 없거나 정리에 실패했습니다.")
        return False

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 직접 실행할 경우 정리 수행
    cleanup_excel_on_startup()