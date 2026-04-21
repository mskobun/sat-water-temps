// =============================================================================
// Final Report skeleton
// Submission requirements (Moodle, 28 April 2026, 11:59pm):
//   - PDF only, filename: <Student-Name & ID>_Final Report.pdf
//   - Font: Calibri 12
//   - Main body <= 15,000 words AND <= 40 A4 pages
//     (bibliography counts; cover/abstract/TOC and appendices DO NOT count)
//   - Marking: 75% Final Report + 15% Demo Video (+ 10% Interim already done)
//   - Late penalty: 5%/day
// Structure below follows slides 6 and 7 of submission requirements.pptx.
// =============================================================================

#set page(paper: "a4", margin: 2.5cm, numbering: "1")
#set text(size: 12pt, font: "Calibri")
#set par(justify: true, leading: 0.75em)
#show raw: set text(font: "FiraCode Nerd Font", size: 10pt)
#show raw.where(block: true): set par(justify: false)
#set heading(numbering: "1.1")

// -----------------------------------------------------------------------------
// Outer Cover Page -- matches template "Final Report - Outer-Cover format.doc"
// -----------------------------------------------------------------------------
#{
  set page(numbering: none)
  align(center)[
    #image("uon_logo.jpg", width: 6cm)

    #v(0.4cm)
    #text(size: 14pt)[School of Computer and Mathematical Sciences]

    #text(size: 14pt)[Faculty of Science and Engineering]

    #text(size: 14pt)[University of Nottingham Malaysia]

    #v(2.5cm)
    #text(size: 16pt, weight: "bold")[UG FINAL YEAR DISSERTATION REPORT]

    #v(2cm)
    #text(size: 18pt, weight: "bold")[Satellite Water Temperature Web Application
    
    Enhancement]

    #v(2cm)
  ]

  // Student block -- left-aligned rows inside a centred box
  align(center)[
    #block(width: 11cm)[
      #set text(size: 13pt)
      #set par(justify: false)
        Student's name: Maksim Skobun \
        Student Number: 20510325 \
        Supervisor Name: Dr. Tomas Maul \
        Year: 2026
    ]
  ]

  v(1fr)
  align(center)[
    #text(size: 12pt)[SUBMITTED IN PARTIAL FULFILMENT OF THE REQUIREMENTS FOR THE AWARD OF BACHELOR OF SCIENCE IN COMPUTER SCIENCE (HONS)]

    #text(size: 12pt)[THE UNIVERSITY OF NOTTINGHAM]
  ]
  pagebreak()
}

// -----------------------------------------------------------------------------
// Title page -- matches template "Final Report - Title page-format.doc"
// -----------------------------------------------------------------------------
#{
  set page(numbering: none)
  align(center)[
    #image("uon_logo.jpg", width: 6cm)

    #v(3cm)
    #text(size: 20pt, weight: "bold")[Satellite Water Temperature Web Application Enhancement]

    #v(2cm)
    #text(size: 12pt)[Submitted in April 2026, in partial fulfilment of the conditions of the award of the degree B.Sc.]

    #v(1.5cm)
    #text(size: 14pt, weight: "bold")[Maksim Skobun]

    #v(0.4cm)
    #text(size: 12pt)[School of Computer Science]

    #text(size: 12pt)[Faculty of Science and Engineering]

    #text(size: 12pt)[University of Nottingham]

    #text(size: 12pt)[Malaysia]
  ]

  v(1fr)
  set par(justify: false)
  text(size: 12pt)[I hereby declare that this dissertation is all my own work, except as indicated in the text:]

  let underline-box(w) = box(width: w, stroke: (bottom: 0.5pt))

  v(1cm)
  text(size: 12pt)[Signature #underline-box(7cm)]

  v(0.5cm)
  text(size: 12pt)[Date #underline-box(1.5cm) / #underline-box(1.5cm) / #underline-box(2.5cm)]
  v(2cm)
  pagebreak()
}

// -----------------------------------------------------------------------------
// Abstract
// -----------------------------------------------------------------------------
#heading(numbering: none)[Abstract]

Surface water temperature is a useful indicator for aquatic ecosystems, water quality, and climate-related change. A previous final-year project produced a web application that visualised temperature data for reservoirs and downstream rivers in Southeast Asia, but its deployment model and retrieval workflow limited continued operation: paid hosting cost roughly \$30 per month, updates depended on a manually run script, and the interface allowed limited exploration of the data.

This dissertation replatforms and extends the system end-to-end. The backend was rebuilt as a serverless pipeline on Cloudflare (Pages, D1, R2) and AWS (Lambda, SQS), deployed reproducibly through Terraform, and reworked to ingest data directly from NASA Earthdata and USGS STAC rather than through the legacy AppEEARS service. The ingestion pipeline was automated and extended to integrate Landsat 8/9 alongside ECOSTRESS. The frontend was rewritten in SvelteKit to expose source toggling, thresholding, and per-pixel inspection, alongside an administrative interface for on-demand backfills and job monitoring.

The resulting system runs within free-tier limits across all providers, with the only recurring charge being approximately \$0.03 per month for ECR image storage. Users can hover any pixel to see its exact temperature, right-click to pull its full time series across both sensors, and filter by temperature threshold, all directly in the browser.
#pagebreak()

// -----------------------------------------------------------------------------
// Table of contents
// -----------------------------------------------------------------------------
#outline(depth: 3, indent: auto)
#pagebreak()

// =============================================================================
// 1. Introduction  (carried over from interim §Introduction, past-tense framing)
// =============================================================================
= Introduction
Surface water temperature influences aquatic ecosystems, water quality, and climate-related processes @usgs-do-water @reservoir-do-warming. The existing Satellite Water Temperature Web Application, developed under a previous SEGP project @segp, was designed to visualise near-real-time temperature data derived primarily from NASA's ECOSTRESS sensor @ecostress. This system enabled users to explore spatial and temporal variations in reservoir and downstream river temperatures.

While the original system demonstrated feasibility, its operational model limited continued use. Data retrieval remained manual and slow, recurring hosting costs were significant for a student project, and the interface supported only limited exploration @segp. The immediate priority of this project was therefore to make the platform sustainable and automated before extending it with multi-sensor integration and richer visualisation.

== Aims
The overall aim of the project was to transform the legacy Satellite Water Temperature Web Application from a costly, manually-operated proof-of-concept into a sustainable, automated, multi-sensor observation platform. Concretely, this required replatforming the system onto free-tier cloud infrastructure, automating the satellite data ingestion pipeline, integrating a second independent sensor family (Landsat) alongside the existing ECOSTRESS one, and replacing the static, server-rendered frontend with an interactive, client-side visualisation that exposes the pixel-level data directly to the user.

== Objectives
The project proposal set six objectives. Their delivery status at the time of writing is summarised below.

#figure(
  table(
    columns: (auto, auto),
    table.header([*Objective*], [*Status*]),
    [O1: Data storage & retrieval optimisation], "Delivered",
    [O2: Sentinel-2 water-mask verification], "Descoped",
    [O3: Enhanced visualisation features], "Delivered",
    [O4: Multi-platform satellite integration], "Delivered",
    [O5: Zone differentiation], "Descoped",
    [O6: Code maintainability & documentation], "Delivered",
  ),
  caption: [Delivery status of the six project objectives]
) <objectives-status>

Two objectives were descoped during the project. O2 (Sentinel-2 water-mask verification) was dropped because both sensor pipelines already apply per-pixel quality filtering through their own bitmask rasters (the ECOSTRESS `QC` band and the Landsat `QA_PIXEL` band), making a separate Sentinel-2 verification stage redundant. O5 (zone differentiation) was dropped after stakeholders ranked multi-sensor coverage above intra-feature zoning; the scope freed by removing O5 was reallocated to the Landsat integration (O4). The remaining four objectives were delivered in full, as detailed in the implementation sections below.


// =============================================================================
// 2. Motivation  (carried over from interim §Motivation)
// =============================================================================
= Motivation <motivation>

== Cost Reduction
A limitation of the original system was hosting cost. The backend was hosted on Heroku; Heroku's Eco dyno plan is listed at \$5 per month for 1,000 dyno hours @heroku-pricing. Data was stored on Supabase, whose Pro plan includes 100 GB of storage and starts from a \$25 monthly plan; this was the tier assumed once the legacy system exceeded the 1 GB free storage allowance @supabase-pricing. Stakeholders identified recurring cost as a barrier to keeping the project running after handover. A student-originated project cannot realistically sustain a \$30 per month bill indefinitely, making cost reduction a prerequisite for continued operation rather than a convenience.

== Data Retrieval Automation
The original system relied on a script that had to be run manually to retrieve temperature data from AppEEARS (Application for Extracting and Exploring Analysis Ready Samples) @appeears, NASA's web service for accessing remote sensing data including ECOSTRESS. In project use, the script took hours to run even for a single day of data, and every parameter change (dates, feature set, output format) required editing the script @segp.

== Single-Sensor Coverage
The legacy system relied on ECOSTRESS alone. Because ECOSTRESS flies on the ISS, it passes over the same location at irregular times @ecostress-orbit, leaving unpredictable gaps in the record. A second sensor with a fixed, repeating schedule was needed to produce a reliable time series. These gaps in the thermal record make it difficult for reservoir operators or researchers to identify temperature trends or anomalies with confidence, as a single missing observation at a critical time (during a heat event or monsoon transition) cannot be retrospectively recovered.

