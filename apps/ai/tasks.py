from celery import shared_task

from apps.ai.services import run_topic_analysis


@shared_task(
    bind=True,
    name="ai.run_topic_analysis",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=2,
)
def run_topic_analysis_task(self, analysis_job_id: str):
    return str(run_topic_analysis(analysis_job_id=analysis_job_id).id)
