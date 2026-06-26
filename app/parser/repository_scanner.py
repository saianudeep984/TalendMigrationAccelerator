import os


def find_talend_jobs(repo_path):

    job_files = []

    for root, dirs, files in os.walk(repo_path):

        # ONLY scan process folder
        if "process" not in root.lower():
            continue

        for file in files:

            if file.endswith(".item"):

                full_path = os.path.join(root, file)

                job_files.append(full_path)

    return job_files