== Lack of Client-Side Interactivity
The legacy frontend was rendered as static HTML from Flask templates and offered two main controls: a date selector and colour mode @segp. It displayed a satellite map with a temperature image overlay and a histogram, but did not expose the underlying pixel records in the browser. As a result, users could not inspect an individual pixel, filter pixels by value, compare two dates interactively, or query a time series for a fixed point on the map. Researchers needed to query individual pixels and their time series directly (for example, to detect the onset of thermal stratification or early indicators of algal bloom conditions), which required pixel-level access that the legacy interface did not provide.

== Code Quality and Reproducibility
The original system was written in Python with hardcoded file paths and parameters, limited documentation, and manually created cloud resources @segp. These choices made the system difficult to reconfigure and meant the deployed environment could not be rebuilt completely from source.

== Scientific and Stakeholder Motivation
Surface water temperature governs dissolved oxygen availability, stratification, algal bloom risk, and the thermal envelope tolerated by aquatic life @usgs-do-water @reservoir-do-warming @hab-inland-waters. In Southeast Asia, large reservoirs also regulate hydropower and irrigation, so climate-driven thermal change has direct economic consequences @mekong-climate-hydropower. The intended users (environmental researchers, reservoir operators, and academic supervisors) need dense, validated time series at low recurring cost, which the original system failed to provide.

// =============================================================================
// 3. Related Work
// =============================================================================
= Related Work <related-work>

== Analysis of the Existing System
The primary point of reference is the system developed by the previous SEGP team @segp. Its importance in this dissertation is that it established the feasibility of a web application for browsing reservoir temperature data and provided the baseline from which the current redesign departs. The operational shortcomings that motivated redevelopment are summarised in @motivation; for related-work purposes, the key point is that the earlier system solved the initial proof-of-concept problem but not the longer-term problem of low-cost, automated, maintainable operation.

== Remote Sensing of Water Surface Temperature
Two sensor families are directly relevant to this project: ECOSTRESS and Landsat. ECOSTRESS (ECOsystem Spaceborne Thermal Radiometer Experiment on Space Station) is a thermal-infrared imager mounted on the ISS; the ECO_L2T_LSTE v002 tiled product is distributed as 70 m UTM tiles in Cloud-Optimised GeoTIFF format @ecostress-l2t @cog-spec. Because the ISS orbit captures the same areas at varying times of day @ecostress-orbit, ECOSTRESS is useful for diurnal observations but does not provide the regular, predictable overpass schedule of a sun-synchronous platform.

Landsat 8 and Landsat 9 carry the Thermal Infrared Sensor (TIRS), whose thermal band is distributed by the USGS as the Collection 2 Level-2 Surface Temperature product (`ST_B10`) @landsat-c2-st. Each satellite images the Earth every 16 days, with Landsat 8 and 9 offset by eight days @landsat-acquisition. This gives the project a more regular second source alongside ECOSTRESS. Both sensor families are catalogued through the SpatioTemporal Asset Catalog (STAC) specification @stac-spec, which standardises discovery of cloud-hosted geospatial data and is the mechanism used to locate granules without bulk download.

Both products expose per-pixel quality information as bitmask rasters: ECOSTRESS ships a dedicated `QC` raster encoding mandatory QA and data-quality flags, whose bit layout is fixed by the Product Specification Document @ecostress-psd, and Landsat ships a `QA_PIXEL` raster encoding cloud, cloud-shadow, snow/ice, and water bits derived from CFMask @landsat-c2-st. This project decodes those bitmasks in the processor so the filtering rule is explicit in source code rather than hidden in a precomputed mask.

For water extent, the Sentinel-2 optical mission and derived indices such as NDWI @ndwi, as well as model-based approaches like GAM4Water @gam4water, can be used to validate and correct water masks supplied inside thermal products. In this project, water extent is instead taken from each sensor's own QA layer (the ECOSTRESS `water` band and Landsat `QA_PIXEL` bit 7), because the dedicated Sentinel-2 verification path was descoped.

== Evaluation of Serverless Architecture
Traditional Virtual Private Servers (VPS) or Platform as a Service (PaaS) solutions like Heroku charge for reserved compute capacity, resulting in idle costs even though the system is not processing data or serving users. Adzic and Chatley (2017) demonstrate that for sporadic workloads, migrating to a serverless model can significantly reduce operational costs by minimising idle resource billing @serverless-compiuting. The "Function-as-a-Service" (FaaS) model allows the system to scale up when processing new batches of data, as well as scale to zero when not serving any users, ensuring the project operates entirely within free-tier limits.

Two distinct FaaS models are relevant to this project. Cloudflare Workers @cloudflare-workers runs JavaScript in lightweight V8 isolates (the same technology used inside Chrome), distributed across Cloudflare's global network. Isolates start in under a millisecond, but the execution environment is intentionally constrained: no arbitrary binaries, no filesystem, and a strict CPU-time cap per request. AWS Lambda @aws-lambda takes a different approach, running each function inside a full container image of up to 10 GB, supporting any language or binary dependency, with execution times of up to 15 minutes @aws-lambda-quotas. The cost of this flexibility is a cold-start latency of up to several seconds when a new container must be initialised. Both models bill only for actual execution time, with no charge when idle.

FaaS functions are commonly paired with a message queue to implement a fan-out pattern: a single trigger publishes one message per unit of work, and the FaaS platform invokes a separate function instance for each message in parallel. Amazon SQS (Simple Queue Service) @aws-sqs-pricing is a managed queue service that integrates natively with Lambda for this purpose, decoupling the trigger from the workers and allowing the processing throughput to scale with the number of messages rather than being bound to a single invocation.

Two alternative processing strategies were considered and rejected. Batch processing frameworks such as AWS Batch @aws-batch or Apache Spark are well suited to long-running, resource-intensive jobs over large static datasets, but they require a persistent job scheduler or cluster that incurs idle cost and does not scale to zero. Stream processing systems such as Apache Kafka or AWS Kinesis @aws-kinesis are designed for continuous, low-latency event ingestion and are appropriate when new data arrives at high and unpredictable rates. Satellite acquisitions, however, are scheduled and infrequent: ECOSTRESS and Landsat each produce a small number of scenes per day per region, and processing need only occur once per scene. The FaaS model fits this workload more naturally than either alternative, as it incurs no cost between runs, scales out automatically to parallelise per-scene work, and requires no infrastructure management beyond the function definition.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    table.header([*Property*], [*Batch (AWS Batch / Spark)*], [*Stream (Kafka / Kinesis)*], [*FaaS (Lambda + SQS)*]),
    "Idle cost", "Cluster provisioning cost", "Broker always running", "Zero",
    "Latency to first result", "Minutes (cluster startup)", "Seconds", "Seconds–minutes",
    "Scales to zero", "No", "No", "Yes",
    "Suited to workload", "Large static datasets", "Continuous high-rate streams", "Infrequent bursts",
    "Free-tier compatible", "No", "No", "Yes",
  ),
  caption: [Comparison of data processing strategies for intermittent satellite ingestion workloads.]
) <processing-strategies>

== Infrastructure as Code
When infrastructure is configured manually through web consoles, the live environment gradually diverges from what anyone intended or documented, making it difficult to reproduce or recover from failures @infra-as-code. Infrastructure as Code (IaC) solves this by treating infrastructure configuration as source code: checked into version control, reviewed, and applied automatically. Terraform is the widely-used IaC tool that supports both AWS and Cloudflare, allowing an entire stack to be defined, versioned, and redeployed from a single configuration @terraform.

== Web Mapping and Visualisation Frameworks
Interactive web mapping libraries such as Leaflet @leaflet and MapLibre GL @maplibre allow developers to place georeferenced layers over a basemap in the browser. Traditional approaches rely on pre-rendered raster overlays (server-generated image tiles that convey spatial patterns visually but expose no queryable per-pixel state to the user). For applications that need users to inspect, filter, or query individual data points directly on the map, raster overlays are insufficient.

deck.gl @deckgl is a WebGL-powered overlay framework designed for large-scale data visualisation on top of basemap libraries. By uploading geometry and attribute data to the GPU as typed arrays, it can render and recolour hundreds of thousands of individually addressable objects at interactive frame rates, and exposes per-object picking so that hover and click events carry data attributes. The Mapbox Vector Tile (MVT) format @mvt-spec is an alternative approach that encodes vector geometry in a binary tile grid; MapLibre can decode and render MVT layers natively, supporting per-feature styling and interaction at the cost of a tile-encoding step on the data producer side.

== Client-Side Analytical Engines
Apache Parquet @parquet-spec is a columnar binary file format designed for efficient analytical reads. Unlike row-oriented formats such as CSV, Parquet stores each column contiguously, which allows repeated values (such as longitude and latitude coordinates that recur across many observations) to compress heavily. Parquet files are subdivided into row groups, each with embedded min/max statistics that query engines can use to skip groups that do not match a filter, reducing the amount of data that must be downloaded.

A more recent development in browser-based data tooling is the appearance of columnar query engines compiled to WebAssembly. DuckDB-Wasm @duckdb-wasm can run SQL in the browser and read Parquet files directly from a URL over HTTP range requests, fetching only the row groups it needs rather than the whole file. This enables analytical queries over large datasets entirely on the client, without a server-side query endpoint.

