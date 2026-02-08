import os
import shutil
import threading
import time
import requests

class DiskSpaceMonitor(threading.Thread):

    usage = {1: 0}

    def __init__(self, threshold_gb=1, check_interval=3600, dirs_to_clean=None, files_to_delete=10):
        super().__init__()
        self.threshold_gb = threshold_gb
        self.check_interval = check_interval
        self.dirs_to_clean = dirs_to_clean if dirs_to_clean else []
        self.files_to_delete = files_to_delete

    def run(self):
        while True:
            time.sleep(5)
            self.check_disk_space_and_cleanup()
            time.sleep(self.check_interval)

    def get_disk_space(self):
        total, used, free = shutil.disk_usage("/")
        self.usage = free / total
        return free / (1024 ** 3)

    def delete_oldest_files(self, directory):
        files = sorted(
            (os.path.join(directory, f) for f in os.listdir(directory)),
            key=lambda x: os.path.getmtime(x)
        )
        for file in files[:self.files_to_delete]:
            try:
                os.remove(file)
                print(f"Deleted: {file}")
            except Exception as e:
                print(f"Error deleting {file}: {e}")

    def check_disk_space_and_cleanup(self):
        free_space = self.get_disk_space()

        if free_space < self.threshold_gb:
            print("Disk space below threshold, cleaning up...")
            for directory in self.dirs_to_clean:
                self.delete_oldest_files(directory)
            print("Cleanup complete.")

        if self.usage < 0.25:  # Notez le seuil correct ici
            self.notify_low_disk_space()

    def notify_low_disk_space(self):
        try:
            message = f"Espace disque disponible inférieur à {self.usage * 100:.2f}%"
            requests.post("http://localhost:5002/notify_low_disk_space", json={"message": message})
        except requests.exceptions.RequestException as e:
            print(f"Failed to send notification: {e}")
