from app.ai.context_accessor import get_ai_context
from app.ai.llm_engine import ask_ollama


DEFAULT_MIGRATION_RECOMMENDATION_PROMPT = """
You are a Talend Cloud migration expert.

Analyze this Talend job.

Job Name:
{job_name}

Components Used:
{component_list}

Provide:

1. Migration Risks
2. Cloud Migration Recommendations
3. Required Remediation Steps
4. Best Practices

Keep response concise.
"""


def build_migration_recommendation_prompt(job_data, prompt_template: str = None):

    component_list = []

    for component in job_data["components"]:

        component_list.append(
            component["component_type"]
        )

    template = prompt_template or DEFAULT_MIGRATION_RECOMMENDATION_PROMPT
    values = {
        "job_name": job_data["job_name"],
        "component_list": component_list,
    }
    try:
        return template.format(**values)
    except Exception:
        return DEFAULT_MIGRATION_RECOMMENDATION_PROMPT.format(**values)


def generate_migration_recommendation(job_data, use_ollama: bool = True, prompt_template: str = None):
    prompt = build_migration_recommendation_prompt(job_data, prompt_template)

    ctx=get_ai_context()
    if ctx.get("migration_recommendations"):
        return ctx.get("migration_recommendations")
    response = ask_ollama(prompt, use_ollama=use_ollama)
    return response
