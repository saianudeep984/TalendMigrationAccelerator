#!/bin/bash
echo "Starting Talend Migration Accelerator..."
cd "$(dirname "$0")/.."
pip install -r requirements.txt --quiet
streamlit run app/ui/streamlit_app.py --server.port 8501
