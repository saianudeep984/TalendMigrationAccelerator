"""
TalendCommandExecutor — safely invokes Talend Studio CLI commands.

Fixed from original:
- Replaced shell=True with shell=False (list-based args) to prevent
  command injection from user-supplied paths.
- Added timeout (default 300 s) so a hung Studio process never blocks
  the Streamlit UI indefinitely.
- Surfaces a clear error dict on TimeoutExpired.
"""

import subprocess


class TalendCommandExecutor:

    def __init__(self, timeout: int = 300):
        self.timeout = timeout

    def execute(self, command, workspace=None):
        """
        Parameters
        ----------
        command : list[str]
            Argument list ready for subprocess — never a raw string.
        workspace : str | None
            Unused; kept for backwards compatibility.

        Returns
        -------
        dict with keys: returncode, stdout, stderr
        """
        if isinstance(command, str):
            # Defensive shim: callers that still pass a string get a
            # clear error rather than a silent shell=True fallback.
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": (
                    "TalendCommandExecutor received a raw string command. "
                    "Pass a list of arguments instead (shell=False required)."
                ),
            }

        try:
            process = subprocess.run(
                command,
                shell=False,          # <-- key security fix
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            return {
                "returncode": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            }

        except subprocess.TimeoutExpired:
            return {
                "returncode": -2,
                "stdout": "",
                "stderr": (
                    f"Talend Studio CLI timed out after {self.timeout} s. "
                    "The process has been killed. "
                    "Try increasing the timeout or running Studio manually."
                ),
            }

        except FileNotFoundError:
            return {
                "returncode": -3,
                "stdout": "",
                "stderr": (
                    f"Executable not found: {command[0]}. "
                    "Check the Talend Studio path is correct."
                ),
            }

        except Exception as exc:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(exc),
            }