// =============================================================================
// 4. Description of the Work  (NEW -- required by rubric, not in interim)
// =============================================================================
= Description of the Work <description>

== Functional Specification
*Public (unauthenticated) users* can:

- Browse an interactive map of all monitored water bodies rendered over satellite imagery.
- Select a feature to view its most recent temperature data as an interactive overlay.
- Hover any pixel to see its temperature in Kelvin, Celsius, or Fahrenheit.
- Click a pixel to open its full temperature history across all available dates.
- Toggle between ECOSTRESS and Landsat sources.
- Filter pixels by a temperature threshold.
- Switch between relative, fixed, and grayscale colour palettes.
- Download the raw CSV, GeoTIFF, or Parquet file for any observation.

*Administrative users* additionally have access to:

- A job dashboard showing every processing run with its duration, status, and per-criterion rejection statistics.
- A backfill interface for triggering on-demand ingestion for arbitrary date ranges on either sensor.
- A feature overview page grouping jobs by water body.
- A settings page for tuning data ingestion parameters.

== Non-Functional Requirements

- *Cost:* the system must run with no recurring cloud charges beyond negligible storage fees.
- *Reproducibility:* the system must be fully rebuildable from source by a new developer without manual environment setup or undocumented steps.
- *Observability:* administrators must be able to monitor pipeline health and diagnose failures.
- *Automation:* no manual step required for routine daily operation.
- *Processing throughput:* a full daily run across all monitored features must complete within 15 minutes of the scheduled trigger firing.
- *UI responsiveness:* per-pixel overlay rendering and threshold filtering must complete within one second of user interaction once observation data is loaded in the browser.

== User Roles
*Public viewers* have unrestricted access to all visualisation and download functionality. *Administrators* additionally access the management and backfill pages, which must be protected by authentication; unauthenticated requests must be redirected to a login page. Administrator accounts are invite-only and not open to self-registration.

// =============================================================================
// 5. Methodology
// =============================================================================
= Methodology <methodology>

== Development Methodology
Source code was managed with Git and hosted on GitHub. Most changes were committed directly to the main branch in small, self-contained increments; larger features were developed on short-lived branches before merging. A GitHub Actions workflow automatically deployed each commit to the live environment (described in @cd-pipeline), so the deployed system was always up to date.

Weekly progress emails were sent on the author's own initiative to the supervisor and external stakeholders throughout the project. Each email covered what was completed that week, the plan for the following week, and any questions. This kept stakeholders aligned with the project's direction and avoided late-stage requirement mismatches.

Key decisions were shared before being acted on: the Landsat integration was proposed to stakeholders in March 2026 before the implementation work began; in the final phase, stakeholder feedback directed effort towards more accurate water detection rather than adding new features. 

== Technology Selection

=== Satellite Data Sources
ECOSTRESS was inherited from the legacy system as the baseline sensor: the ECO_L2T_LSTE v002 tiled product provides 70m UTM tiles @ecostress-l2t, and the ISS orbit gives observations at different times of day @ecostress-orbit. The limitation for this application is that its revisit rhythm is irregular compared with a sun-synchronous satellite.

Landsat 8/9 Collection 2 Level-2 Surface Temperature was chosen as the second sensor for three reasons. First, its thermal surface-temperature product is freely distributed by USGS @landsat-c2-st. Second, Landsat 8 and 9 are offset by eight days while each satellite repeats every 16 days @landsat-acquisition, giving a regular acquisition schedule that complements ECOSTRESS. Third, the no-cost data policy is compatible with the project's cost constraint.

MODIS @modis-lst was evaluated and rejected on resolution grounds: its 1 km thermal pixels are too coarse to resolve the reservoirs of interest, most of which are only a few kilometres across.

=== Data Access Strategy
The key methodological choice for data access was whether to keep the legacy AppEEARS-mediated workflow or move to direct catalogue-driven access (as discussed in @motivation). Direct access to cloud-hosted Cloud-Optimised GeoTIFFs (COGs) @cog-spec better matched the project's goals of predictable scheduling, lower orchestration complexity, and faster recovery from failed runs.

Both NASA and USGS publish their data through STAC (SpatioTemporal Asset Catalog) @stac-spec, a standard web API for discovering geospatial datasets by location and time. For ECOSTRESS, the `earthaccess` library @earthaccess queries the NASA CMR-STAC index for granules intersecting each polygon. For Landsat, `pystac-client` @pystac-client queries the USGS STAC server. In both cases the returned items carry HTTP/S3 links that `rasterio` @rasterio can query directly with range requests.

Critically, both catalogues are stored on AWS S3 in `us-west-2` region, a fact that directly informed the compute platform choice described in @data-processing-pipeline.

=== Storage
Temperature data is stored as files (CSVs, GeoTIFFs, Parquet), which are too large and numerous to fit in a relational database. S3-compatible object storage is the natural fit: it handles arbitrary file sizes, is accessed via a widely supported standard API, and makes switching providers straightforward if pricing changes. Among S3-compatible options, Cloudflare R2 was selected because its free tier includes 10 GB-month of storage and charges no egress fees @cloudflare-r2-pricing, undercutting both AWS S3 @aws-s3-pricing and Supabase Storage @supabase-pricing on cost, as shown in @storage-comparison.

#figure(
  [#table(columns: 4, table.header([*Feature*], "Supabase Storage", [AWS S3 (`us-east-1` Region)], "Cloudflare R2"),
  "Free Tier Limit", "1 GB", "5 GB (for 12 months only)", "10 GB",
  "Monthly Storage Cost (over limit)", "$0.021/GB", "$0.023/GB (First 50TB)", "$0.015/GB",
  "Egress Fees", "$0.03/GB (over limit)", "$0.09/GB (over limit)", "Not Charged",
  "Minimum Monthly Spend", "$25 (over 1 GB)", "Pay-as-you-go", "Pay-as-you-go")],
  caption: [Comparison of S3-compatible storage services (USD), based on published provider pricing @supabase-pricing @cloudflare-r2-pricing @aws-s3-pricing]
) <storage-comparison>

Alongside object storage, the system needs a relational database for metadata such as observation dates, file paths, job logs, and settings. Cloudflare D1 was selected for this role. Its free tier includes 5 GB of storage and 25 million row reads per day @cloudflare-d1-pricing, which is well in excess of the project's needs.

=== Data Processing Pipeline <data-processing-pipeline>
As established above, both ECOSTRESS and Landsat data live on AWS S3 in `us-west-2`, and each scene requires dozens of range reads against large COG files. Running the processor outside AWS would incur egress fees on every invocation; running it in the same region eliminates them entirely.

Within AWS, Lambda @aws-lambda was chosen over a persistent server such as EC2 because the workload is intermittent: processing runs once per day in a short burst, so paying for a continuously running instance would be wasteful. Lambda charges only for actual execution time, accepts container images up to 10 GB, and allows up to 15 minutes per invocation @aws-lambda-quotas which is sufficient for the heavy geospatial processing involved. Its free tier covers one million requests and 400,000 GB-seconds of compute per month @aws-lambda-pricing, which is sufficient for the project's needs. The only recurring cost is ECR image storage, discussed in @cost-summary.

Lambda is paired with Amazon SQS to fan out each daily trigger into one message per scene. Lambda scales out automatically to process all scenes in parallel, and since the free tier is measured in total invocation-seconds rather than wall-clock time, parallel execution costs no more than sequential.

=== Frontend/API Ecosystem
Once R2 and D1 were chosen for storage, the hosting platform followed directly. Cloudflare Pages was chosen as it runs on the same network as R2 and D1, accessing them with minimal latency. Its free tier includes 100,000 requests per day @cloudflare-workers-pricing, which is sufficient for serving the frontend and API endpoints; the paid plan at US\$5/month is more economical than competitors such as Vercel @vercel-pricing or Netlify @netlify-pricing if the limit were ever exceeded.

With Cloudflare Pages chosen, SvelteKit @sveltekit was selected as the frontend framework: it is a popular framework with an officially maintained Cloudflare adapter, and the author had prior experience with it.

=== DevOps and Infrastructure Strategy
To ensure the deployed environment could be reproduced from source, the project adopted an Infrastructure as Code (IaC) methodology. Terraform was chosen because its provider ecosystem covers both AWS and Cloudflare, allowing the entire stack to be defined in one configuration language @terraform. A GitHub Actions pipeline applies Terraform changes and deploys the frontend on every commit to the main branch.

// =============================================================================
// 6. Design
// =============================================================================
= Design <design>

== High-Level Overview
The system architecture is divided into two zones. The Cloudflare zone hosts the frontend, the admin-facing API, and the persistence layer, and handles all synchronous user requests by reading from D1 and R2. The AWS zone hosts the data acquisition and processing pipeline, which is driven by scheduled daily triggers as well as admin-initiated triggers, and asynchronously populates the storage layer that Cloudflare then serves. Two scheduled initiator Lambdas, one for ECOSTRESS and one for Landsat, query the respective STAC catalogues, fan out one SQS message per scene, and a single processor Lambda consumes those messages and writes the processed outputs to R2 and D1.

