web: gunicorn src.api.wallet_analytics_api_v4_gpt:app --workers $WEB_CONCURRENCY --timeout 120 --worker-class uvicorn.workers.UvicornWorker --bind "0.0.0.0:$PORT"
