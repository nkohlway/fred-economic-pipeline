# FRED Economic Pipeline

A serverless AWS data pipeline that automatically ingests, transforms, and catalogs 
economic indicators from the Federal Reserve Economic Data (FRED) API — built as a 
hands-on cloud engineering project targeting the AWS Data Engineer Associate certification.

## Overview

This project pulls four economic time-series from FRED on a weekly Friday schedule, 
lands raw JSON in S3, transforms it into Parquet, catalogs it with Glue, and exposes 
it for SQL analysis via Athena. It was built incrementally to gain real hands-on AWS 
experience — debugging IAM permissions, Lambda layers, and Glue crawler configuration 
along the way.

**FRED Series tracked:**
| Series | Description |
|---|---|
| `MORTGAGE30US` | 30-Year Fixed Mortgage Rate |
| `CPIAUCSL` | Consumer Price Index (All Urban Consumers) |
| `UNRATE` | Unemployment Rate |
| `HOUST` | Housing Starts |

## Architecture

*(See diagram below)*

## Tech Stack

| Service | Purpose |
|---|---|
| **Lambda** | Ingestion (`fred-ingest`) and transformation (`fred-transform`) |
| **EventBridge** | Weekly scheduled trigger (Friday cadence) |
| **S3** | Raw and processed data storage with Hive partitioning |
| **Glue Crawler** | Schema cataloging of processed Parquet files |
| **Athena** | Serverless SQL querying |
| **IAM** | Least-privilege roles for Lambda and EC2 |
| **EC2** | Development instance (t3.micro, Amazon Linux 2023) |
| **SSM** | Secure shell access without open SSH ports |
| **CloudWatch** | Lambda monitoring and custom EC2 metrics |
| **Lambda Layer** | `AWSSDKPandas-Python312` (x86_64) for PyArrow |

## Status

**Complete:**
- [x] S3 buckets with Hive-style partitioning and lifecycle rules
- [x] IAM roles with least-privilege policies
- [x] EC2 development instance with SSM access (no open SSH port)
- [x] CloudWatch agent for memory/disk metrics
- [x] Lambda ingestion function (`fred-ingest`) pulling 4 FRED series
- [x] EventBridge weekly trigger (Friday schedule)
- [x] Lambda transformation function (`fred-transform`) — JSON → Parquet via PyArrow
- [x] Glue Crawler cataloging processed data into `fred_processed_db`
- [x] Athena queries running against cataloged data

**In Progress:**
- [ ] Lambda source code pushed to this repo
- [ ] Architecture diagram
- [ ] Deeper Athena analysis queries

**Planned:**
- [ ] AWS Data Engineer Associate exam prep
- [ ] Expanded economic series coverage
- [ ] Analysis notebook

## Key Engineering Decisions & Lessons Learned

**Lambda over Glue ETL for transformation**
A Glue ETL job was attempted for the transformation step, but abandoned after persistent 
`IllegalArgumentException: Can not create a Path from an empty string` errors that 
survived multiple fresh job attempts. The root cause was likely a missing `default` 
Glue database or Spark warehouse configuration issue. Lambda with the AWSSDKPandas 
layer was chosen as the pragmatic replacement — simpler to debug, faster to iterate, 
and appropriate for this data volume. The Glue ETL job is retained in the account for 
reference.

**EventBridge async invocation**
Lambda destinations for automatic function chaining require asynchronous invocation. 
EventBridge satisfies this; the manual Lambda Test button does not — an important 
distinction when debugging chained functions.

**EC2 free tier expiry**
This account is past 12 months, so EC2 compute and public IPv4 usage are billed at 
on-demand rates. The development instance is stopped between sessions to manage costs.

**IMDSv2**
The EC2 instance requires token-based metadata requests (IMDSv2) — relevant when 
configuring the CloudWatch agent and SSM.

## Cost Management

Built to minimize AWS spend. The EC2 instance is stopped between sessions. S3 lifecycle 
rules expire raw data after 30 days. Athena costs are minimized by querying only 
Parquet (columnar format reduces data scanned). Glue Crawler runs are triggered 
manually rather than on a schedule.

## Repository Structure

## License

MIT