#figure(
  image("High Level Overview.png", width: 100%),
  caption: [High-level system architecture. The AWS zone performs scheduled and on-demand ingestion; the Cloudflare zone serves the frontend from D1 + R2.]
) <high-level>

== Data Storage
The system uses Cloudflare R2 object storage and the D1 SQL database together.

*D1* stores structured metadata that needs to be queried and filtered:
- Feature metadata: water-body names, polygon identifiers, latest observation date.
- Per-observation summary statistics: min/max/mean/median/std temperature, pixel counts, per-flag rejection counts.
- Scene-level raster geometry: CRS, affine transform coefficients, pixel size.
- Job records: timestamps, duration, status, error message.
- Application settings.

*R2* stores the bulk per-pixel outputs for each observation:
- GeoTIFF raster.
- Gzipped CSV of per-pixel readings.
- PNG visualisations.
- Parquet file per feature per year.


#figure(
  image("DB Schema.png", width: 100%),
  caption: [D1 database schema. Only columns referenced in the report prose are shown.]
) <db-schema>

== Ingestion Pipeline
Both sensors share the same three-stage pipeline structure: a daily trigger, a STAC search and SQS fan-out, and parallel per-scene processing by a shared processor Lambda.

1. *Daily Trigger*. A CloudWatch Event Rule fires each initiator Lambda once per day. Each is also invocable on demand by an administrator with an optional feature filter and date range.

2. *STAC Search and Enqueue*. The initiator queries the sensor's STAC catalogue for scenes intersecting each monitored polygon within the date window, then sends one SQS message per (feature, date) scene to the shared processor queue.

3. *Parallel Processing*. The shared processor Lambda consumes the queue, applies the quality filter stack (described in @quality-control), and writes the following outputs to R2 for every feature processed: a GeoTIFF, CSV, PNG visualisations, a Parquet file (per year). It also records metadata and filter statistics in D1.

#figure(
  image("EcoStress Updater Flow.png", width: 100%),
  caption: [Pipeline structure shared by both sensors: daily trigger, STAC-driven fan-out, and per-scene processing by a shared processor Lambda.]
) <updater-design>

== Frontend Design
The frontend is divided into three areas: the public map, a historical archive and public dashboard, and the administrative area restricted to authenticated users.

The public map is the primary interface. It renders satellite imagery as a basemap with monitored water bodies drawn as vector polygons. Selecting a water body loads its most recent temperature observation as a per-pixel colour overlay. Users can hover any pixel to see its exact temperature, right-click to open its full point history across all dates and sensors, drag a threshold slider to filter pixels by temperature, switch between ECOSTRESS and Landsat, and choose between relative, fixed and grayscale colour palettes. Keyboard shortcuts are supported throughout: Escape closes the sidebar, arrow keys pan the map.

The administrative area gives pipeline operators visibility into system health without requiring access to AWS or Cloudflare consoles. It surfaces job status, per-scene filter statistics, per-water-body failure summaries, and a backfill interface for triggering on-demand ingestion.

All UI components are built with shadcn-svelte @shadcn-svelte, giving a consistent, accessible component library with automatic dark and light mode based on the user's system preference. The interface is fully responsive and usable on both desktop and mobile screen sizes.

// =============================================================================
// 7. Implementation
// =============================================================================
= Implementation <implementation>
The final system combines a TypeScript SvelteKit frontend and API on Cloudflare Pages @sveltekit, Cloudflare D1 and R2 for storage, Python 3.12 AWS Lambda functions for ingestion and raster processing, Terraform-managed infrastructure @terraform, and GitHub Actions for deployment.

== Implementation Overview
The implementation is split across two execution environments. The interactive application and lightweight API routes run close to the user on Cloudflare, where D1 provides low-latency metadata queries and R2 serves large binary objects. The heavier geospatial processing runs on AWS Lambda, where raster clipping, quality filtering, and artifact generation can scale independently of frontend traffic. This split was chosen because the read path and the write path have different requirements: the read path benefits from edge delivery and cheap object access, while the write path needs Python geospatial libraries such as `rasterio`, `shapely`, and `pyarrow`, which are more naturally packaged in a Linux container image.

The Lambda side is therefore deployed as a container image rather than as a zipped function package. This avoids repeated dependency workarounds for native libraries and allows the same image to expose multiple entry points: ECOSTRESS initiator, Landsat initiator, and the shared processor. The result is a single deployable processing runtime with different commands configured per Lambda function.

== Serverless Data Pipeline
=== Direct STAC/COG ingestion
Both ingestion paths begin with a small initiator Lambda that performs catalogue search and queue fan-out, but the two sensors differ in the catalogue client used. The ECOSTRESS initiator uses `earthaccess` @earthaccess against NASA's CMR-STAC endpoint, while the Landsat initiator uses `pystac-client` @pystac-client against the USGS Landsat STAC service. In both cases the initiator iterates over the monitored polygons, queries scenes intersecting the polygon bounding box within the requested date range, groups matching assets by feature and date, and enqueues one SQS message per candidate observation.

This design replaced the AppEEARS submission workflow described in @motivation, removing the long wait between request creation and data availability. The processor reads sensor assets directly as Cloud Optimized GeoTIFFs @stac-spec @cog-spec, so there is no separate manifest-processing phase and no dependency on a NASA-side batching service. Manual backfills use the same mechanism: the administrative UI records a request in D1 and then triggers the same initiator Lambda with a user-supplied date range.

=== Shared queue-driven processing
All scene-level work is handled by a single SQS-triggered processor Lambda. The queue message declares the source sensor, and the top-level router dispatches the message to the matching processor implementation. This preserved one horizontal scaling mechanism while still allowing source-specific filtering logic.

Within the processor, the implementation pattern is the same for both sensors. The processor opens the required COG bands, clips them to the feature polygon, mosaics multiple overlapping scenes when necessary, applies source-specific quality filtering, and then writes four output forms for each successful observation: a filtered GeoTIFF, a gzipped CSV, three preview PNGs, and an appended Parquet shard. Summary statistics and object paths are then inserted into D1. If a scene overlaps the polygon but yields no valid pixels after filtering, the job is marked as `nodata` rather than as a processing failure so that operators can distinguish "no usable observation" from "broken pipeline execution".

=== Sensor-specific quality filtering <quality-control>
The main implementation difference between the two sources lies in how valid pixels are defined. ECOSTRESS uses a combination of the `QC`, `cloud`, and `water` bands. The processor rejects pixels with failing mandatory QA or data-quality bits, rejects cloudy pixels, rejects non-water pixels when the water mask is present, and then applies two source-independent sanity checks: a physical temperature range filter and a 5×5 Hampel-style spatial outlier filter. Landsat follows the same final two checks, but derives its initial mask from the `QA_PIXEL` bitfield: fill pixels, dilated cloud, cloud shadow, and non-water pixels are removed before the common outlier checks are applied.

The filter results are recorded as a per-pixel bit-flag raster and then summarised into a histogram stored in `temperature_metadata.filter_stats`. This gives the administrative dashboard a direct explanation layer instead of just a binary success/failure outcome.

#figure(
  table(
    columns: (auto, auto, auto),
    table.header([*Bit*], [*Meaning*], [*Applied from*]),
    "0", "Sensor quality-control rejection", "ECOSTRESS QC checks; Landsat invalid/fill state",
    "1", "Cloud rejection", "ECOSTRESS cloud band; Landsat QA_PIXEL cloud bits",
    "2", "Non-water rejection", "Sensor-native water mask",
    "3", "No-data / swath-gap rejection", "Missing or zero-valued raster cells",
    "4", "Out-of-range temperature rejection", "Shared physical range check",
    "5", "Spatial outlier rejection", "Shared Hampel neighbourhood test",
  ),
  caption: [Per-pixel filter flags recorded for each processed observation and summarised into `filter_stats`.]
) <processor-code-filter>

== Storage and Data Delivery
=== Hybrid D1 and R2 storage
The hybrid storage implementation follows the separation introduced in the design chapter: D1 stores only query-oriented metadata, while R2 stores all bulk observation artifacts. D1 therefore contains the `features` table, the `temperature_metadata` table, the `processing_jobs` table, application settings, and the unified `data_requests` table used by scheduled and manual ingestion. For each observation, the metadata row stores summary temperatures, valid-pixel counts, filter histograms, source identifier, pixel size, source CRS, affine transform coefficients, and the R2 keys of the CSV, GeoTIFF, PNG, and Parquet artifacts. This metadata-first design keeps D1 small enough for frequent read queries while still allowing the browser and the admin UI to discover the required objects efficiently.

R2 stores the heavier outputs because these files grow with feature size and observation count. Using object storage for the read-mostly bulk layer also simplified download features such as archive ZIP generation and Parquet range requests. The implementation therefore treats D1 as an index over the archive rather than as the archive itself.

=== Columnar temperature storage
The most important storage change in the final implementation is the move from CSV-only archival data to year-sharded Parquet. Each processor still writes a CSV for compatibility, but it also appends valid pixels to a per-feature Parquet file whose actual object key is suffixed by year. The append function downloads the current year shard if it exists, removes any rows for the same observation date, concatenates the old and new data, sorts by longitude and latitude, and writes the combined table back with Zstandard compression.

