# utils 폴더 내부에서 encrypt_excel을 임포트하는 경우, 상대 경로 임포트 사용
from .encrypt_excel import EncryptExcel  # 상대 경로 사용

def encrypt_excel_for_distribution(input_path, output_path=None):
    """
    Excel 파일을 암호화하여 배포용 파일로 변환
    
    Args:
        input_path (str): 원본 Excel 파일 경로
        output_path (str, optional): 출력 파일 경로 (None이면 AUTO.encrypted로 저장)
    
    Returns:
        bool: 성공 여부
    """
    if output_path is None:
        output_path = "AUTO.encrypted"
    
    SECRET_KEY = "holdem2025_secret_key"
    
    # EncryptExcel 클래스의 인스턴스 생성
    encryptor = EncryptExcel()
    
    # 인스턴스의 encrypt_file 메소드 호출
    return encryptor.encrypt_file(input_path, output_path, SECRET_KEY)

if __name__ == "__main__":
    import os
    import sys
    
    # 현재 스크립트의 상위 디렉토리(프로젝트 루트)를 Python 경로에 추가
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 함수 실행
    result = encrypt_excel_for_distribution("AUTO.xlsx")
    print(f"암호화 결과: {'성공' if result else '실패'}")