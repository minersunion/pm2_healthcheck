import time
import json
import tailer
import threading
import subprocess
from pm2_process import PM2Process
from datetime import datetime
import pytz


def get_formatted_date_now() -> str:
    now_utc = datetime.now(pytz.utc)
    now_eastern = now_utc.astimezone(pytz.timezone("US/Eastern"))
    return now_eastern.strftime("%Y-%m-%d %H:%M:%S %Z%z")


def log(something):
    print(f"{get_formatted_date_now()} {something}")


class LogReader(threading.Thread):
    def __init__(self, health_checker, pm2_process: PM2Process):
        super().__init__()
        self.health_checker = health_checker
        self.pm2_process = pm2_process
        log(f"Initiating LogReader with pm2 process name {pm2_process.name}")
        starting_timestamp = time.time()  # in seconds
        self.last_line_timestamp = starting_timestamp
        self.last_delay = 0
        # throw an error if the log file doesn't exist
        self.open_handle = open(self.pm2_process.pm_out_log_path)

    def run(self):
        # Follow the file as it grows
        for line in tailer.follow(self.open_handle):
            self.last_line_timestamp = time.time()

    def restart_pm2_process(self):
        try:
            subprocess.run(["pm2", "restart", self.pm2_process.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except Exception as e:
            log(f"An error occurred: {e}")

    def is_pm2_process_running(self):
        try:
            # Run 'pm2 jlist' to get a JSON-formatted list of all PM2 processes
            result = subprocess.run(["pm2", "jlist"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Check for errors in running the command
            if result.returncode != 0:
                log("Error running pm2 command:", result.stderr)
                return False

            # Parse the JSON output
            processes = json.loads(result.stdout)

            # Search for the process with the specified name
            for process in processes:
                if process["name"] == self.pm2_process_name and process["pm2_env"]["status"] == "online":
                    return True

            # If the process is not found or not online, return False
            return False
        except Exception as e:
            log(f"An error occurred: {e}")
            return False

    def get_stats(self):
        return {
            "pm2_process": self.pm2_process.to_json(),
            "last_delay": self.last_delay,
            "last_line_timestamp": self.last_line_timestamp,
        }
