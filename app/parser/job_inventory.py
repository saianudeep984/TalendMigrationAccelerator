from pathlib import Path


def scan_jobs(project_path):

    item_files = []

    for file in Path(project_path).rglob("*.item"):
        item_files.append(str(file))

    return item_files


if __name__ == "__main__":

    jobs = scan_jobs("sample_projects")

    for job in jobs:
        print(job)