Parquet was chosen because it addresses two different implementation goals at once. First, it gives much better compression than repeatedly storing the same coordinate columns in plain CSV. Second, it can be queried directly in the browser through DuckDB-WASM @duckdb-wasm without a new server-side time-series API. The yearly sharding is a practical compromise: combining all dates for a feature would maximise compression but produce files that grow without bound, whereas sharding by individual date would fragment the archive and increase request overhead. In testing on the largest monitored features, annual shards remained small enough to download and query interactively while still benefiting from columnar compression.

The public Parquet endpoint was implemented with HTTP range support so that browser-side DuckDB can issue efficient partial reads against R2 rather than always downloading the full file. Logical file registration is cached per source in the frontend to avoid repeatedly mounting the same Parquet objects in the DuckDB virtual file system during normal map use.

=== Derived artifacts and compatibility path
The GeoTIFF output is retained as the highest-fidelity processed raster and is primarily useful for research export and downstream GIS inspection. The PNG outputs are a separate optimisation for the web application: they serve as thumbnails and provide an immediate preview image while the browser prepares the vector-based temperature overlay. Gzipped CSV files remain in the archive for backwards compatibility with the legacy system and for straightforward tabular export. A clear future improvement would be to generate CSV downloads from Parquet on demand and eventually remove the redundant CSV write path.

== Public Web Application
=== Interactive map and overlay rendering
The public interface is built around MapLibre GL JS @maplibre rather than the Leaflet-based legacy map. The deciding factor was not just aesthetics but rendering strategy: the final system needed to combine polygon overlays, basemap tiles, raster preview images, and eventually a large number of per-pixel cells. A WebGL-first map stack is better suited to this than a DOM-heavy 2D map. The basemap uses Esri World Imagery tiles, while monitored water bodies are loaded from the shared polygon GeoJSON and rendered as vector layers on top.

When a feature is selected, the page first displays the pre-generated PNG overlay for immediate feedback, then fetches metadata for the chosen observation, loads the corresponding Parquet shard, and finally replaces the preview with a deck.gl `SolidPolygonLayer` @deckgl. The overlay is coloured either relative to the observation's own temperature range or against a fixed global range, and the same layer handles hover tooltips and click selection. This implementation avoids trying to stream hundreds of thousands of individual DOM markers or SVG elements. On the largest features, the deck.gl path can still render and filter the full observation interactively.

#figure(
  image("map-interface.png", width: 100%),
  caption: [Public map interface with a selected water body, rendered temperature overlay, hover tooltip, and feature sidebar controls.]
) <map-interface>

=== Browser-side point-history queries
The feature sidebar and point-history panel are implemented around the same Parquet archive rather than around a dedicated server endpoint per query. Once the relevant Parquet shards are available, DuckDB-WASM runs entirely in the browser and retrieves the time series of the nearest pixel to the selected map point. For Landsat and ECOSTRESS observations stored in projected CRSs, the frontend also uses the stored raster row, column, CRS, and affine transform to reconstruct the exact pixel footprint and highlight it on the map when the user hovers the history table.

This approach moved an otherwise expensive read pattern out of the backend and made the interface more responsive after the initial file fetch. It did, however, create one implementation constraint: DuckDB-WASM binaries are large, and bundling them directly into the SvelteKit output would put pressure on Cloudflare Pages file-size limits @cloudflare-pages-limits. The final implementation therefore loads the WASM assets from a CDN at runtime instead of shipping them as ordinary application bundle files.

#figure(
  image("point-history.png", width: 68%),
  caption: [Point-history panel showing the nearest-pixel time series together with the synchronised map highlight for the selected location.]
) <point-history>

=== Historical archive and public dashboard
The archive page exposes the observation history of a single feature as a table of available dates, sources, and downloadable artifacts. Users can download selected CSV files as a ZIP archive or fetch the available Parquet shard or shards directly. The dashboard page provides a cross-feature overview instead: latest observation date, latest mean temperature, sparkline trend, source badge, freshness indicator, and links back to both the map and the archive. This pair of pages was implemented to separate two different use cases: exploratory browsing of the whole estate and targeted extraction of the raw or semi-raw outputs for a single feature.

#figure(
  image("historical-archive.png", width: 100%),
  caption: [Historical archive page listing observations and downloadable artifacts for a selected water body.]
) <historical-archive>

#figure(
  image("public-dashboard.png", width: 100%),
  caption: [Public dashboard summarising the latest observation date, recent trend, and temperature status across monitored water bodies.]
) <public-dashboard>

== Administrative Tooling
=== Authentication and protected routes
The administrative area is protected with Auth.js @authjs using AWS Cognito @cognito as the identity provider. Cognito handles the hosted login flow and token issuance, while the SvelteKit server hook applies route-level protection to `/admin/*` pages and `/api/admin/*` endpoints. Unauthenticated page requests are redirected to `/admin/login`, and unauthenticated API requests receive a `401` response. This keeps the operational tooling behind an ordinary web login without requiring administrators to access the AWS Console or Cloudflare dashboard directly.

=== Security model
The system applies different trust boundaries to its public and administrative surfaces. The public map and API endpoints are unauthenticated by design: all data they expose is already publicly available from NASA and USGS, and no user data is collected. The administrative area is protected at the SvelteKit server hook level, which redirects unauthenticated requests before any D1 or R2 access occurs.

The Lambda Function URLs, which accept backfill trigger requests from the admin API, require AWS Signature V4 signing. The SvelteKit admin API signs outbound requests using `aws4fetch` @aws4fetch and a dedicated IAM user whose permissions are scoped to invoking the two initiator function URLs only. The Lambda execution role is similarly scoped: it has SQS send and receive permissions, ECR image pull rights, and the specific R2 and D1 bindings it needs, but no broader AWS account access. R2 buckets are private and served exclusively through Cloudflare's service-binding mechanism, with no public bucket URL exposed. Earthdata credentials are injected into the Lambda environment at deploy time via Terraform variables sourced from GitHub Actions secrets, and are not present in source code or build artefacts.

=== Operational monitoring views
The administrative UI exposes the operational state that is already recorded in D1. The jobs page lists processing jobs with status, timestamps, durations, feature/date identifiers, and filter summaries. The job-detail page expands this into per-bit filter breakdowns, progress bars, and thumbnail previews of successful observations. The features page aggregates the archive by water body and shows which features have recent data and which have repeated failures. The requests page shows the higher-level ingestion runs recorded in `data_requests`, distinguishing pending, processing, completed, and completed-with-errors states. Together, these views turn the database schema in @db-schema into an operator-facing dashboard rather than a hidden implementation detail.

#figure(
  image("admin-dashboard.png", width: 100%),
  caption: [Administrative jobs dashboard showing recent processing runs, job status, and per-job filter summaries.]
) <admin-dashboard>

#figure(
  image("admin-diagnostics.png", width: 100%),
  caption: [Administrative diagnostics view showing per-scene filter statistics, rejection counts, and failure details for a processed observation.]
) <admin-diagnostics>

=== Manual backfill interface
The backfill interface provides the operational path for ad hoc reprocessing. An administrator chooses the source and date range through a calendar-based dialog. The SvelteKit admin API first writes a new `data_requests` row to D1 so that the request has a durable audit record, then signs and sends an HTTP request to the appropriate Lambda Function URL using `aws4fetch`. The initiator Lambda receives the same payload shape used by scheduled runs, so manual and scheduled ingestion differ only in who triggered them and which date window they cover. This was intentionally implemented as a thin control-plane layer over the same backend workflow rather than as a separate "admin-only" processing pipeline.

#figure(
  image("admin-backfill.png", width: 72%),
  caption: [Manual backfill interface used to submit date-range ingestion requests and track their execution status.]
) <admin-backfill>

== Deployment Automation <cd-pipeline>
Infrastructure provisioning is implemented declaratively in Terraform @terraform across both AWS and Cloudflare. On the AWS side this includes the Lambda functions, function URLs, IAM roles, ECR repository, SQS queue, CloudWatch schedules, and Cognito resources. On the Cloudflare side it includes the D1 database, R2 bucket, and Pages project bindings. GitHub Actions then supplies the continuous-deployment path: Python dependencies are locked with `uv` @uv, exported into `requirements.txt`, baked into the Lambda container image, pushed to ECR, and then rolled out through `terraform apply`. Frontend deployment is handled in a separate job that builds the SvelteKit application, applies D1 migrations, and deploys the Pages bundle.

Alongside the production pipeline, a `local_fill` CLI module was implemented to support development and debugging. It runs either the ECOSTRESS or Landsat processor in-process for a single (feature, date) combination, without SQS or a scheduled trigger. The `--runtime local` flag redirects all storage writes to the Wrangler-managed local D1 and R2 stores, allowing the full processing path to be exercised on a developer machine against a locally seeded database. The `--runtime cloud` default writes directly to production D1 and R2, which makes it the primary tool for ad hoc backfills that do not warrant a full admin UI request. The module uses HTTPS range requests to open COGs rather than S3 links, avoiding the need for Earthdata S3 credentials during local development.

// =============================================================================
// 8. Evaluation
// =============================================================================
= Evaluation <evaluation>

== Cost Analysis
A primary goal of this project was to eliminate the recurring operational costs of the legacy system. Steady-state AWS usage was derived from the pipeline's D1 run history rather than from a single billing month, since all observed months included historical backfill activity alongside the regular daily scheduled runs.

