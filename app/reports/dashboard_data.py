import streamlit as st

from app.utils.zip_extractor import extract_zip

from app.parser.repository_scanner import find_talend_jobs
from app.parser.talend_xml_parser import TalendJobParser
from app.cache.cache_manager import CacheManager as _CacheManager
_tma_cache = _CacheManager()

from app.analyzers.complexity_analyzer import calculate_complexity
from app.analyzers.component_analyzer import analyze_components
from app.analyzers.deprecated_checker import analyze_component_risks
from app.analyzers.cloud_readiness import calculate_cloud_readiness

from app.reports.excel_report import export_excel

from app.ai.repository_ai_context import _repository_summary as _build_repository_summary


def generate_repository_summary(jobs_data):
    """Lightweight repository summary for the legacy MVP dashboard."""
    return _build_repository_summary(jobs_data)


def generate_dashboard_metrics(jobs_data):
    """Compute summary metrics for the legacy MVP dashboard."""
    total_jobs = len(jobs_data)
    total_components = sum(len(job.get("components", [])) for job in jobs_data)
    high_risk_components = sum(
        len(analyze_component_risks(job)) for job in jobs_data
    )
    return {
        "total_jobs": total_jobs,
        "total_components": total_components,
        "high_risk_components": high_risk_components,
    }



# ---------------------------------------------------
# Streamlit Config
# ---------------------------------------------------

st.set_page_config(
    page_title="Talend Migration Accelerator",
    layout="wide"
)

st.title("Talend Migration Accelerator MVP v2")

st.markdown("AI-Assisted Talend Open Studio → Talend Cloud Migration Platform")


# ---------------------------------------------------
# Upload ZIP Repository
# ---------------------------------------------------

uploaded_file = st.file_uploader(
    "Upload Talend Repository ZIP",
    type=["zip"]
)

# ---------------------------------------------------
# Process Repository
# ---------------------------------------------------

if uploaded_file:

    zip_path = "uploaded_repository.zip"

    with open(zip_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.success("ZIP uploaded successfully")

    # ---------------------------------------------------
    # Extract ZIP
    # ---------------------------------------------------

    with st.spinner("Extracting Repository..."):

        repo_path = extract_zip(zip_path)

    st.success("Repository extracted")

    # ---------------------------------------------------
    # Find Talend Jobs
    # ---------------------------------------------------

    job_files = find_talend_jobs(repo_path)

    st.info(f"Found {len(job_files)} Talend jobs")

    all_jobs = []

    # ---------------------------------------------------
    # Parse All Jobs
    # ---------------------------------------------------

    progress_bar = st.progress(0)

    for index, file in enumerate(job_files):

        try:

            job_data = _tma_cache.load_or_parse(file)

            complexity = calculate_complexity(job_data)

            component_summary = analyze_components(job_data)

            risk_report = analyze_component_risks(job_data)

            readiness = calculate_cloud_readiness(job_data)

            job_result = {
                "job_data": job_data,
                "complexity": complexity,
                "component_summary": component_summary,
                "risk_report": risk_report,
                "cloud_readiness": readiness
            }

            all_jobs.append(job_result)

        except Exception as e:

            st.warning(f"Failed to process: {file}")

        progress_bar.progress((index + 1) / len(job_files))

    # ---------------------------------------------------
    # Dashboard Metrics
    # ---------------------------------------------------

    dashboard_metrics = generate_dashboard_metrics(
        [job["job_data"] for job in all_jobs]
    )

    st.header("Repository Dashboard")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total Jobs",
        dashboard_metrics["total_jobs"]
    )

    col2.metric(
        "Total Components",
        dashboard_metrics["total_components"]
    )

    col3.metric(
        "High Risk Components",
        dashboard_metrics["high_risk_components"]
    )

    # ---------------------------------------------------
    # AI Repository Summary
    # ---------------------------------------------------

    with st.spinner("Generating AI Repository Summary..."):

        ai_summary = generate_repository_summary(
            [job["job_data"] for job in all_jobs]
        )

    st.header("AI Migration Summary")

    st.write(ai_summary)

    # ---------------------------------------------------
    # Detailed Job Analysis
    # ---------------------------------------------------

    st.header("Detailed Job Analysis")

    for job in all_jobs:

        with st.expander(
            job["job_data"]["job_name"]
        ):

            st.subheader("Job Metadata")

            st.json(job["job_data"])

            st.subheader("Complexity Analysis")

            st.write(job["complexity"])

            st.subheader("Component Summary")

            st.write(job["component_summary"])

            st.subheader("Component Risk Analysis")

            st.json(job["risk_report"])

            st.subheader("Cloud Readiness")

            st.write(job["cloud_readiness"])

    # ---------------------------------------------------
    # Excel Export
    # ---------------------------------------------------

    report_file = export_excel(
        [job["job_data"] for job in all_jobs]
    )

    with open(report_file, "rb") as f:

        st.download_button(
            label="Download Excel Report",
            data=f,
            file_name="migration_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.success("Migration assessment completed successfully")