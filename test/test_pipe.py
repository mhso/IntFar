from time import time, sleep
from multiprocessing import Pipe, Process, Lock, Event
from multiprocessing.connection import wait
from threading import Thread

def register_connection(main_pipe, lock, conn_id):
    lock.acquire()
    print("Registering connection", flush=True)
    main_pipe.send(("register", conn_id, None))
    our_pipe = main_pipe.recv()
    print("Connection registered local", flush=True)
    lock.release()
    return our_pipe

def send_request(pipe, conn_id, data):
    try:
        pipe.send(("op", conn_id, data))
        return True
    except (EOFError, BrokenPipeError) as e:
        return False

def do_20_requests(other_pipe, num, lock, event):
    numbers = []
    our_pipe = register_connection(other_pipe, lock, num)
    for task_count in range(20):
        success = send_request(our_pipe, num, num)
        if not success:
            our_pipe = register_connection(other_pipe, lock, num)
            success = send_request(our_pipe, num, num)

        pow_num = our_pipe.recv()
        numbers.append(pow_num)
        if event.is_set():
            exit(0)
    valid = all(n == num ** 2 for n in numbers)
    print(f"Thread {num}: {numbers}", flush=True)
    if not valid:
        print(f"THREAD {num} INVALID!")

def spawn_consumer_process(other_pipe, lock, event):
    num_threads = 10
    time_start = time()

    threads = [Thread(target=do_20_requests, args=(other_pipe, i, lock, event)) for i in range(1, num_threads+1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    time_after = time()

    print(f"All done. That took {time_after - time_start} seconds.")

def spawn_producer_process(other_pipe, event):
    pipes = {0: other_pipe}
    max_timeout = 5
    timeouts = {}
    while True:
        for pipe in wait(pipes.values(), 0.01):
            try:
                status, conn_id, data = pipe.recv()
                if status == "register": # Register new connection.
                    our_pipe, new_pipe = Pipe()
                    pipes[conn_id] = our_pipe
                    timeouts[conn_id] = time()
                    print("Connection registered external", flush=True)
                    pipe.send(new_pipe) # Indicate we have registered the connection.
                else:
                    number = data
                    pow_num = number ** 2
                    timeouts[conn_id] = time()
                    pipe.send(pow_num)
            except EOFError:
                continue

        conns_to_remove = []
        now = time()
        for conn_id in timeouts:
            if now - timeouts[conn_id] > max_timeout:
                conns_to_remove.append(conn_id)

        for conn_id in conns_to_remove:
            print(f"Connection {conn_id} timed out!", flush=True)
            del timeouts[conn_id]
            pipes[conn_id].close()
            del pipes[conn_id]

        if event.is_set():
            exit(0)

if __name__ == "__main__":
    conn_1, conn_2 = Pipe()
    conn_lock = Lock()
    stop_event = Event()
    producer = Process(target=spawn_producer_process, args=(conn_1, stop_event))
    consumer = Process(target=spawn_consumer_process, args=(conn_2, conn_lock, stop_event))

    producer.start()
    consumer.start()

    try:
        while consumer.is_alive():
            sleep(0.1)
    except KeyboardInterrupt:
        stop_event.set()