=== Legacy System Costs
The legacy architecture incurred fixed monthly costs regardless of actual usage:

#figure(
  table(
    columns: (auto, auto, auto),
    table.header([*Service*], [*Tier/Usage*], [*Monthly Cost*]),
    "Heroku", "Eco Dyno (always-on)", "$5.00",
    "Supabase", "Pro Plan (>1GB storage)", "$25.00",
    table.cell(colspan: 2)[*Total*], [*\$30.00*],
  ),
  caption: [Legacy system monthly costs (USD)]
) <legacy-costs>

=== New System: AWS Usage
The data processing pipeline runs on AWS Lambda with SQS-based fan-out. Because every observed billing month included historical backfill activity, steady-state usage was derived from the D1 `data_requests` table rather than from a billing snapshot. At the time of writing, the system had completed 83 ECOSTRESS timer-triggered runs (2,626 scenes total, averaging 31.6 scenes per run) and 33 Landsat timer-triggered runs (563 scenes total, averaging 17.1 scenes per run). Projecting over 30 days at the per-scene durations measured in production (13.5 s average for ECOSTRESS, 15.7 s average for Landsat; see @performance) and the 3 GB Lambda memory allocation gives an estimated monthly compute usage of approximately 62,600 GB-seconds. @aws-usage shows the resulting steady-state estimates against free-tier limits.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    table.header([*Service*], [*Free Tier Limit*], [*Estimated Monthly Usage*], [*Utilisation*]),
    "Lambda (compute)", "400,000 GB-sec/mo", "~62,600 GB-sec", "~15.6%",
    "Lambda (requests)", "1,000,000 req/mo", "~1,500 requests", "~0.2%",
    "SQS", "1,000,000 req/mo", "<1,000,000 requests", "<100%",
    "Data Transfer", "100 GB/mo", "<5 GB", "<5%",
  ),
  caption: [AWS service usage against documented free-tier limits @aws-lambda-pricing @aws-sqs-pricing (steady-state estimates derived from D1 timer-run history; see text)]
) <aws-usage>

Historical backfills to populate the archive temporarily exceed these figures. The two-year Landsat backfill carried out in April 2026 dispatched approximately 16,800 scenes in a single day and consumed an estimated 7.2 million GB-seconds, incurring roughly \$20 in Lambda compute charges. Backfills are one-time operations; the recurring steady-state cost remains within the free tier.

Amazon ECR (Elastic Container Registry) does not have a perpetual free tier for the project's private repository storage. ECR private repositories are billed at \$0.10/GB-month @aws-ecr-pricing. The current image is 326 MB, giving an actual ECR cost of approximately \$0.03/month.

=== New System: Cloudflare Usage
The frontend, API, and storage layer run entirely on Cloudflare's edge network. @cloudflare-usage shows the measured usage against free-tier limits; figures are from the December 2025 interim window. R2 storage has grown since then with the addition of Parquet files, expanded Landsat coverage, and accumulation of two years of historical records.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    table.header([*Service*], [*Free Tier Limit*], [*Actual Usage*], [*Utilisation*]),
    "Workers (requests)", "100,000/day", "133/day avg", "0.1%",
    "R2 (storage)", "10 GB", "9.91 GB", "99.1%",
    "R2 (Class A ops)", "1,000,000/mo", "~8,800 ops", "~0.9%",
    "R2 (Class B ops)", "10,000,000/mo", "5,700 ops", "0.06%",
    "D1 (rows read)", "5,000,000/day", "2,400/day avg", "0.05%",
    "D1 (rows written)", "100,000/day", "167/day avg", "0.2%",
  ),
  caption: [Cloudflare service usage against documented free-tier limits @cloudflare-workers-pricing @cloudflare-r2-pricing @cloudflare-d1-pricing. R2 storage measured April 2026; Class A ops derived from steady-state scene rate (6 writes/scene × 1,461 scenes/mo); Class B ops and other figures from December 2025 interim measurement.]
) <cloudflare-usage>

=== Cost Comparison Summary
@cost-summary compares the total monthly costs between the two architectures.

#figure(
  table(
    columns: (auto, auto, auto),
    table.header([*Component*], [*Legacy System*], [*New System*]),
    "Compute (Backend/API)", "$5.00", "$0.00",
    "Object Storage", "$25.00", "$0.00",
    "Database", "Included above", "$0.00",
    "Container Registry (ECR)", "N/A", "$0.03",
    "Data Processing (Lambda/SQS/etc.)", "N/A (manual)", "$0.00",
    [*Monthly Total*], [*\$30.00*], [*\$0.03*],
  ),
  caption: [Monthly cost comparison summary (USD)]
) <cost-summary>

=== 12-Month Projection
R2 storage reached 9.91 GB by April 2026 (99.1% of the 10 GB free tier). Steady-state ingestion adds approximately 0.73 GB per month, derived from the per-scene average of 0.50 MB across 20,005 processed scenes multiplied by the 1,461 steady-state scenes per month estimated above. R2 overage is billed at \$0.015/GB-month @cloudflare-r2-pricing, so the projected additional cost is modest but grows with coverage. @cost-projection includes this growing overage alongside the fixed ECR charge.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    table.header([*Period*], [*Legacy System*], [*New System*], [*Cumulative Savings*]),
    "1 Month", "$30.00", "$0.04", "$29.96",
    "3 Months", "$90.00", "$0.13", "$89.87",
    "6 Months", "$180.00", "$0.26", "$179.74",
    "12 Months", "$360.00", "$0.52", "$359.48",
  ),
  caption: [Projected cost comparison over 12 months from April 2026 (USD). New system includes \$0.03/mo ECR plus growing R2 overage at \$0.015/GB-month @cloudflare-r2-pricing.]
) <cost-projection>

In steady-state operation the new architecture reduces recurring cost from \$30.00/month to under \$0.05/month, a greater than 99.8% reduction. Steady-state Lambda compute sits at roughly 15.6% of the free-tier threshold. R2 storage will accrue a small and slowly growing overage charge as the archive expands, reaching an estimated \$0.13/month after one year, which remains negligible relative to the legacy baseline. The only one-time cost incurred was approximately \$20 for the two-year historical Landsat backfill; that charge does not recur.

== Automation and Observability
The new architecture also changes how ingestion and failures are operated.

=== Automation Improvements
The legacy system required manual intervention for data updates: a developer had to modify script parameters, execute the retrieval code locally, and monitor progress while AppEEARS completed a server-side task. The new pipeline replaces that flow with four trigger paths:

- *Scheduled Execution*: two CloudWatch Event Rules fire the ECOSTRESS and Landsat initiators daily (the Landsat trigger is offset to 06:00 UTC so the two pipelines do not contend for the same SQS batch).
- *Parallel Processing*: the initiators enqueue one SQS message per scene and the processor Lambda scales horizontally up to its concurrency ceiling.
- *On-Demand Backfill*: administrators can request ad hoc ingestion for any date range on either sensor through the `/admin/requests` UI, which invokes the initiator Function URL with `trigger_type="manual"` and tracks progress in the same `data_requests` table as the scheduled runs.
- *Developer-Driven Reprocessing*: the `local_fill` CLI runs either processor in-process against a single (feature, date) combination, writing either to production D1 + R2 or to the Wrangler local store, enabling fast iteration without a full redeploy cycle.

The practical improvement over the legacy workflow is substantial. The old system required a developer to run a retrieval script locally for each day of data, with AppEEARS processing taking hours per request before any output was available. The new pipeline handles an equivalent workload (31.6 ECOSTRESS scenes per daily run across all monitored features) in approximately five minutes of wall time, with 50 parallel workers and no manual step required.

=== Observability Improvements
The new system records every pipeline execution in D1 with timestamps, status codes, per-bit filter statistics and error messages, and surfaces this through the admin dashboard (@admin-dashboard) without requiring AWS Console access. Failed scenes are logged with enough context for targeted reprocessing, and the historical record supports trend analysis and capacity planning. By contrast, the legacy system had no structured logging or job tracking: failures were only discovered by manually inspecting output files or noticing that expected data was absent from the interface.

== Data Quality and Coverage <filter-stats>
Every processed scene is now accompanied by a histogram of its 6-bit filter flags, stored in `temperature_metadata.filter_stats` as JSON and surfaced on the administrative dashboard. This provides a direct measurement of how the pipeline treats incoming data: administrators can distinguish QC rejection, cloud rejection, non-water rejection, nodata, range outliers and spatial outliers. The move from the legacy `LST_err` accuracy threshold to the PSD-defined QC bitmask (see @quality-control and @processor-code-filter) was motivated by validation scenes where the earlier threshold removed plausible water pixels; a formal retention-rate comparison across the same set of scenes has not yet been run.

Temporal coverage was the primary motivation for adding Landsat. A quantitative comparison still requires a fixed window of several months' data; the administrative dashboard's feature page already exposes the raw job counts per source, which will be the basis for this comparison in the final submission.

The aggregate filter statistics from the production database illustrate how sparse the accepted data is relative to the raw input. Across 3,341 ECOSTRESS scenes totalling 313 million pixels, only 11.4% of pixels are accepted; the equivalent figure for 7,540 Landsat scenes (3.2 billion pixels) is 9.5%. The dominant rejection causes are non-water classification and nodata or swath-gap fill: sensor tiles are large relative to the water bodies being monitored, so the majority of each clipped raster is land, and a significant additional fraction is unfilled by the sensor swath on a given pass. Cloud cover, which is frequent in the tropical Southeast Asian environments the platform monitors, is a further major contributor; its rejection rate varies considerably by season and feature.

