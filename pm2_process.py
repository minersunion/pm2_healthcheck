
from typing import List

class PM2Process:
    name: str
    interpreter: str
    args: List
    pm_out_log_path: str
    pm_err_log_path: str
    status: str
    pm2_home: str
    venv: str
    pwd: str
    git_revision: str
    git_comment: str
    git_branch: str
    git_repo_path: str
    netuid = -1
    subtensor = ""
    coldkey_name = ""
    hotkey_name = ""

    def __init__(self, pm2_jlist_process):
        pm2_env = pm2_jlist_process["pm2_env"]
        self.name = pm2_jlist_process["name"]
        self.interpreter = pm2_env["exec_interpreter"]
        self.args = pm2_env.get("args", [])
        self.pm_out_log_path = pm2_env["pm_out_log_path"]
        self.pm_err_log_path = pm2_env["pm_err_log_path"]
        self.status = pm2_env["status"]
        pm2_env_env = pm2_env.get("env", {})
        self.pm2_home = pm2_env_env.get("PM2_HOME")
        self.venv = pm2_env_env.get("VIRTUAL_ENV")
        self.pwd = pm2_env_env.get("PWD")
        versioning = pm2_env.get("versioning") or {}
        self.git_revision = versioning.get("revision", "N/A")
        self.git_comment = versioning.get("comment", "N/A")
        self.git_branch = versioning.get("branch", "N/A")
        self.git_repo_path = versioning.get("repo_path", "N/A")

        if "--netuid" in self.args:
            netuid_arg_index =  self.args.index("--netuid")
            self.netuid = int(self.args[netuid_arg_index+1])

        if "--subtensor.network" in self.args:
            subtensor_arg_index =  self.args.index("--subtensor.network")
            self.subtensor = self.args[subtensor_arg_index+1]

        if "--wallet.name" in self.args:
            coldkey_arg_index =  self.args.index("--wallet.name")
            self.coldkey_name = self.args[coldkey_arg_index+1]

        if "--wallet.hotkey" in self.args:
            hotkey_arg_index =  self.args.index("--wallet.hotkey")
            self.hotkey_name = self.args[hotkey_arg_index+1]
    
    def to_json(self):
        return {
            "name": self.name,
            # "interpreter": self.interpreter,
            # "args": self.args,
            # "pm_out_log_path": self.pm_out_log_path,
            # "pm_err_log_path": self.pm_err_log_path,
            "status": self.status,
            # "pm2_home": self.pm2_home,
            # "venv": self.venv,
            "pwd": self.pwd,
            "git_revision": self.git_revision,
            "git_comment": self.git_comment,
            "git_branch": self.git_branch,
            "git_repo_path": self.git_repo_path,
            "netuid": self.netuid,
            "subtensor": self.subtensor,
            "coldkey_name": self.coldkey_name,
            "hotkey_name": self.hotkey_name
        }
