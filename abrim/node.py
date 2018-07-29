#!/usr/bin/env python

import subprocess
import time
import threading


def output_reader(proc, prefix):
    for line in iter(proc.stdout.readline, b''):
        print('{0}: {1}'.format(prefix, line.decode('utf-8')), end='')


def main():
    proc_queue_in = subprocess.Popen(['py', '-3', '-u', 'queue_in.py', '-i', 'node_1', '-p', '5001'],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
    t = threading.Thread(target=output_reader, args=(proc_queue_in, "queue_in"))
    t.start()

    try:
        time.sleep(0.2)

        for i in range(600):
            #print("test")
            time.sleep(0.1)
    finally:
        # This is in 'finally' so that we can terminate the child if something
        # goes wrong
        proc_queue_in.terminate()
        try:
            proc_queue_in.wait(timeout=0.2)
            print('== subprocess exited with rc =', proc_queue_in.returncode)
        except subprocess.TimeoutExpired:
            print('subprocess did not terminate in time')

    t.join()


if __name__ == '__main__':
    main()
