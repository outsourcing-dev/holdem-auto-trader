# utils/__init__.py
import sys
from .excel_manager_compatibility import ExcelManager
sys.modules['utils.excel_manager'] = sys.modules['utils.excel_manager_compatibility']