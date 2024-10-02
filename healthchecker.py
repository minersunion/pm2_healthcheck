import json
import time
import argparse
import threading
import subprocess
from typing import Optional

import psutil
from log_reader import LogReader
from pm2_process import PM2Process
from datetime import datetime
import pytz
import socket
import traceback
import bittensor
from retry import retry


def get_formatted_date_now() -> str:
    now_utc = datetime.now(pytz.utc)
    now_eastern = now_utc.astimezone(pytz.timezone("US/Eastern"))
    return now_eastern.strftime("%Y-%m-%d %H:%M:%S %Z%z")

def log(something):
    print(f"{get_formatted_date_now()} {something}")


def get_subtensor(network: Optional[str] = "wss://entrypoint-finney.opentensor.ai:443", config: Optional[bittensor.config] = None, log_verbose=False):
    """create a subtensor and retry 3 times by increasing the sleep by 2 between each retries"""

    @retry(tries=3, delay=1, backoff=2)
    def _create_subtensor(_network: Optional[str] = None, _config: Optional[bittensor.config] = None, _log_verbose=False):
        return bittensor.subtensor(network=_network, config=_config, log_verbose=_log_verbose)

    subtensor = _create_subtensor(network, config, log_verbose)
    return subtensor

class NotRegistered(Exception):
    pass

def is_registered(metagraph: bittensor.metagraph, ss58_address: str):
    if ss58_address not in metagraph.hotkeys:
        print(f"{ss58_address} is not registered.")
        raise NotRegistered()
    else:
        uid = metagraph.hotkeys.index(ss58_address)
        print(f"{ss58_address} is registered with {uid} uid.")
        return uid

BLOCKS_WITHOUT_SETTING_WEIGHTS_THRESHOLD = 500

class HealthChecker:
    def __init__(self, pm2_process_names, disk_limit: int):
        log("Initializing HealthChecker")
        self.hostname = socket.gethostname()
        self.ss58_address = "5Hb63SvXBXqZ8zw6mwW1A39fHdqUrJvohXgepyhp2jgWedSB"
        self.disk_state = self.check_disk_space(disk_limit)
        log("Listing pm2 processes")
        pm2_processes = self.list_pm2_process()
        
        if pm2_process_names and len(pm2_process_names):
            pm2_processes = list(filter(lambda x: x.name in pm2_process_names, pm2_processes))
            
        # start a thread for each log file
        self.threads = [LogReader(self, pm2_process) for pm2_process in pm2_processes]

        for log_reader in self.threads:
            log_reader.start()

        self.is_running = True
        self.monitoring_thread = threading.Thread(target=self.monitor_processes)
        self.monitoring_thread.start()
    
    def wait(self):
        for log_reader in self.threads:
            log_reader.join()
        self.monitoring_thread.join()

    @classmethod
    def check_disk_space(cls, disk_limit) -> list:
        partition_almost_full = []
        partitions = psutil.disk_partitions()
        for partition in partitions:
            partition_info = psutil.disk_usage(partition.mountpoint)
            total_space = round(partition_info.total / (1024 * 1024 * 1024), 2)
            used_space = round(partition_info.used / (1024 * 1024 * 1024), 2)
            free_space = round(partition_info.free / (1024 * 1024 * 1024), 2)
            # Pass if the volume is less than 30 Gb
            if total_space <= 30:
                continue
            if partition_info.percent > disk_limit:
                msg = f"Partition: {partition.device}, Total: {total_space} GB, Used: {used_space} GB, Free: {free_space} GB, Percentage used: {partition_info.percent}%"
                partition_almost_full.append(msg)
        return partition_almost_full

    def monitor_processes(self):
        while True:
            log("Monitoring processes")
            subtensor = get_subtensor(log_verbose=True)
            for log_reader in self.threads:
                try:
                    last_line_timestamp = log_reader.get_stats().get("last_line_timestamp")
                    last_line_delta = time.time() - last_line_timestamp
                    if last_line_delta > 900: # no new logs for more than 15 minutes
                        log(f"Restarting pm2 process {log_reader.pm2_process.name}")
                        log_reader.restart_pm2_process()
                    else:
                        log(f"PM2 process {log_reader.pm2_process.name} is ok, last log line was {int(last_line_delta)} seconds ago")
                except Exception as e:
                    print(e)
                netuid = log_reader.pm2_process.netuid
                if netuid and netuid > 0:
                    try:
                        metagraph = subtensor.metagraph(netuid)
                        curr_block = subtensor.block

                        try:
                            validator_uid = is_registered(metagraph, self.ss58_address)
                        except NotRegistered:
                            print(f"netuid: {netuid:<3} | not registered on netuid")
                            return

                        updated_block_since = curr_block - metagraph.last_update[validator_uid]
                        x_blocks_since_last_restart = curr_block - log_reader.last_restart_block
                        if updated_block_since >= BLOCKS_WITHOUT_SETTING_WEIGHTS_THRESHOLD and x_blocks_since_last_restart >= BLOCKS_WITHOUT_SETTING_WEIGHTS_THRESHOLD:
                            log(f"Restarting pm2 process {log_reader.pm2_process.name} cause it hasn't set weights in {BLOCKS_WITHOUT_SETTING_WEIGHTS_THRESHOLD} blocks")
                            log_reader.restart_pm2_process()
                            log_reader.last_restart_block = curr_block
                    except Exception as e:
                        print(e)
            time.sleep(150)


    def stop(self):
        self.is_running = False
        for log_reader in self.threads:
            log_reader.join()
            self.thread.join()
    
    def list_pm2_process(self):
        try:
            # Run 'pm2 jlist' to get a JSON-formatted list of all PM2 processes
            result = subprocess.run(['pm2', 'jlist'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Check for errors in running the command
            if result.returncode != 0:
                log("Error running pm2 command:", result.stderr)
                return False
            
            # Parse the JSON output
            processes = json.loads(result.stdout)
            
            # Search for the process with the specified name
            return [PM2Process(process) for process in processes]
        except Exception as e:
            log(f"An error occurred: {e}")
            return []


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Miner PM2 health check")
    
    parser.add_argument('--pm2', nargs='+', type=str)
    parser.add_argument('--disk_limit', type=int, default=90)

    try:
        args = parser.parse_args()

        health_checker = HealthChecker(args.pm2, args.disk_limit)
        health_checker.wait()
    except Exception as e:
        traceback.print_exc()
        print(e)
