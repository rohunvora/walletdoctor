web: gunicorn src.api.wallet_analytics_api_v4_gpt:app --workers $WEB_CONCURRENCY --timeout 120 --bind "0.0.0.0:$PORT" --log-level info --access-logfile -
