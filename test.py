#!/usr/bin/python3

import signal, time, sys

def main():
    shutting_down = False
    def handler(*args):
        nonlocal shutting_down
        shutting_down = True
    signal.signal(signal.SIGTERM, handler)

    # Main logic goes here, taking shutting_down into consideration
    while True:
        print("are we shutting down: " + str(shutting_down), file = sys.stderr)
        time.sleep(1)

if __name__ == '__main__':
    main()
