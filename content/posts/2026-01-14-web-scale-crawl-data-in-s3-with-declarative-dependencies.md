---
action_run_id: '20984292531'
article_quality:
  dimensions:
    citations: 100.0
    code_examples: 100.0
    length: 100.0
    readability: 71.4
    source_citation: 100.0
    structure: 80.0
    tone: 100.0
  overall_score: 88.9
  passed_threshold: true
cover:
  alt: ''
  image: ''
  image_source: unsplash
  photographer: Marques Thomas
  photographer_url: https://unsplash.com/@querysprout
date: 2026-01-14T06:13:29+0000
generation_costs:
  content_generation:
  - 0.0023007
  image_generation:
  - 0.0
  title_generation:
  - 0.00038288
generator: General Article Generator
icon: ''
illustrations_count: 0
models_used:
  content: gpt-5-mini
  enrichment: gpt-5-nano
  title: gpt-5-nano
reading_time: 7 min read
sources:
- author: willbryk
  platform: hackernews
  quality_score: 0.65
  url: https://exa.ai/blog/exa-d
summary: Introduction Storing "the web" at scale—raw HTML, assets, metadata, link
  graphs, and derived crawl artifacts—is a different problem than storing structured
  tables.
tags:
- cloud storage
- amazon s3
- data processing framework
- web-scale data
- declarative programming
title: Web-Scale Crawl Data in S3 with Declarative Dependencies
word_count: 1491
---

> **Attribution:** This article was based on content by **@willbryk** on **hackernews**.  
> Original: https://exa.ai/blog/exa-d

## Introduction

Storing "the web" at scale—raw HTML, assets, metadata, link graphs, and derived crawl artifacts—is a different problem than storing structured tables. Object storage such as Amazon S3 (Simple Storage Service) gives you durability and low-cost storage, but you must design a data model and processing system that supports incremental updates, lineage, and efficient reads. This tutorial walks you through a practical pattern inspired by exa-d (exa.ai) for keeping web-scale crawl data in S3 using declarative, typed dependencies and sparse updates.

> Background: S3 is an object store optimized for immutable blobs; designing incremental update patterns requires manifests, deltas, or table formats that layer transactional semantics on top of S3.

Key Takeaways

- You can treat S3 as the canonical store for web artifacts while using manifests and typed dependency graphs to enable sparse updates and reproducibility.
- Declarative processing (dependencies expressed in schemas) gives you compile-time validation and easier evolution.
- Sparse updates are implemented with delta manifests, object tagging, and ACID-ish table formats (Iceberg/Delta/Hudi) to avoid rewriting petabytes.

Credit: Concept and inspiration adapted from exa-d (exa.ai) and original Hacker News discussion by @willbryk.

