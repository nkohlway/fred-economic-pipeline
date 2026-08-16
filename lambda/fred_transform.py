import json
import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import io
from datetime import datetime

# ---------------------------------------------------------------------------
# FRED Economic Data Transformation
# Triggered by Lambda destination after fred-ingest completes
# Reads raw JSON from S3, flattens observations, writes Parquet to processed bucket
# ---------------------------------------------------------------------------

s3 = boto3.client('s3')

RAW_BUCKET       = 'fred-raw-nkohlway-2026'
PROCESSED_BUCKET = 'fred-processed-nkohlway-2026'

# PyArrow schema — explicit typing ensures consistent Parquet output
# and clean Glue Crawler inference
SCHEMA = pa.schema([
    ('series_id',    pa.string()),
    ('series_label', pa.string()),
    ('date',         pa.string()),  # kept as string to preserve FRED's YYYY-MM-DD format
    ('value',        pa.float64()), # null where FRED reports '.' (missing data)
    ('ingested_at',  pa.string()),  # propagated from raw file metadata
])


def read_raw_file(key: str) -> dict:
    """Read and parse a raw JSON file from the S3 raw bucket."""
    raw = s3.get_object(Bucket=RAW_BUCKET, Key=key)
    return json.loads(raw['Body'].read().decode('utf-8'))


def flatten_observations(data: dict) -> list[dict]:
    """
    Flatten the FRED observations array into individual row dicts.
    FRED represents missing values as '.', which we convert to None
    so PyArrow writes them as proper nulls in the Parquet file.
    """
    series_id    = data.get('series_id', '')
    series_label = data.get('series_label', '')
    ingested_at  = data.get('ingested_at', '')
    rows = []

    for obs in data.get('observations', []):
        raw_value = obs.get('value', '.')
        rows.append({
            'series_id':    series_id,
            'series_label': series_label,
            'date':         obs.get('date', ''),
            'value':        float(raw_value) if raw_value != '.' else None,
            'ingested_at':  ingested_at
        })

    return rows


def rows_to_parquet(rows: list[dict]) -> bytes:
    """Convert a list of row dicts to Parquet bytes using the defined schema."""
    table = pa.table(
        {
            'series_id':    pa.array([r['series_id']    for r in rows], type=pa.string()),
            'series_label': pa.array([r['series_label'] for r in rows], type=pa.string()),
            'date':         pa.array([r['date']         for r in rows], type=pa.string()),
            'value':        pa.array([r['value']        for r in rows], type=pa.float64()),
            'ingested_at':  pa.array([r['ingested_at']  for r in rows], type=pa.string()),
        },
        schema=SCHEMA
    )
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()


def lambda_handler(event, context):
    """
    Main Lambda entry point.
    Lists all raw JSON files in today's S3 partition, flattens each into
    row-level observations, and writes a single Parquet file to the
    processed bucket under the same Hive-style partition key.
    """
    today  = datetime.utcnow()
    prefix = f"year={today.year}/month={today.month:02d}/day={today.day:02d}/"

    # List all files in today's partition
    response = s3.list_objects_v2(Bucket=RAW_BUCKET, Prefix=prefix)

    if 'Contents' not in response:
        print(f"[WARN] No raw files found under s3://{RAW_BUCKET}/{prefix}")
        return {
            'statusCode': 404,
            'body': f"No files found for partition: {prefix}"
        }

    all_rows = []

    for obj in response['Contents']:
        key = obj['Key']
        try:
            data = read_raw_file(key)
            rows = flatten_observations(data)
            all_rows.extend(rows)
            print(f"[OK] Flattened {len(rows)} observations from {key}")
        except Exception as e:
            print(f"[ERROR] Failed to process {key}: {str(e)}")

    if not all_rows:
        print("[ERROR] No observations extracted — aborting Parquet write")
        return {
            'statusCode': 500,
            'body': 'No observations extracted from raw files'
        }

    # Convert all rows to a single Parquet file and upload
    output_key = f"{prefix}fred_observations.parquet"
    parquet_bytes = rows_to_parquet(all_rows)

    s3.put_object(
        Bucket=PROCESSED_BUCKET,
        Key=output_key,
        Body=parquet_bytes,
        ContentType='application/octet-stream'
    )

    print(f"[OK] Wrote {len(all_rows)} rows → s3://{PROCESSED_BUCKET}/{output_key}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'partition':    prefix,
            'rows_written': len(all_rows),
            'output_key':   output_key
        })
    }
