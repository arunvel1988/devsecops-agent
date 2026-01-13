# cpu_load.py
import multiprocessing
import time

def burn_cpu():
    while True:
        pass  # infinite loop

if __name__ == "__main__":
    cores = multiprocessing.cpu_count()
    print(f"Spawning {cores} processes to use CPU")
    for _ in range(cores):
        multiprocessing.Process(target=burn_cpu).start()