The sensor-native cloud masks, while the most authoritative available source, are not perfect: thin cirrus, rapidly moving cloud edges, and haze can escape the ECOSTRESS cloud band and Landsat CFMask detection. When such contamination is limited to isolated pixels it is typically caught by the spatial Hampel outlier stage (bit 5 of the flag raster), which compares each pixel against its 5×5 neighbourhood. However, scene-wide or patch-scale cloud contamination that biases many adjacent water pixels uniformly, such as a thin fog layer over an entire reservoir, produces a systematic warm or cool offset that the within-scene Hampel test is not designed to detect. Such episodes manifest as anomalous spikes or troughs in the point-history time series. The per-bit filter statistics on the administrative dashboard allow an operator to identify scenes with an unusually high spatial-outlier fraction, which can be an indicator of partial cloud contamination that escaped earlier filter stages; a dedicated cross-scene anomaly detection step remains future work.

== Performance <performance>
The main performance improvement is architectural: direct STAC and COG access removes the AppEEARS order-and-poll stage, and SQS fan-out allows many processor instances to run in parallel. Measured against production job records, individual ECOSTRESS scenes complete in 13.5 s on average (7–48 s range across 4,268 jobs) and Landsat scenes in 15.7 s (5–294 s range across 12,785 jobs). With 50 concurrent workers, a full month of ECOSTRESS across all monitored features (750 to 1,050 scenes) processes in approximately five minutes. The largest recorded backfill, 1,271 Landsat scenes covering two months (December 2025 – January 2026), completed in under seven minutes of processor wall time. The legacy AppEEARS workflow required submitting a task to NASA's servers and waiting hours to days before data was available for download; the same data volume now takes minutes from trigger to stored result.

The 50-worker ceiling is not a Lambda or SQS constraint (both could sustain far higher concurrency) but a D1 one: Cloudflare D1 serialises all writes through a single writer, so concurrent processor invocations compete for the same lock. Raising the concurrency cap beyond 50 produced sporadic write failures in integration testing (see @implementation). The pipeline is therefore bottlenecked on the metadata store rather than on compute, and a migration to a database that supports concurrent writers would directly translate into faster backfill throughput.

On the read path, frontend performance is dominated by Parquet shard download size. Static assets, API metadata responses, and PNG previews are all served from Cloudflare's edge network and load near-instantly. The interactive overlay follows a two-stage strategy: the pre-generated PNG preview is displayed immediately on feature selection, giving the user visual feedback while the Parquet shard downloads in the background; the deck.gl layer then replaces it once the data is ready. For smaller features and ECOSTRESS shards this transition is fast, but the largest Landsat annual shards reach approximately 50 MB, which produces a noticeable wait on typical broadband connections. Once a shard is loaded, all subsequent interactions (threshold filtering, hover tooltips, palette switching) are handled on the GPU by deck.gl and complete within the one-second NFR target. Point-history queries run entirely in DuckDB-WASM with no further network requests, provided the relevant shard is already cached.

== User / Stakeholder Evaluation
Stakeholders had access to the live deployment throughout the project and provided feedback via the weekly email updates described in @methodology. Cloud account ownership was transferred to the external stakeholder during the project so the system can continue operating after handover.

TODO: Conduct formal evaluation.
== Testing
The data pipeline is covered by a `pytest` suite of 96 tests focused on unit-level processing logic and supporting helpers for the ECOSTRESS, Landsat, and D1 code paths. Tests cover areas including processor pipeline logic, quality-filter bitmask decoding for both the ECOSTRESS `QC` band and the Landsat `QA_PIXEL` field, raster clipping and mosaic helpers, and D1 insert and query helpers. No end-to-end integration tests exist: the suite exercises individual modules in isolation rather than running the full STAC-to-R2 pipeline against live data. The GitHub Actions deployment workflow runs the test suite before deploying Lambda and infrastructure changes, so the suite acts as a regression gate that prevents broken code from reaching the production pipeline.

== Limitations
A small residual cost of \$0.03 per month remains for ECR container-image storage (the current image is 326 MB at \$0.10/GB-month) @aws-ecr-pricing. R2 storage is the tightest constraint: at 9.91 GB against a 10 GB free tier, steady-state ingestion will exceed the threshold within weeks and incur a slowly growing overage charge (~\$0.015/GB-month). All other dimensions (Lambda compute, SQS, and Workers requests) remain well within their respective free-tier limits. The pipeline's daily schedule is a ceiling rather than a guarantee: sub-daily updates would require either a more frequent schedule or continuous polling of STAC, neither of which was required for this project. The sensor-native water masks are used in place of an external Sentinel-2 verification pipeline; a formal validation study against Sentinel-2 is beyond the current scope.

// =============================================================================
// 9. Summary and Reflections
// =============================================================================
= Summary and Reflections <summary>

== Summary of Results
The project delivered all four retained objectives and descoped two stretch objectives in consultation with the supervisor. The objectives table in @objectives-status records the formal delivery status; in practical terms, the platform became operationally sustainable, automated for routine ingestion, multi-sensor rather than ECOSTRESS-only, and substantially more interactive for end users. Evaluation showed recurring cost reduced to under \$0.05/month (see @cost-summary), while users gained per-pixel inspection, threshold filtering, archive downloads, and point-history queries in the browser.

== Implications for Stakeholders
For reservoir operators and ecological researchers in Southeast Asia, the practical implication is that the platform no longer depends on paid always-on hosting for routine operation. Because the stack is defined in Terraform and documented in the repository, a successor maintainer can recreate the infrastructure in their own Cloudflare and AWS accounts. The `local_fill` CLI and the on-demand backfill UI together mean that filling gaps in historical coverage, for example after a sensor outage, does not require editing the scheduled ingestion code.

// =============================================================================
// 10. Project Management
// =============================================================================
= Project Management <projectmgmt>

== Work Plan
Project work was organised into two phases, separated by the interim report. *Phase 1 (weeks 1–11)* focused on the non-functional foundations identified during requirement elicitation as highest priority: replacing the paid legacy stack with Cloudflare and AWS free-tier services, automating the ECOSTRESS ingestion pipeline, and putting the entire infrastructure under Terraform. *Phase 2 (weeks 12–26)* built on that foundation to deliver the user-facing enhancements: Landsat integration, the deck.gl and DuckDB-WASM visualisation layer, the administrative dashboard and its filter-explainability features, and the Parquet storage path. The midpoint snapshot is the interim report's §Timeline Assessment; the statuses below update that snapshot to the current point in the project.

== Progress Against Plan
Progress against the six deliverables from the proposal is summarised below. Statuses are updated from the midpoint snapshot in the interim report.

#figure(
  table(
    columns: (auto, auto, auto),
    table.header([*Deliverable*], [*Status*], [*Notes*]),
    "D1: Refactored codebase", "Complete", "SvelteKit + Terraform + Lambda; single-commit deploy",
    "D2: Sentinel-2 water mask", "Descoped", "Replaced by sensor-native QA layers (ECOSTRESS water band, Landsat QA_PIXEL bit 7)",
    "D3: Pixel-level storage", "Complete", "R2 + D1 hybrid; gzipped CSV + Parquet (migration 0018)",
    "D4: Interactive dashboard", "Complete", "MapLibre + deck.gl; DuckDB-WASM for point history; admin dashboard with filter explainability",
    "D5: Landsat integration", "Complete", "lambda_functions/landsat; sharing processor with ECOSTRESS",
    "D6: Technical documentation", "In Progress", "This report; user and deployment guides in Appendices A and B",
  ),
  caption: [Summary of deliverable status]
)

== Resource Management
The only project resources that required active operational management were cloud spend and deployment credentials. Cloud spend was controlled with billing alerts in both AWS and Cloudflare, so unexpected cost growth from backfills, storage growth, or deployment activity would be surfaced immediately while the platform was still operating against free-tier constraints. In practice, this monitoring confirmed that recurring cost stayed negligible, with the only non-zero steady-state charge being the ECR image-storage cost reported in @cost-summary.

Credential management was handled through GitHub Actions secrets. AWS access keys, Cloudflare API tokens, Earthdata credentials, and R2 keys were stored as repository secrets and injected into the deployment workflow as environment variables or Terraform inputs at runtime; they were not committed to the repository. This kept the CI/CD pipeline fully automated without exposing long-lived secrets in source control.

// =============================================================================
// 11. Contributions and Reflections
// =============================================================================
= Contributions and Reflections <contributions>

== Contributions
The project's primary contribution is demonstrating that a production-grade satellite data pipeline can operate sustainably within free-tier cloud limits. Rather than treating cost as a constraint to minimise after the fact, the architecture was designed around it from the start: Cloudflare R2 was chosen over AWS S3 for its zero egress fees, Lambda runs the geospatial processing only for the minutes per day it is needed, and the frontend is co-located with its storage on the same edge network. The outcome, under \$0.05 per month in steady-state recurring cost (see @cost-summary), is not merely a saving over the legacy system but a proof of concept that a research platform of this kind can remain operational after student handover without institutional compute budget.

