import logging
import os

from app.scheduler import register_jobs
from wsgi import app

logging.basicConfig(level=logging.INFO)

if os.environ.get("DISABLE_SCHEDULER") != "1":
    register_jobs(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
