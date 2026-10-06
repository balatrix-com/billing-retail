# Project Overview

The **CDR Analytics System** is a real-time data processing and visualization platform designed to handle Call Detail Records (CDRs). It transitions data from raw billing logs into actionable insights displayed on a web dashboard.

## Objectives

- **High Performance**: Process large batches of CDRs efficiently without impacting the main billing database.
- **Reliability**: Use a persistent PostgreSQL-based metrics store to ensure data is never lost, even if components restart.
- **Actionable Insights**: Provide key performance indicators (KPIs), daily trends, and distribution metrics for customers.

## Core Features

- **Automated Processing**: A background loop continuously polls the source database for new CDRs.
- **Aggregated Metrics**: Data is summarized by day, hour, and DID (Direct Inward Dialing) numbers.
- **Unified API**: A single endpoint provides all dashboard data in a format optimized for frontend rendering.
- **Dual-DB Architecture**: Separates the high-traffic source data from the analytics-optimized metrics store.

## Technology Stack

- **Backend**: Python 3.11+
- **API Framework**: FastAPI
- **Server**: Uvicorn (managed via Multiprocessing)
- **Database**: PostgreSQL (Source and Metrics)
- **Configuration**: Pydantic Settings & `.env`
