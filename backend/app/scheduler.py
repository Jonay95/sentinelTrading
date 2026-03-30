"""
Jobs APScheduler: invocan casos de uso a través del contenedor (misma orquestación que la API).
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app import config as app_config
from app.container import get_container

logger = logging.getLogger(__name__)

scheduler: BackgroundScheduler | None = None


def _with_app(app, fn, *args, **kwargs):
    with app.app_context():
        return fn(*args, **kwargs)


def register_jobs(app):
    global scheduler
    if scheduler is not None:
        return scheduler

    sched = BackgroundScheduler()

    def job_ingest():
        def _run():
            get_container().ingest_market.execute()

        _with_app(app, _run)

    def job_news():
        def _run():
            get_container().ingest_news.execute(force=False)

        _with_app(app, _run)

    def job_predict():
        def _run():
            mv = app_config.Config.MODEL_VERSION
            get_container().run_predictions.execute(mv)

        _with_app(app, _run)

    def job_eval():
        def _run():
            get_container().evaluate_predictions.execute()

        _with_app(app, _run)

    sched.add_job(job_ingest, "cron", hour=6, minute=5, id="ingest_daily")
    sched.add_job(job_news, "cron", hour=6, minute=20, id="news_daily")
    sched.add_job(job_predict, "cron", hour=6, minute=35, id="predict_daily")
    sched.add_job(job_eval, "cron", hour="*/6", minute=10, id="eval_periodic")

    sched.start()
    scheduler = sched
    logger.info("APScheduler started")
    return sched
