from celery import shared_task


@shared_task(name="common.ping")
def ping() -> str:
    return "pong"
