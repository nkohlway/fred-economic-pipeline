import json
import urllib.request
import boto3
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# FRED Economic Data Ingestion
# Triggered weekly by EventBridge (Friday schedule)
# Pulls 4 FRED economic series and writes raw JSON to S3
# ---------------------------------------------------------------------------

s3 = boto3.client('s3')

BUCKET_NAME = 'fred-raw-nkohlway-2026'
API_KEY = os.environ['FRED_API_KEY']  # Stored in Lambda environment variables

# FRED series to ingest — maps API series ID to a human-readable label
# used in S3 key naming
SERIES_IDS = {
    'MORTGAGE30US': 'mortgage_30yr',    # 30-year fixed mortgage rate
    'CPIAUCSL':     'cpi',              # Consumer Price Index (all urban consumers)
    'UNRATE':       'unemployment_rate', # Unemployment rate
    'HOUST':        'housing_starts'    # Housing starts
}

FRED_BASE_URL = 'https://api.stlouisfed.org/fred/series/observations'


def fetch_series(series_id: str) -> dict:
    """Fetch all observations for a FRED series and return as a dict."""
    url = f"{FRED_BASE_URL}?series_id={series_id}&api_key={API_KEY}&file_type=json"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())


def build_s3_key(label: str, dt: datetime) -> str:
    """
    Build a Hive-style partitioned S3 key.
    Example: year=2026/month=01/day=03/mortgage_30yr.json
    Partitioning enables efficient Athena queries filtered by date.
    """
    return (
        f"year={dt.year}/"
        f"month={dt.month:02d}/"
        f"day={dt.day:02d}/"
        f"{label}.json"
    )


def lambda_handler(event, context):
    """
    Main Lambda entry point.
    Iterates over SERIES_IDS, fetches each from FRED, and writes raw JSON
    to S3 with Hive-style date partitioning.
    """
    today = datetime.utcnow()
    files_written = []
    errors = []

    for series_id, label in SERIES_IDS.items():
        try:
            # Fetch raw data from FRED API
            data = fetch_series(series_id)

            # Annotate with series metadata before writing
            data['series_id'] = series_id
            data['series_label'] = label
            data['ingested_at'] = today.isoformat()

            # Build S3 key and write
            key = build_s3_key(label, today)
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=json.dumps(data),
                ContentType='application/json'
            )

            files_written.append(key)
            print(f"[OK] {series_id} → s3://{BUCKET_NAME}/{key}")

        except Exception as e:
            error_msg = f"[ERROR] {series_id}: {str(e)}"
            print(error_msg)
            errors.append(error_msg)

    # Return summary — visible in CloudWatch logs and Lambda destinations
    return {
        'statusCode': 200 if not errors else 207,
        'body': json.dumps({
            'ingestion_date': today.strftime('%Y-%m-%d'),
            'files_written': files_written,
            'errors': errors
        })
    }
