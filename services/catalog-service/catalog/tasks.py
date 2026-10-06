from celery import shared_task


@shared_task
def add_numbers(a, b):
    return a + b
