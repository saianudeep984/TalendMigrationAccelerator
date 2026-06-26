
import os


class ManualImportWorkspace:

    def generate(

        self,
        workspace_dir
    ):

        guide_path = os.path.join(

            workspace_dir,

            "migration_guide.md"
        )

        content = """
# Talend Migration Workspace

## Recommended Migration Steps

1. Open Talend Enterprise Studio 8
2. Create a new blank project
3. Import jobs individually
4. Allow Talend internal migration
5. Validate migrated jobs
6. Export migrated repository
7. Upload migrated repository back into accelerator

## Notes

- Talend internally handles:
  - EMF metadata synchronization
  - migration tokens
  - repository signatures
  - Eclipse metadata migration

- This workspace prepares jobs for migration
  but does not replace Talend Studio migration engine.
"""

        with open(

            guide_path,

            "w",

            encoding="utf-8"

        ) as f:

            f.write(content)

        return guide_path