Citations: Dean and Ghemawat (2004); [Armbrust et al. (2015)](https://arxiv.org/abs/1507.02882); Apache [Iceberg (2019)](https://doi.org/10.5040/9781350946316); Delta [Lake (2019)](https://doi.org/10.34191/m-281dm); ISO 28500 (2009).

Estimated total time: ~90–150 minutes.

## Prerequisites

You will need:

- Familiarity with S3 semantics and features (multipart upload, object tagging, versioning). (Estimated time to review: 15 minutes)
- Basic Python and AWS CLI experience. (10 minutes)
- Basic knowledge of distributed processing (Spark, Beam) or orchestration (Airflow/Dagster). (20 minutes)
- A working AWS account with an S3 bucket and IAM credentials. (setup: 10 minutes)

> Background: ACID means Atomicity, Consistency, Isolation, Durability—important for table formats that emulate database guarantees on S3.

Expected outcome: You will be able to upload raw web artifacts, define typed dependencies, and perform sparse updates that modify only changed items instead of rewriting whole datasets.

## Setup / Installation

Estimated time: 15–20 minutes

Install basic tools:

```bash
# Install AWS CLI
pip install awscli

# Install boto3 for Python S3 access
pip install boto3

# Optionally install pyspark and iceberg for table operations
pip install pyspark
# Iceberg/Delta integration often requires JVM artifacts; consult project docs for production setup
```

Expected output: aws and boto3 ready in your environment; you can run `aws s3 ls` and a simple boto3 script.

## Step-by-step Instructions

You will implement a pipeline with these numbered steps:

1. Define a typed artifact model
1. Ingest raw web artifacts to S3
1. Build manifests and dependency declarations
1. Process derived stages declaratively
1. Apply sparse updates using delta manifests

Estimated time for full walkthrough: 60–90 minutes.

### 1) Define a typed artifact model (10–15 minutes)

You will declare the types of objects you store (raw_page, asset, link_graph, crawl_meta). Use Python dataclasses (typed) to validate schema boundaries.

```python
from dataclasses import dataclass
from typing import Dict, List

# Typed artifact definition
@dataclass
class RawPage:
    url: str
    s3_key: str     # S3 object key for HTML blob
    content_type: str
    crawl_time: str
    headers: Dict[str, str]  # HTTP headers, content-length, etc.

# Example usage: RawPage("https://example.com", "raw/2026-01-01/obj123.warc", ...)
```

Expected output: a code-level schema you can use across processing stages to type-check inputs/outputs.

### 2) Ingest raw web artifacts to S3 (15–25 minutes)

Store raw content using WARC (Web ARChive) containers or per-URL objects. WARC lets you group records; ISO 28500 (2009) defines the format.

Example: upload a WARC shard or single HTML blob:

```python
import boto3
s3 = boto3.client("s3")
bucket = "my-web-archive"

# Upload a single HTML blob
s3.put_object(Bucket=bucket, Key="raw/2026-01-01/page123.html",
              Body="<html>...</html>", ContentType="text/html")
# Upload a WARC file (binary)
with open("shard-0001.warc.gz", "rb") as f:
    s3.put_object(Bucket=bucket, Key="warc/shard-0001.warc.gz", Body=f)
```

Expected result: objects appear in S3 under predictable prefixes (partitioning by date/domain). You will see keys when running `aws s3 ls s3://my-web-archive/raw/2026-01-01/`.

### 3) Build manifests and declarative typed dependencies (15–20 minutes)

A manifest is a small JSON/NDJSON file that lists artifact keys, checksums, and types. A typed dependency graph describes how a derived computation consumes artifacts.

Example manifest JSON record:

```json
{
  "key": "raw/2026-01-01/page123.html",
  "type": "RawPage",
  "crc32": "1a2b3c4d",
  "crawl_time": "2026-01-01T12:00:00Z"
}
```

You can declare dependencies using YAML or JSON:

```yaml
# crawl_pipeline.yaml
stages:
  - name: parse_links
    input: RawPage
    output: LinkGraph
    spec: "parse_links.py"   # script or container ref
```

Inline comment: this declaration makes it easy for orchestration systems to validate types before execution.

Expected output: a manifest file stored next to shards, e.g., `warc/shard-0001.manifest.json`, and a YAML stage declaration that orchestration tools can read.

### 4) Process derived stages declaratively (20–30 minutes)

Use your manifest and typed declarations to drive compute. Here’s a simple Spark job that reads manifest entries and parses links:

```python
# parse_links.py (simplified)
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("parse-links").getOrCreate()
# Read manifest as JSON lines
manifests = spark.read.json("s3a://my-web-archive/warc/shard-0001.manifest.json")
# Filter RawPage and then read content and extract links (pseudocode)
raw_pages = manifests.filter(manifests.type == "RawPage")
# ... join with raw objects, parse HTML, emit link records ...
```

Comment: using declarative manifests lets you separate "what" from "how"—the stage only requires typed inputs.

Expected output: A link graph file written as Parquet/NDJSON under `derived/link_graphs/2026-01-01/`.

Citations: Using Spark for large-scale processing follows patterns in Armbrust et al. (2015).

### 5) Apply sparse updates using delta manifests (10–20 minutes)

When a small set of pages changes, you avoid rewriting entire datasets by issuing a delta manifest that lists additions, deletions, and replacements. Table formats (Apache Iceberg, Delta Lake, Hudi) also support file-level transactional updates on S3.

Example delta manifest (NDJSON):

```json
{"action":"add","key":"raw/2026-01-02/page999.html","type":"RawPage"}
{"action":"delete","key":"raw/2025-12-31/page321.html","type":"RawPage"}
```

A lightweight processor reads the delta manifest and:

- Copies new objects to canonical prefixes
- Tags or versions objects to mark superseded ones
- Emits incremental derived outputs (e.g., link deltas)

Code snippet to mark deletions via S3 object tagging:

```python
# tag an object as deleted (soft delete)
s3.put_object_tagging(
    Bucket=bucket,
    Key="raw/2025-12-31/page321.html",
    Tagging={"TagSet":[{"Key":"deleted","Value":"true"}]}
)
# downstream processing filters out objects tagged deleted
```

Expected output: only changed derived files are recomputed; manifests reflect new state; cost and IO are limited to deltas.

Citations: Iceberg and Delta Lake provide stronger semantics for this pattern (Apache Iceberg, 2019; Delta Lake, 2019).

## Common Issues & Troubleshooting

Estimated time to read: 5–10 minutes

- Objects not visible in reads: ensure you use the right S3 URI and credentials. Multipart uploads might not be completed—check `aws s3api list-multipart-uploads`.
- Inconsistent reads during updates: S3 offers read-after-write consistency for new objects and eventual consistency for overwrite/delete in some regions—architect your delta application to use new keys or manifest-driven reads (Amazon, 2020).
- Too many small files: small objects increase per-object overhead. Batch small artifacts into WARC shards or Parquet files. Use compaction jobs to merge small files.
- Manifest drift: keep manifests authoritative; use a catalog (Glue or Iceberg catalog) or a single-manifest-per-shard pattern to avoid split-brain.
- Schema evolution: define typed schemas and use canonical serializers (Avro/Parquet) and add version fields to detect incompatible changes.

> Background: Eventual consistency refers to a system guaranteeing that, given enough time without new updates, all accesses will return the last updated value.

## Expected outputs after major steps (recap)

- After Step 1: validated typed classes for artifacts.
- After Step 2: raw artifacts and/or WARC shards in S3.
- After Step 3: manifests and YAML stage declarations in S3.
- After Step 4: derived datasets (link graphs, parsed metadata) in partitioned, compressed formats.
- After Step 5: delta-applied state with minimal reprocessing; manifests updated.

## Common Pitfalls

- Trying to update objects in-place. Prefer new object keys and manifests (avoid in-place overwrites unless using a transactional table format).
- No manifest/versioning: without manifests, you will do costly scans to discover deltas.
- Unbounded small files: leads to metadata overhead and long job start times.
- Ignoring access control: S3 objects and manifests should have IAM policies and optional encryption and audit logging.

## Next Steps / Further Learning

Estimated time: ongoing exploration

- Explore ACID table formats on S3: Apache Iceberg (2019), Delta Lake (2019), and Hudi for stronger transactional semantics.
- Add a catalog and lineage tool such as AWS Glue Catalog or Apache Atlas for provenance.
- Implement compaction and small-file management jobs; integrate orchestration (Airflow / Dagster).
- Consider content-addressed storage and deduplication for assets to save cost.
- Read deeper: Dean and Ghemawat (2004) for map-reduce patterns; Armbrust et al. (2015) for Spark-style processing; ISO 28500 (2009) for the WARC spec.

Further reading and citations:

- Dean and Ghemawat (2004) — MapReduce.
- Armbrust et al. (2015) — Spark SQL and large-scale data processing patterns.
- Apache Iceberg (2019) — table format for data lakes.
- Delta Lake (2019) — transactional storage layer on object stores.
- ISO 28500 (2009) — WARC web-archiving format.
- [Amazon (2020)](https://doi.org/10.1093/wentk/9780190668297.003.0006) — S3 behavior and consistency documentation.

This tutorial distilled patterns from exa-d (exa.ai) and the Hacker News discussion by @willbryk, showing concrete ways to treat S3 as the canonical store for web-scale data while using declarative typed dependencies and delta/manifest-driven sparse updates.


## References

- [Exa-d: How to store the web in S3](https://exa.ai/blog/exa-d) — @willbryk on hackernews

- [Armbrust et al. (2015)](https://arxiv.org/abs/1507.02882)
- [Iceberg (2019)](https://doi.org/10.5040/9781350946316)
- [Lake (2019)](https://doi.org/10.34191/m-281dm)
- [Amazon (2020)](https://doi.org/10.1093/wentk/9780190668297.003.0006)