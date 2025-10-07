import os
import argparse
from win32com.client import Dispatch


def just_open(filename):
    filename = os.path.abspath(filename)
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


def open_all_spreadsheet_in_dir(dir_path):
    if not os.path.isdir(dir_path):
        print(f"Not a valid dir path: {dir_path}")
        return

    # 支持的扩展名
    supported_extensions = {'.xlsx', '.xls'}
    
    # 遍历目录中的所有文件
    for filename in os.listdir(dir_path):
        _, ext = os.path.splitext(filename)
        if ext.lower() in supported_extensions:
            full_path = os.path.join(dir_path, filename)
            print(f"Processing: {full_path}")
            just_open(full_path)

    print("Finish processing all files")


if __name__ == '__main__':
    parser = argparse.ArgumentParser("command line arguments for open spreadsheets.")
    
    parser.add_argument('--dir_path', type=str, help='the dir path of spreadsheets')

    opt = parser.parse_args()

    open_all_spreadsheet_in_dir(opt.dir_path)

