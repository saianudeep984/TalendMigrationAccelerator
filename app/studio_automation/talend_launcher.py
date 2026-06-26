
import subprocess


class TalendLauncher:

    def launch(

        self,
        studio_path,
        workspace
    ):

        command = [studio_path, "-data", workspace]

        return subprocess.Popen(
            command,
            shell=False
        )
