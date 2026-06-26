from collections import Counter


def analyze_components(job_data):

    component_types = []

    for component in job_data["components"]:
        component_types.append(component["component_type"])

    return Counter(component_types)