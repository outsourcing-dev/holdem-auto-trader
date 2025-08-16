"""
홀덤 웹 트레이더 런처
백그라운드에서 서버를 실행하고 브라우저를 열어줍니다.
"""
import sys
import os
import time
import threading
import subprocess
import webbrowser
from pathlib import Path

# Tkinter GUI
try:
    import tkinter as tk
    from tkinter import ttk
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

def run_server():
    """백그라운드에서 서버 실행"""
    # main.py 임포트하여 실행
    sys.path.insert(0, str(Path(__file__).parent / "backend"))
    from main import app, open_browser
    import uvicorn
    
    # 서버 실행
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

def open_browser_delayed():
    """잠시 후 브라우저 열기"""
    time.sleep(3)
    webbrowser.open('http://localhost:8000')

def main():
    """메인 실행 함수"""
    if HAS_GUI:
        # GUI 모드
        root = tk.Tk()
        root.title("홀덤 웹 트레이더")
        root.geometry("400x200")
        root.resizable(False, False)
        
        # 중앙 정렬
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'{width}x{height}+{x}+{y}')
        
        # 상태 레이블
        status_label = tk.Label(
            root,
            text="홀덤 웹 트레이더 서버를 시작하는 중...",
            font=("맑은 고딕", 12)
        )
        status_label.pack(pady=30)
        
        # 프로그레스 바
        progress = ttk.Progressbar(
            root,
            mode='indeterminate',
            length=300
        )
        progress.pack(pady=10)
        progress.start(10)
        
        # URL 레이블
        url_label = tk.Label(
            root,
            text="http://localhost:8000",
            font=("맑은 고딕", 10),
            fg="blue",
            cursor="hand2"
        )
        url_label.pack(pady=10)
        
        def on_url_click(event):
            webbrowser.open('http://localhost:8000')
        
        url_label.bind("<Button-1>", on_url_click)
        
        # 서버 스레드 시작
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # 브라우저 열기
        browser_thread = threading.Thread(target=open_browser_delayed, daemon=True)
        browser_thread.start()
        
        # 3초 후 상태 업데이트
        def update_status():
            status_label.config(text="서버가 실행 중입니다. 브라우저에서 확인하세요.")
            progress.stop()
            progress.pack_forget()
            
            # 종료 버튼 추가
            close_btn = tk.Button(
                root,
                text="프로그램 종료",
                command=root.quit,
                font=("맑은 고딕", 10),
                bg="#ff4444",
                fg="white",
                padx=20,
                pady=5
            )
            close_btn.pack(pady=20)
        
        root.after(3000, update_status)
        
        # GUI 실행
        root.mainloop()
    else:
        # 콘솔 모드
        print("=" * 60)
        print("홀덤 자동 트레이더 웹 서버가 시작되었습니다!")
        print("브라우저가 자동으로 열립니다...")
        print("주소: http://localhost:8000")
        print("종료하려면 Ctrl+C를 누르세요.")
        print("=" * 60)
        
        # 브라우저 열기
        browser_thread = threading.Thread(target=open_browser_delayed, daemon=True)
        browser_thread.start()
        
        # 서버 실행
        run_server()

if __name__ == "__main__":
    main()