from celery import shared_task

from apps.insights.services import run_monthly_insight


@shared_task(
    bind=True,
    name="insights.run_monthly_insight",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=2,
)
def run_monthly_insight_task(self, insight_id: str):
    return str(run_monthly_insight(insight_id=insight_id).id)
