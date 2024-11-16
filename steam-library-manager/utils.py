import os
import shutil
import psutil
from pathlib import Path

from tqdm import tqdm


def check_proc(proc_name):
    proc_pids = []
    for proc in psutil.process_iter(attrs=['name', 'pid']):
        if proc_name.lower() in proc.name().lower():
            proc_pids.append(proc.pid)
    if proc_pids:
        return proc_pids


def term_proc(proc_pids):
    for pid in proc_pids:
        proc = psutil.Process(pid)
        proc.terminate()


def copytree_with_progress(source, destination):
    total_size = sum(os.path.getsize(f) for f in Path(source).rglob('*'))

    def copy_with_progress(src, dst):
        shutil.copy2(src, dst)
        progress_bar.update(os.path.getsize(src))

    try:
        with tqdm(total=total_size, unit='B', unit_scale=True) as progress_bar:
            shutil.copytree(source, destination, copy_function=copy_with_progress, ignore=shutil.ignore_patterns(''))
            return True

    except Exception as e:
        print(f"ERROR: Copy function failed. Exception: {e}")
        return False
