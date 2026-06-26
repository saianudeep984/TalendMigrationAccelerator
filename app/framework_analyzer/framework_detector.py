from __future__ import annotations
from app.upgrade_advisor.upgrade_inventory import components, ctype


class FrameworkDetectionEngine:
    RULES = {
        "metadata_framework": {"tDBInput", "tDBOutput", "tFileInputDelimited", "tFileOutputDelimited"},
        "audit_framework": {"tStatCatcher", "tFlowMeterCatcher", "tFlowMeter"},
        "error_handling_framework": {"tDie", "tWarn", "tLogCatcher"},
        "notification_framework": {"tSendMail", "tRESTClient", "tHTTPRequest"},
        "batch_framework": {"tPrejob", "tPostjob", "tRunJob"},
        "restartability_framework": {"tCheckpoint", "tSetGlobalVar", "tHashOutput", "tHashInput"},
        "logging_framework": {"tLogRow", "tLogCatcher", "tStatCatcher"},
        "reusable_joblet_framework": {"tJoblet", "tRunJob"},
        "context_framework": {"tContextLoad", "tContextDump"},
        "scheduling_framework": {"tWaitForFile", "tSleep", "tLoop"},
    }
    def detect(self, jobs):
        types = [ctype(c) for j in jobs or [] for c in components(j)]
        findings = {}
        for name, comps in self.RULES.items():
            hits = [t for t in types if t in comps or (name == "reusable_joblet_framework" and "Joblet" in t)]
            findings[name] = {"detected": bool(hits), "usage_count": len(hits), "components": sorted(set(hits))}
        return findings
