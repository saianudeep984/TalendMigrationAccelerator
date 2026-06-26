"""
Talend Cloud API client.

Bridges the gap between the accelerator's analysis pipeline and the
Talend Cloud REST API — the key feature present in Qlik's Talend Cloud that
was missing from the accelerator.

Supports:
  - Connection test / token validation
  - Listing existing cloud artifacts (plans, connections, tasks)
  - Creating plan shells for migrated jobs
  - Getting migration inventory diff (cloud vs local)

API reference: https://talend.qlik.dev/apis/

Usage:
    client = TalendCloudClient(personal_access_token="...", region="us")
    ok, msg = client.test_connection()
    if ok:
        ok, plan, err = client.publish_job_as_plan("MyJob", workspace_id="abc")
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)


_REGION_URLS = {
    "us": "https://api.us.cloud.talend.com",
    "eu": "https://api.eu.cloud.talend.com",
    "ap": "https://api.ap.cloud.talend.com",
    "au": "https://api.au.cloud.talend.com",
}


class TalendCloudClient:
    """
    Minimal REST client for Talend Cloud / Qlik Talend Cloud API.

    Parameters
    ----------
    personal_access_token : str
        Generated in Talend Cloud Management Console.
        Required scopes: TMC_READER, TMC_OPERATOR (or higher).
    region : str
        One of 'us', 'eu', 'ap', 'au'. Defaults to 'us'.
    timeout : int
        HTTP timeout in seconds for each request.
    """

    def __init__(self, personal_access_token: str, region: str = "us", timeout: int = 30):
        self.token = personal_access_token.strip()
        self.base_url = _REGION_URLS.get(region.lower(), _REGION_URLS["us"])
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get(self, path: str):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = {}
            try:
                body = json.loads(exc.read().decode())
            except Exception:
                logger.exception("Failed to parse Talend Cloud GET error response body.")
                pass
            return exc.code, body
        except Exception as exc:
            logger.exception("Talend Cloud GET request failed.")
            return -1, {"error": str(exc)}

    def _post(self, path: str, payload: dict):
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = {}
            try:
                body = json.loads(exc.read().decode())
            except Exception:
                logger.exception("Failed to parse Talend Cloud POST error response body.")
                pass
            return exc.code, body
        except Exception as exc:
            logger.exception("Talend Cloud POST request failed.")
            return -1, {"error": str(exc)}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def test_connection(self) -> tuple:
        """
        Validates the PAT and region via /security/users/me.
        Returns (True, user_email) or (False, error_message).
        """
        status, body = self._get("/security/users/me")
        if status == 200:
            email = body.get("email", body.get("login", "authenticated"))
            return True, f"Connected as {email}"
        if status == 401:
            return False, "Invalid or expired Personal Access Token."
        if status == 403:
            return False, "Token lacks required permissions (need TMC_READER+)."
        if status == -1:
            return False, body.get("error", "Network error — check region and connectivity.")
        return False, f"Unexpected HTTP {status}: {body}"

    def list_workspaces(self) -> tuple:
        """Returns (True, [workspaces], '') or (False, [], error_msg)."""
        status, body = self._get("/orchestration/workspaces?limit=100")
        if status == 200:
            items = body.get("items", body if isinstance(body, list) else [])
            return True, items, ""
        return False, [], f"HTTP {status}: {body.get('message', body)}"

    def list_plans(self, workspace_id: str = "") -> tuple:
        """Lists existing plans, optionally filtered by workspace."""
        path = "/orchestration/plans?limit=100"
        if workspace_id:
            path += f"&workspaceId={workspace_id}"
        status, body = self._get(path)
        if status == 200:
            items = body.get("items", body if isinstance(body, list) else [])
            return True, items, ""
        return False, [], f"HTTP {status}: {body.get('message', body)}"

    def list_connections(self, workspace_id: str = "") -> tuple:
        """Lists existing connections, optionally filtered by workspace."""
        path = "/orchestration/connections?limit=100"
        if workspace_id:
            path += f"&workspaceId={workspace_id}"
        status, body = self._get(path)
        if status == 200:
            items = body.get("items", body if isinstance(body, list) else [])
            return True, items, ""
        return False, [], f"HTTP {status}: {body.get('message', body)}"

    def get_migration_inventory(self, workspace_id: str = "") -> dict:
        """
        Returns a combined inventory of what currently lives in the cloud
        workspace — useful for diffing against the local repo before pushing.
        """
        _, workspaces, _ = self.list_workspaces()
        ok_p, plans, err_p = self.list_plans(workspace_id)
        ok_c, connections, err_c = self.list_connections(workspace_id)
        return {
            "workspaces": workspaces,
            "plans": plans if ok_p else [],
            "connections": connections if ok_c else [],
            "total_plans": len(plans) if ok_p else 0,
            "total_connections": len(connections) if ok_c else 0,
            "errors": [e for e in [err_p, err_c] if e],
        }

    def publish_job_as_plan(
        self,
        job_name: str,
        workspace_id: str,
        engine_id: Optional[str] = None,
        description: str = "Migrated by Artha Talend Migration Accelerator",
    ) -> tuple:
        """
        Creates a Cloud Data Integration plan shell for a migrated job.

        Note: Binary artifact upload requires the Talend Artifact Repository
        API (tenant-specific URL). This method creates the plan metadata
        record so the job is visible in the cloud workspace. Bind the artifact
        via the API portal: https://talend.qlik.dev/apis/

        Returns (True, plan_dict, '') or (False, {}, error_msg).
        """
        payload: dict = {
            "name": job_name,
            "description": description,
            "workspaceId": workspace_id,
        }
        if engine_id:
            payload["engineId"] = engine_id

        status, body = self._post("/orchestration/plans", payload)
        if status in (200, 201):
            return True, body, ""
        msg = body.get("message", body.get("error", str(body)))
        return False, {}, f"HTTP {status}: {msg}"
