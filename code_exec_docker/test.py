from jupyter_kernel_cli import ClientJupyterKernel


def get_exec_client():
    URL = 'http://localhost:8081/execute'
    CONV_ID = 'TEST'
    client = ClientJupyterKernel(URL, CONV_ID)

    return client


def test_exec():
    code = """
import pandas as pd

df = pd.read_csv('/mnt/data/data.csv')

print(df)
"""

    code = """
import os
os.system('ls /mnt/data')
"""

    client = get_exec_client()
    res = client.execute(code)
    print(res)

    return res


def test_error_feedback():
    code = """
import pandas as pd

df = pd.read_csv('/mnt/data.csv')

print(df)
"""

    client = get_exec_client()
    res = client.execute(code)
    if res.find('-----') != -1:
        tracebacks = res.split('\n\n\n\n')
        error_feedback = ''
        for t in tracebacks:
            if t.find('Error') != -1:
                error_feedback += t + '\n'
                break
        for t in tracebacks:
            if len(t) >= len('Cell') and t[:len('Cell')] == 'Cell':
                error_feedback += t
                break
        error_feedback += tracebacks[-1]
        print(error_feedback)


if __name__ == '__main__':
    test_exec()
