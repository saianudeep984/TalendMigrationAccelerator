import streamlit as st
import plotly.express as px
import pandas as pd
from typing import List, Dict, Any


def show_dashboard(all_jobs: List[Dict[str, Any]]) -> None:
    """
    Display executive migration dashboard.

    Args:
        all_jobs (List[Dict]): List of analyzed Talend jobs
    """

    st.header("📊 Executive Dashboard")

    # Handle empty input
    if not all_jobs:
        st.warning("No job data available for dashboard.")
        return

    complexity_data = []

    for job in all_jobs:

        job_data = job.get("job_data", {})
        estimation = job.get("estimation", {})

        complexity_data.append({
            "job_name": job_data.get("job_name", "Unknown"),
            "complexity": estimation.get("complexity", "N/A"),
            "hours": estimation.get("estimated_hours", 0)
        })

    # Create dataframe
    df = pd.DataFrame(complexity_data)

    # Display dataframe
    st.subheader("Migration Summary")
    st.dataframe(df, width="stretch")

    # Complexity Distribution Chart
    st.subheader("Complexity Distribution")

    fig_complexity = px.histogram(
        df,
        x="complexity",
        color="complexity",
        title="Jobs by Complexity Level"
    )

    st.plotly_chart(
        fig_complexity,
        width="stretch"
    )

    # Effort Estimation Chart
    st.subheader("Estimated Migration Effort")

    fig_effort = px.bar(
        df,
        x="job_name",
        y="hours",
        color="complexity",
        title="Estimated Migration Hours per Job"
    )

    st.plotly_chart(
        fig_effort,
        width="stretch"
    )