import os
from win32com.client import Dispatch

def just_open(file_path):
    # filename = os.path.abspath(filename)
    filename = file_path
    xlApp = Dispatch("Excel.Application")
    xlApp.Visible = False
    xlApp.DisplayAlerts = False
    xlApp.ScreenUpdating = False
    try:
        xlBook = xlApp.Workbooks.Open(Filename=filename, UpdateLinks=False, ReadOnly=False)
        xlBook.Save()
        xlBook.Close(SaveChanges=True)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        xlApp.Quit()

file_path = '/Users/mzy/vscode-projects/SpreadsheetBench/_ExpenseReport.xlsx'
just_open(file_path)
