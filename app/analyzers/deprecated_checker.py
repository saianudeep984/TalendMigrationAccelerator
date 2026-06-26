from app.config.component_rules import COMPONENT_RISK_RULES


def analyze_component_risks(job_data):

    risks = []

    for component in job_data["components"]:

        component_type = component["component_type"]

        if component_type in COMPONENT_RISK_RULES:

            risk_data = COMPONENT_RISK_RULES[component_type]

            risks.append({
                "component": component_type,
                "details": risk_data
            })

    return risks