The analytical design makes a less obvious choice than most comparable applications: rather than exposing a server-side time-series API, raw pixel data is archived as year-sharded Parquet and queried entirely in the browser through DuckDB-WASM. This eliminates a class of backend endpoints, keeps the data accessible to researchers in a standard format independent of the web interface, and moves query latency onto the client after the initial file fetch. The bitmask-level filter transparency extends the same research-oriented principle: every processed observation records which pixels were rejected and why across six independently trackable causes, rather than surfacing only a final valid/invalid mask. Any filtering decision can be inspected and reproduced from the stored statistics without access to the raw satellite imagery.

== Personal Reflection

The most consistent demand of this project was breadth, and most of it arrived as problems to solve rather than technologies to learn. Choosing which cloud services to use required evaluating competing providers against real cost and constraint tradeoffs before committing. Getting satellite data into the pipeline meant understanding how ECOSTRESS and Landsat distribute their products, which led to STAC catalogs and direct COG access. Making the map interactive with tens of thousands of pixels meant finding an approach that could handle that scale in the browser, which led to WebGL rendering via deck.gl after simpler options proved too slow. Deciding how to let users query point history while balancing storage and server compute costs meant first working out that Parquet was the right storage format for the problem, then discovering DuckDB-WASM as a way to query it in-browser. Reproducible deployment was a goal that led to learning Terraform. None of this followed a "learn X, apply X" pattern; the technology came at the end of the reasoning, not the beginning.

Overall the project delivered what it set out to do. The platform is deployed, usable, automated, and running within free-tier limits. The descoped objectives (Sentinel-2 water-mask validation and zone differentiation) were cut because the pipeline work consumed more of the timeline than expected, not because they were technically blocked.

The clearest lesson from the project is to challenge inherited assumptions earlier. The original system used NASA's AppEEARS service for data retrieval, and this was taken as a given for most of the project because that is what the previous team had built on. The discovery that ECOSTRESS data is accessible directly as Cloud-Optimised GeoTIFFs via STAC, without submitting an order and waiting hours for it to be fulfilled, only came in March. Switching to direct access was the right architectural decision and it is what the final system is built on, but arriving at it later in the project meant less time to build on top of it. The better habit would have been to re-evaluate the core assumptions of any inherited system at the start, rather than treating the previous team's choices as constraints.

== Future Work
Some improvements that could be made to the project are:

- *MODIS integration.* A third, coarser-resolution sensor would extend the historical baseline; it would slot naturally into the existing `source` column and processor-routing design, at the cost of not resolving smaller reservoirs.
- *Automated anomaly detection and alerting.* The admin dashboard surfaces failures passively; a once-per-day check that posts to an email or messaging service when any feature has gone more than N days without a successful observation would close the observability loop.
- *Extending the polygon set beyond Southeast Asia.* The pipeline is polygon-driven with no regional assumptions; adding reservoirs elsewhere is a data-entry task rather than an engineering one.
- *Public API documentation.* The `/api/` surface is stable but undocumented externally; an OpenAPI description would let third-party researchers consume temperature data directly.
- *Sentinel-2-assisted water-mask validation.* The descoped O2 objective would slot into the pipeline as an additional filter stage if future stakeholders required formal mask-validation evidence.
- *OPERA DSWx-HLS water mask.* The current pipeline relies on the sensor's own quality raster to identify water pixels: the ECOSTRESS `water` band for ECOSTRESS scenes and the CFMask-derived bit 7 of `QA_PIXEL` for Landsat. A dedicated, independently validated water-extent product would be more reliable. NASA's OPERA Dynamic Surface Water Extent from Harmonized Landsat Sentinel-2 (DSWx-HLS) @opera-dswx-hls provides 30 m per-pixel water classification updated on each Landsat/Sentinel-2 acquisition. Substituting DSWx-HLS as the water mask source, co-registered and resampled to the LST raster at processing time, would reduce both false water inclusions (land pixels near shorelines classed as water by QA_PIXEL) and false exclusions (water pixels near cloud edges discarded by an overly conservative cloud-shadow dilation).
- *CNN-based cloud masking for Landsat.* The Landsat cloud rejection stage uses the CFMask algorithm embedded in the `QA_PIXEL` bitmask, which is known to miss thin cirrus and haze, as discussed in @filter-stats. The DLR `ukis-csmask` library @ukis-csmask provides a convolutional neural-network cloud and cloud-shadow mask for Landsat and Sentinel-2 that has been shown to outperform CFMask on these edge cases. Integrating it as an optional second-pass cloud stage, applied to pixels that passed the `QA_PIXEL` cloud test, would reduce the scene-wide cloud contamination that the existing Hampel spatial-outlier filter cannot detect.

// =============================================================================
// Bibliography  (counts toward word/page limit per slide 8)
// =============================================================================
#heading(numbering: none)[Acknowledgements]

I would like to thank my supervisor, Dr. Tomas Maul, for his guidance throughout the project. His feedback and regular check-ins helped keep the work focused and the design decisions well-reasoned.

I am grateful to Dr. Matteo Redana, Dr. Celine Chong and Prof. Christopher Gibbins who provided the requirements for this platform and offered feedback throughout development. Their willingness to engage with the project on a regular basis through the weekly email updates made it possible to align the implementation with real operational needs.

Finally, this project would not have been possible without the foundation laid by the previous SEGP team led by Abdullah Usmani. Their proof-of-concept web application established that satellite-derived surface temperature data could be visualised usefully in the browser, and it gave this project a clear starting point and a concrete problem to solve rather than a blank canvas.

#bibliography("bibliography.yaml")

// =============================================================================
// Appendices (optional; NOT counted toward word/page limit)
// =============================================================================
#pagebreak()
#heading(numbering: none, level: 1)[Appendix A: User Manual]

*Browsing temperature data.* Open the deployed site at the project URL. The landing page shows a map of all monitored water bodies overlaid on satellite imagery. Click any polygon to open the feature's most recent observation: the temperature raster appears as a coloured overlay, and the sidebar shows the observation metadata (date, source, min/max/mean temperature). Hover a pixel to see its exact temperature in a tooltip; right-click a pixel to open a drawer with its time series across all available dates on the currently-selected source. Use the date scrubber at the bottom of the sidebar to step between dates, and the source toggle to switch between ECOSTRESS and Landsat. The threshold slider re-colours only pixels within the chosen temperature band, and the colour-palette selector switches between relative, fixed and grayscale renderings. Downloads (CSV, GeoTIFF and Parquet) are available from the sidebar for the current observation.

*Administrative access.* Administrators sign in at `/admin/login` using Cognito credentials issued by the project maintainer. Once signed in, `/admin/jobs` shows every processing job with its status, duration, thumbnail and per-bit filter statistics; `/admin/requests` lists every scheduled and on-demand ingestion run, and the "New Request" dialog triggers an on-demand backfill for a chosen source and date range; `/admin/features` aggregates job counts per water body; and `/admin/settings` tunes the `data_delay_days` lookback window.

*Running a local backfill.* After cloning the repository and installing dependencies (`npm install`; `cd lambda_functions && uv sync`), seed NASA Earthdata credentials into `~/.netrc` or `EARTHDATA_USERNAME`/`EARTHDATA_PASSWORD` environment variables. To run a single (feature, date) against the production D1 + R2: `cd lambda_functions && uv run python -m local_fill --source ecostress --feature NamTheun2 --start-date 2026-03-15`. To run against the Wrangler-local store, add `--runtime local` and first run `npm run r2:seed:local`.

#pagebreak()
#heading(numbering: none, level: 1)[Appendix B: Developer / Deployment Guide]

*Prerequisites.* Node 20, `uv` for Python, Terraform, the `wrangler` CLI (installed via `npm install`), and access to: a Cloudflare account with R2 and D1 enabled; an AWS account with permissions for Lambda, SQS, ECR, IAM and CloudWatch; a NASA Earthdata Login; and an AWS Cognito user pool (provisioned by Terraform).

*One-time setup.* Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars` and fill in the required variables (Cloudflare account/API token, R2 credentials, Earthdata username/password, AWS region). Run `terraform -chdir=terraform init`, then `terraform -chdir=terraform apply`. This provisions the AWS side (Lambdas, SQS queue, ECR repository, IAM role and user, Cognito user pool, CloudWatch Event Rules) and the Cloudflare side (R2 bucket, D1 database, Pages project). The D1 database ID that Terraform emits is written into `wrangler.toml` by `scripts/update_wrangler_db_id.sh`.

*Initial data load.* Apply the D1 schema with `npm run db:migrate:remote`. Trigger a first ingestion by either waiting for the scheduled daily trigger or calling `/admin/requests` with a manual date range.

*Routine deployment.* Every push to `main` triggers the GitHub Actions workflow described in @cd-pipeline, which runs tests, builds and pushes the Docker image, applies Terraform, applies pending D1 migrations, and deploys the SvelteKit frontend. No manual steps are required in steady state.

*Secrets.* The NASA Earthdata username and password, the Cloudflare API token and account ID, and the R2 access key and secret are stored as GitHub Actions secrets and passed through Terraform variables. They are *not* checked into the repository. Local development uses a `.dev.vars` file (listed in `.gitignore`) seeded by `scripts/setup-dev-auth.sh`.