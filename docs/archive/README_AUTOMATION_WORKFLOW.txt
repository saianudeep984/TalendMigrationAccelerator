
# Talend Migration Automation Platform

## Updated Workflow

1. Upload Open Studio ZIP
2. Provide Talend Studio executable path
3. Platform launches Talend Studio automatically
4. Talend migration engine executes internally
5. Platform exports migrated repository
6. Download migrated repository ZIP

## Important

Do NOT manually import generated ZIPs using:
Import Items → Select ZIP

The platform now orchestrates Talend Studio migration internally.
