class MigrationChecklistEngine:
    def generate(self, upgrade=None):
        return {
            "pre_migration": ["Freeze scope", "Backup repository", "Confirm source/target versions", "Resolve critical blockers"],
            "migration": ["Apply component fixes", "Run wave migration", "Build jobs", "Capture defects"],
            "validation": ["Run unit tests", "Run reconciliation", "Validate lineage", "Validate schedules"],
            "go_live": ["Approve cutover", "Deploy packages", "Enable monitoring", "Business smoke test"],
            "rollback": ["Stop target jobs", "Restore source schedules", "Restore repository backup", "Communicate rollback status"],
        }
