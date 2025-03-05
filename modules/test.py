# simple_excel_reader.py
"""
간단하게 엑셀 파일의 13행 B열부터 R열까지 읽는 스크립트
"""
import openpyxl
import sys

def read_excel_row13(file_path):
    """B13부터 R13까지의 값을 읽어 출력합니다."""
    try:
        # data_only=True 옵션으로 수식이 아닌 결과값을 읽어옵니다
        workbook = openpyxl.load_workbook(file_path, data_only=True)
        sheet = workbook.active
        
        # B13부터 R13까지 읽기
        result = {}
        for col_letter in [chr(i) for i in range(ord('B'), ord('R')+1)]:
            cell = sheet[f"{col_letter}12"]
            result[f"{col_letter}1"] = cell.value
        
        workbook.close()
        return result
    
    except Exception as e:
        print(f"오류 발생: {e}")
        return None

if __name__ == "__main__":
    # 기본 파일 경로를 AUTO.xlsx로 설정
    file_path = "AUTO.xlsx"
    
    # 명령줄 인수로 다른 파일 경로가 제공되었는지 확인
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    print(f"파일 '{file_path}'에서 13행 B열 ~ R열 값을 읽는 중...")
    values = read_excel_row13(file_path)
    
    if values:
        print("===== 13행 B열 ~ R열 값 =====")
        for cell, value in values.items():
            print(f"{cell}: {value}")