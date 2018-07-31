#!/usr/bin/env python

import subprocess
import threading
import time
import webbrowser
from abrim.util import args_init

def output_reader(proc, prefix):
    for line in iter(proc.stdout.readline, b''):
        print('{0}: {1}'.format(prefix, line.decode('utf-8')), end='')


def main():
    node_id, client_port = args_init()

    proc_ui, thread_ui = launch_subprocess('ui.py', "UI___", node_id, client_port)
    proc_queue_in, thread_queue_in = launch_subprocess('input.py', "INPUT", node_id, client_port + 1)
    proc_queue_out, thread_queue_out = launch_subprocess('out.py', "OUT__", node_id, client_port + 1)
    proc_queue_patch, thread_queue_patch = launch_subprocess('patch.py', "PATCH", node_id, client_port + 1)

    webbrowser.open_new_tab("http://localhost:" + str(client_port) + "/")

    try:
        while True:
            time.sleep(0.1)
        #
        # for i in range(600):
        #     #print("test")
        #     time.sleep(0.1)
    finally:
        # This is in 'finally' so that we can terminate the child if something
        # goes wrong
        proc_terminate(proc_ui)
        proc_terminate(proc_queue_in)
        proc_terminate(proc_queue_out)
        proc_terminate(proc_queue_patch)

    thread_ui.join()
    thread_queue_in.join()
    thread_queue_out.join()
    thread_queue_patch.join()


def proc_terminate(my_proc):
    my_proc.terminate()
    try:
        my_proc.wait(timeout=0.2)
        print('== subprocess exited with rc =', my_proc.returncode)
    except subprocess.TimeoutExpired:
        print('subprocess did not terminate in time')


def launch_subprocess(script, prefix, node_id, port=None):
    popen = ['py', '-3', '-u', str(script), '-i', str(node_id)]
    if port:
        popen.extend(['-p', str(port)])

    my_proc = subprocess.Popen(popen,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
    my_thread = threading.Thread(target=output_reader, args=(my_proc, prefix))
    my_thread.start()
    return my_proc, my_thread

if __name__ == '__main__':
    main()
