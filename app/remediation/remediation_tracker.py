"""
Remediation Tracker
Tracks fixed, pending, and in-progress remediation tasks.
"""

import json
import os

TRACKER_FILE = "remediation_state.json"


class RemediationTracker:

    def __init__(self):

        self.state = self._load()

    def _load(self) -> dict:

        if os.path.exists(TRACKER_FILE):

            with open(TRACKER_FILE, "r") as f:

                return json.load(f)

        return {
            "tasks": [],
            "fixed": [],
            "pending": [],
            "in_progress": []
        }

    def _save(self):

        with open(TRACKER_FILE, "w") as f:

            json.dump(self.state, f, indent=4)

    def add_task(
        self,
        job_name: str,
        issue: str,
        severity: str
    ):

        task = {
            "job": job_name,
            "issue": issue,
            "severity": severity,
            "status": "PENDING"
        }

        self.state["tasks"].append(task)
        self.state["pending"].append(task)
        self._save()

    def mark_fixed(
        self,
        job_name: str,
        issue: str
    ):

        self.state["pending"] = [
            t for t in self.state["pending"]
            if not (
                t["job"] == job_name
                and t["issue"] == issue
            )
        ]

        self.state["fixed"].append({
            "job": job_name,
            "issue": issue,
            "status": "FIXED"
        })

        self._save()

    def get_summary(self) -> dict:

        return {
            "total_tasks": len(
                self.state["tasks"]
            ),
            "fixed": len(
                self.state["fixed"]
            ),
            "pending": len(
                self.state["pending"]
            ),
            "in_progress": len(
                self.state["in_progress"]
            ),
            "completion_pct": (
                round(
                    len(self.state["fixed"]) /
                    max(len(self.state["tasks"]), 1)
                    * 100,
                    1
                )
            )
        }

    def build_from_blockers(
        self,
        blockers_result: dict
    ):

        for item in blockers_result.get(
            "hard_blockers", []
        ):
            self.add_task(
                item["job"],
                item["action"],
                "CRITICAL"
            )

        for item in blockers_result.get(
            "soft_blockers", []
        ):
            self.add_task(
                item["job"],
                item["action"],
                "WARNING"
            )
