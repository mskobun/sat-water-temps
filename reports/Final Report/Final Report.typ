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
//
// OUTDATED-CONTENT AUDIT (grep for "OUTDATED" to find every site):
//   DIAGRAMS (all from interim, all wrong for current architecture)
//     - High Level Overview.png   — shows AppEEARS + Step Function
//     - DB Schema.png             — missing every migration 0006–0021
//     - EcoStress Updater Flow.png — legacy AppEEARS flow
//   SCREENSHOTS (all predate current UI)
//     - map-interface.png         — no Landsat, no threshold, no source toggle
//     - admin-dashboard.png       — missing /admin/requests, /features, /settings
//   PROSE / CODE (pipeline architecture changed)
//     - §Motivation / Data Retrieval Automation — still OK but add note that
//       AppEEARS itself is legacy; we no longer use it at all.
//     - §Methodology / Data Processing Pipeline — drop Step Functions.
//     - §Design / ECOSTRESS Updater — rewrite 4-step pipeline entirely.
//     - §Implementation / ECOSTRESS:
//         * Initiator Lambda prose + code snippet are pure AppEEARS → replace
//         * Step Function State Machine subsection → DELETE
//         * Manifest Processor Lambda subsection  → DELETE
//         * Processor Lambda prose says "downloads from AppEEARS" → fix
//         * Processor code uses INVALID_QC_VALUES enum → replaced by bitmask
//     - §Evaluation / AWS Usage table — remove Step Functions row; numbers
//       are Dec-2025 and must be re-measured post-Landsat.
//     - §Evaluation / Cost Analysis summary — "Step Functions at 42.7%" line
//       no longer valid.
//   VERIFY (may be fine, cross-check against repo)
//     - Terraform snippet in §Implementation
//     - SvelteKit GET snippet in §Implementation (getFeatureDates signature)
//     - Continuous Deployment step list
// =============================================================================

#set page(paper: "a4", margin: 2.5cm, numbering: "1")
#set text(size: 12pt, font: "Calibri")
#set par(justify: true, leading: 0.75em)
#show raw: set text(font: "FiraCode Nerd Font", size: 10pt)
#show raw.where(block: true): set par(justify: false)
#set heading(numbering: "1.1")

// -----------------------------------------------------------------------------
// Outer Cover Page — matches template "Final Report - Outer-Cover format.doc"
// -----------------------------------------------------------------------------
#{
  set page(numbering: none)
  align(center)[
    #image("uon_logo.jpg", width: 6cm)

    #v(0.4cm)
    #text(size: 14pt)[School of Computer Science]

    #text(size: 14pt)[Faculty of Science and Engineering]

    #text(size: 14pt)[University of Nottingham]

    #text(size: 14pt)[Malaysia]

    #v(2.5cm)
    #text(size: 16pt, weight: "bold")[UG FINAL YEAR DISSERTATION REPORT]

    #v(2cm)
    #text(size: 18pt, weight: "bold")[Satellite Water Temperature Web Application Enhancement]

    #v(2cm)
  ]

  // Student block — left-aligned rows inside a centred box
  align(center)[
    #block(width: 11cm)[
      #set text(size: 13pt)
      #set par(justify: false)
      #align(left)[
        Student's name#h(1fr): Maksim Skobun \
        Student Number#h(1fr): 20510325 \
        Supervisor Name#h(1fr): Dr. Tomas Maul \
        Year#h(1fr): 2026
      ]
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
// Title page — matches template "Final Report - Title page-format.doc"
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
// Acknowledgements
// -----------------------------------------------------------------------------
#heading(numbering: none)[Acknowledgements]

// TODO: personalise. Suggested to thank: Dr. Tomas Maul (supervision); the
// previous SEGP team whose work this project builds on; NASA for ECOSTRESS /
// Landsat / AppEEARS / Earthdata; any stakeholders who gave domain input.
#pagebreak()

// -----------------------------------------------------------------------------
// Abstract
// -----------------------------------------------------------------------------
#heading(numbering: none)[Abstract]

// TODO: ~250 words. Recommended structure:
//   (1) Problem — inland water temperature monitoring in SE Asia; legacy
//       system costs $30/mo, manual pipeline, single-sensor, fragile UI.
//   (2) Approach — zero-cost serverless replatform (Cloudflare R2/D1/Pages +
//       AWS Lambda/Step Functions/SQS), automated daily ingest, Sentinel-2
//       water-mask verification, multi-sensor integration (ECOSTRESS +
//       Landsat), zone differentiation, enhanced visualisation.
//   (3) Outcome — $0.10/mo running cost (~99.7% reduction), automated
//       multi-sensor pipeline, interactive dashboard.
//   (4) One-sentence contribution statement.
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
Surface water temperature is a critical environmental indicator influencing aquatic ecosystems, water quality, and climate-related processes. However, in Southeast Asia, there remains a lack of continuous, high-resolution monitoring of inland water temperatures. The existing Satellite Water Temperature Web Application, developed under a previous SEGP project, was designed to visualise near-real-time temperature data derived primarily from NASA's ECOSTRESS sensor @ecostress. This system enables users to explore spatial and temporal variations in reservoir and downstream river temperatures, supporting research in hydrology, ecology, and climate impact studies.

While the original system demonstrated the concept, several limitations hindered its real-world use. The data retrieval process was inefficient and manual, taking many hours to complete and requiring modifying the code to adjust retrieval parameters. The system relied on paid-tier hosting for data storage and retrieval, threatening the long-term sustainability of the project. The immediate priority of this project was therefore to establish a robust, zero-cost infrastructure capable of supporting the advanced visualisation features planned for the final release. This project addresses those limitations by implementing a modern serverless architecture with an automated, observable data processing pipeline running on free-tier hosting, and then building on that foundation to deliver multi-sensor data integration, zone-aware analysis, and interactive visualisation.

== Aims
// TODO: one short paragraph summarising the overall aim.

== Objectives
// TODO: restate the six objectives from the proposal and mark each as
// delivered / partial / descoped.
//   O1  Data storage & retrieval optimisation
//   O2  Sentinel-2 water-mask verification
//   O3  Enhanced visualisation features
//   O4  Multi-platform satellite integration (Landsat)
//   O5  Zone differentiation (upstream reservoir vs downstream river)
//   O6  Code maintainability & documentation

== Report Structure
// TODO: one short paragraph mapping chapters of this report to the rubric.

// =============================================================================
// 2. Motivation  (carried over from interim §Motivation)
// =============================================================================
= Motivation

== Cost Reduction
A critical limitation of the original system was the cost of hosting. The backend was hosted on Heroku and incurred a monthly cost of \$5, while data was stored on Supabase which would have incurred a monthly cost of \$25 once more than 1 month of historical data was stored. This was identified as a major limitation by the stakeholders, who were concerned about the long-term sustainability of the project.

== Data Retrieval Automation
The original system relied on a script that had to be run manually to retrieve temperature data from AppEEARS (Application for Extracting and Exploring Analysis Ready Samples) @appeears, NASA's web service for accessing remote sensing data including ECOSTRESS. The script took hours to run, required modifying the code to adjust the retrieval parameters, and did not log failed processing attempts.

// TODO [OUTDATED]: the current system no longer uses AppEEARS at all.
// ECOSTRESS now uses NASA Earthdata CMR-STAC via the `earthaccess` library,
// and Landsat uses USGS STAC directly. Update this section (or at least the
// §Related Work framing) to note that AppEEARS was the legacy approach and
// we moved to direct STAC + COG access in the replatform.

== Code Quality and Reproducibility
The original system was written in Python and contained many anti-patterns and little documentation. File paths and parameters were hardcoded and not easily configurable. While the documentation contained deployment instructions, it was not comprehensive and did not cover all details of the system.

== Scientific and Stakeholder Motivation
// TODO: NEW. Short paragraph on why inland water temperature matters (ecology,
// climate, reservoir management) and who the intended users are.

// =============================================================================
// 3. Related Work
// =============================================================================
= Related Work

== Analysis of the Existing System
The primary point of reference for this project is the existing system developed by the previous SEGP project team @segp. The system demonstrated feasibility, but suffered from suboptimal architecture decisions that hindered its scalability and maintainability.

+ *Monolithic architecture*: The backend was built as a monolithic Flask application hosted on Heroku. This is convenient for development, but means it incurred constant hosting costs, regardless of usage. The cheapest Heroku server, or "dyno" as Heroku refers to them, costs \$5/mo @heroku-pricing. More powerful and expensive "dynos" might be required as the system gets used by more users.
+ *Storage constraints*: The system used Supabase Storage to store temperature data and images. The free tier of Supabase allows for 1 GB of storage, which is not enough to store historical temperature data for more than a month. In addition, Supabase's pricing structure only allows to purchase additional storage in a bundle of 100 GB for \$25/mo @supabase-pricing, which is in excess of what is needed and would significantly increase the cost of keeping the system running.
+ *Manual Data Processing Pipeline*: The script to fetch new data from AppEEARS was not automated or run on any cloud, unlike the rest of the system. Fetching new satellite data required a developer to modify the script's code and run it on their local machine. The script sequentially downloaded and processed data for hundreds of features, taking hours to run.
+ *Fragile Client-Side Logic*: The frontend was built using "vanilla JavaScript", making heavy use of manual DOM manipulation. This imperative approach tightly couples the logic to the specific HTML structure. As noted in modern software engineering literature, this pattern leads to brittle codebases where minor UI changes break functionality, making the addition of complex interactive features hard to maintain.

== Remote Sensing of Water Surface Temperature
// TODO: NEW. Short review (~1 page) of:
//   - ECOSTRESS LST product characteristics.
//   - Landsat 8/9 Collection 2 Level-2 surface temperature (ST_B10).
//   - Sentinel-2 for water extent (NDWI / MNDWI / GAM4Water).
//   - Prior work on inland water monitoring in SE Asia.

== Evaluation of Serverless Architecture
Traditional Virtual Private Servers (VPS) or Platform as a Service (PaaS) solutions like Heroku charge for reserved compute capacity, resulting in idle costs even though the system is not processing data or serving users. Adzic and Chatley (2017) demonstrate that for sporadic workloads, migrating to a serverless model can significantly reduce operational costs by minimising idle resource billing @serverless-compiuting. The "Function-as-a-Service" (FaaS) model allows the system to scale up when processing new batches of data, as well as scale to zero when not serving any users, ensuring the project operates entirely within free-tier limits.

In addition to idle cost, traditional architectures require reserving resources in specific physical locations, creating a tradeoff between latency and cost of keeping idle servers in as many regions as possible. Modern FaaS platforms like Cloudflare Workers solve this: the function code is stored in every "edge" location of their Content Delivery Network (CDN) @cloudflare-workers. Users' requests are then routed to the closest "edge" location, where a server almost instantaneously loads the function code and processes the request, ensuring superior latency anywhere in the world.

== Infrastructure as Code
A significant limitation in many software projects is the "reproducibility crisis." The legacy system relied on manual environment setup ("ClickOps"), a practice Morris (2016) identifies as a primary cause of "configuration drift" and deployment failure @infra-as-code.

To solve this, Infrastructure as Code (IaC) software can be used. With it, the infrastructure can be treated as normal code: checked in to version control, rolled back, redeployed to multiple environments. Terraform is the industry standard IaC solution, having plug-ins for every major cloud service provider.

== Web Mapping and Visualisation Frameworks
// TODO: NEW. Short justification (Leaflet / MapLibre / deck.gl; Svelte
// reactivity model) for the frontend stack used in §Design.

// =============================================================================
// 4. Description of the Work  (NEW — required by rubric, not in interim)
// =============================================================================
= Description of the Work

== Scope and Out-of-Scope
// TODO: enumerate what is in scope (replatform, Landsat, Sentinel-2 mask,
// visualisation enhancements, zone split) and explicitly out of scope
// (e.g. MODIS, sub-daily cadence, mobile app).

== Functional Specification
// TODO: describe user-facing behaviours.
//   - Public: map of monitored features; per-feature time series; per-pixel
//     temperature inspection; threshold filter; colour-scale options;
//     CSV/TIF download.
//   - Admin: jobs dashboard (/admin/jobs), on-demand backfill requests
//     (/admin/requests), feature management (/admin/features), global
//     settings (/admin/settings).

== Non-Functional Requirements
// TODO: reliability (automated retries), cost (free-tier-only),
// reproducibility (IaC + lockfiles), observability (D1 job records),
// latency (sub-second cold reads via edge cache).

== User Roles
// TODO: anonymous public viewer vs authenticated admin (Auth.js + AWS
// Cognito — src/hooks.server.ts, src/auth.ts).

// =============================================================================
// 5. Methodology
// =============================================================================
= Methodology

== Requirement Elicitation
A meeting was held with stakeholders to review the limitations of the current system. It was established that data reliability and low-cost deployment were the highest priority non-functional requirements. Therefore, it was decided to dedicate Phase 1 entirely to replatforming the system to zero-cost cloud solutions and automating the data processing pipeline.

== Development Methodology
// TODO: NEW. Short description of iterative workflow, trunk-based development
// with CI, supervisor review loop, commit/review cadence.

== Technology Selection

=== Storage
The architectural design process was initially driven by the need to resolve the storage cost bottlenecks of the legacy system. Researching alternatives to Supabase's S3-compatible storage, Cloudflare R2 stood out with the free plan offering 10 GB of data storage and zero egress fees, meaning no matter how many downloads from the storage will be done, they will not be charged for. In addition, even over the limit, R2 has cheaper monthly storage costs than any of the alternatives compared.

#figure(
  [#table(columns: 4, table.header([*Feature*], "Supabase Storage", [AWS S3 (`us-east-1` Region)], "Cloudflare R2"),
  "Free Tier Limit", "1 GB", "5 GB (for 12 months only)", "10 GB",
  "Monthly Storage Cost (over limit)", "$0.021/GB", "$0.023/GB (First 50TB)", "$0.015/GB",
  "Egress Fees", "$0.03/GB (over limit)", "$0.09/GB (over limit)", "Not Charged",
  "Minimum Monthly Spend", "$25 (over 1 GB)", "Pay-as-you-go", "Pay-as-you-go")],
  caption: "Comparison of S3-compatible storage services (USD)"
)

=== Frontend/API Ecosystem
Following the selection of R2, it made natural sense to use Cloudflare Workers for serving frontend files and API endpoints. Workers are hosted on the same Cloudflare network, ensuring superior latency and are integrated into Cloudflare's ecosystem, allowing easy linking of R2 buckets to the workers. The free plan of Workers allows up to 100 thousand requests daily, which is well within system requirements.

=== Data Processing Pipeline
While a pure Cloudflare solution would have been better for simplicity, Workers face strict limits on execution time and memory. In the Free tier, these limits are 10 ms of CPU time per request and 128 MB of memory. While this is enough for serving JSON APIs and frontend files, it is unsustainable for processing satellite rasters.

// TODO [OUTDATED PARAGRAPH ABOVE]: the rationale about AppEEARS being slow
// is no longer relevant because we dropped AppEEARS. Rewrite as: Worker
// limits are too strict for geospatial processing → chose AWS Lambda
// packaged as Docker images (GDAL/rasterio/geopandas need native libs).
// Remove the mention of Step Functions below — the current architecture
// does NOT use Step Functions anymore (see §Design).

Therefore, a workflow based on AWS Lambda was chosen @aws-lambda. A Lambda function can be any Docker image and can run up to 15 minutes. Coupled with other AWS technologies like Step Functions and SQS (Simple Queue Service), a complex data processing workflow can be built in a serverless fashion. Lambda also has a generous free tier of 400 thousand GB-seconds a month (where GB is the memory allocated to the Lambda), which is more than enough for a pipeline that updates from ECOSTRESS data daily.

=== DevOps and Infrastructure Strategy
To address the "configuration drift" and reproducibility issues identified in the legacy system, the project adopted a strict Infrastructure as Code (IaC) methodology. Given the requirement of supporting both AWS and Cloudflare platforms, Terraform was the only suitable solution. Terraform's provider-agnostic architecture allows the entire stack to be defined in a unified language.

The project utilised a "GitOps" framework @gitops, where the Git repository was used as the single source of truth for deploying both infrastructure and code changes. A GitHub Actions pipeline was set up to automatically update the code and apply Terraform changes on commits to the production branch.

=== Satellite Data Sources
// TODO: NEW. Justify ECOSTRESS + Landsat 8/9 choice (complementary cadence
// and resolution; both free via NASA). Explain why MODIS was not selected.

=== Data Access Strategy: AppEEARS vs Direct COG
// TODO: NEW. Describe the shift from pure-AppEEARS to a hybrid model in
// which the ECOSTRESS processor can also open NASA Earthdata HTTPS
// Cloud-Optimised GeoTIFFs directly in-process (commit 09ddbfe; see
// lambda_functions/local_fill/ and CLAUDE.md §"Running Processors Locally").

=== Quality Control Strategy
// TODO: NEW. Document the move from accuracy-threshold filtering to QC
// bitmask rules for ECOSTRESS (commit 630ba54) and subsequent removal of
// LST-accuracy rejection (commit 6cd4fe5). Reference filters.py in both
// ecostress/ and landsat/ modules.

// =============================================================================
// 6. Design
// =============================================================================
= Design

== High-Level Overview
The system architecture, as shown in @high-level, is divided into two zones. The Cloudflare zone handles synchronous user requests that simply retrieve data from the database and object storage and display it to the user. The AWS zone, on the other hand, is responsible for asynchronously processing new satellite data and updating the database and object storage.

// TODO [OUTDATED PROSE]: the sentence "processing new data from AppEEARS"
// has been softened above but should be rewritten to name the actual data
// sources: ECOSTRESS granules via NASA Earthdata CMR-STAC and Landsat C2 L2
// ST scenes via USGS STAC. No AppEEARS in the current design.

// TODO [OUTDATED DIAGRAM]: High Level Overview.png is from the interim and
// does not match the current architecture. It must be regenerated to show:
//   - ECOSTRESS initiator hitting CMR-STAC (earthaccess), NOT AppEEARS
//   - Landsat initiator hitting USGS STAC (pystac-client)
//   - Both initiators writing directly to SQS (no Step Function, no Manifest
//     Processor, no Status Checker — those Lambdas no longer exist)
//   - Processor Lambda opening COGs directly via HTTPS/S3 (not downloading
//     AppEEARS bundles)
//   - Admin on-demand backfill path (function URL → initiator with
//     trigger_type=manual)
//   - local_fill CLI path that bypasses SQS entirely
//   - Parquet path in addition to CSV in R2
#figure(
  [#image("High Level Overview.png")],
  caption: [High-Level System Architecture #text(red)[*(OUTDATED — regenerate)*]]
) <high-level>

== Data Storage
The system uses both Cloudflare R2 object storage and the D1 SQL database. D1 is used for fast access to feature metadata, as well as storing processing logs for the updater. R2 is used to store pixel-level temperature readings as well as TIF/PNG visualisations.

While it is possible to store temperature data in D1 since it is a CSV file, doing so is impractical. Each CSV has thousands of rows and is always accessed in a predictable pattern (load all of them at once). Since D1 charges per row read/written, keeping the CSV files in R2 and creating a "pointer" to them in the metadata table is more efficient.

// TODO [OUTDATED DIAGRAM]: DB Schema.png is from the interim and is missing
// every migration from 0006 onwards. Regenerate after reviewing
// migrations/0006_*.sql through 0021_*.sql. At minimum it must now include:
//   - filter_stats at job level       (0006)
//   - removal of unique task_id       (0004)
//   - removal of status column        (0005, then re-added per 0009/0020/0021)
//   - dispatched_at                   (0008)
//   - app_settings table              (0010)
//   - submit (renamed from scrape)    (0011)
//   - source column (ECO vs Landsat) (0012)
//   - latest_sort_date               (0013)
//   - pixel_size / pixel_size_x      (0014, 0017)
//   - date normalisation             (0015)
//   - unified data_requests          (0016)
//   - parquet_path                   (0018)
//   - raster_geometry                (0019)
//   - nodata_status                  (0020)
//   - ecostress_requests view        (0007)
#figure(
  [#image("DB Schema.png")],
  caption: [D1 Database Schema #text(red)[*(OUTDATED — regenerate)*]]
)

== ECOSTRESS Updater
// TODO [OUTDATED — REWRITE ENTIRELY]: the 4-step pipeline below describes
// the *interim* design (AppEEARS + Step Function polling + Manifest
// Processor + Fan-Out). That design has been REPLACED. The current flow
// (see lambda_functions/ecostress/initiator.py) is:
//
//   1. Daily Trigger — CloudWatch Event Rule fires the Initiator Lambda.
//   2. CMR-STAC Search — Initiator uses the NASA `earthaccess` library to
//      search Earthdata CMR for ECO_L2T_LSTE v002 granules intersecting
//      each polygon's bounding box within the date window. Date window
//      defaults to a 2-day lookback (the `data_delay_days` app setting).
//   3. Granule Grouping — granules are grouped by (AID, date) and their
//      per-band COG hrefs (LST, QC, water, cloud, EmisWB, ...) are
//      collected. S3 hrefs are used in Lambda; HTTPS hrefs are preferred
//      for local runs (via `--prefer-s3-hrefs=false` / local_fill).
//   4. Direct SQS Enqueue — one message per (AID, date) goes straight to
//      the processor SQS queue. NO Step Function, NO Manifest Processor,
//      NO Status Checker Lambda.
//   5. Parallel Processing — Processor Lambda consumes SQS messages and
//      opens the COGs directly (no bundle download), applies QC bitmask
//      filtering, writes CSV/Parquet/TIF/PNG to R2, and inserts metadata
//      into D1.
//
// Also describe the unified data_requests table (migration 0016) that logs
// every initiator run (scheduled or manual) and the admin on-demand path
// that invokes the initiator via a Function URL with trigger_type=manual.

// TODO [OUTDATED PROSE — DO NOT PUBLISH]:
ECOSTRESS Updater is responsible for fetching and processing new data from AppEEARS into the system. The pipeline is as follows:
1. *Daily Trigger*: A CloudWatch Event Rule triggers the *Initiator Lambda* daily at 00:00 UTC. The *Initiator Lambda* submits a task to AppEEARS to collect information for regions of interest.
2. *Asynchronous Polling*: Since AppEEARS processing times are unpredictable, taking from minutes to sometimes hours, an AWS Step Function is used to wait for the request to complete. The Step Function calls the *Status Checker Lambda*, which polls AppEEARS whether the task is done. If yes, the pipeline goes to the next step, otherwise the Step Function will retry with exponential backoff @exponential-backoff (doubling the wait time between attempts each time). Using a Step Function with backoff prevents "busy waiting" and minimises compute costs during long delays.
3. *Task Fan-Out*: Once the AppEEARS task is done, the *Manifest Processor Lambda* retrieves the file list. Instead of processing files sequentially, it implements a "Fan-Out" pattern: it splits the task into individual "scenes" (combination of area ID + date) and pushes a message for each scene into an *SQS Queue*. This decouples retrieval from processing, allowing multiple *Processor Lambdas* to fire in parallel, significantly reducing total pipeline runtime.
4. *Parallel Processing*: The *Processor Lambda* consumes messages from the *SQS Queue*. For each scene it downloads all the data for the scene from AppEEARS, processes the data and uploads the results and metadata to R2 and D1 respectively.

// TODO [OUTDATED DIAGRAM]: EcoStress Updater Flow.png depicts the legacy
// AppEEARS + Step Function + Manifest Processor flow. It is no longer
// correct. Regenerate to match the CMR-STAC direct-to-SQS flow above.
#figure(
  [#image("EcoStress Updater Flow.png")],
  caption: [Internal Logic of ECOSTRESS Updater #text(red)[*(OUTDATED — regenerate)*]]
) <updater-design>

== Landsat Updater
// TODO: NEW. Mirror the ECOSTRESS section. Cover:
//   - Cadence (Landsat 8/9 combined revisit ~8 days).
//   - Product used (Collection 2 Level-2 surface temperature).
//   - QA_PIXEL cloud / water bitmask filters in landsat/filters.py.
//   - How the `source` column (migration 0012) lets the frontend
//     disambiguate ECOSTRESS vs Landsat pixels.

== Zone Differentiation
// TODO: NEW. Describe upstream reservoir vs downstream river zones:
//   - Convention used in polygons_new.geojson.
//   - How the processor separates statistics per zone.
//   - How the UI surfaces the split.

== Sentinel-2 Water Mask Verification
// TODO: NEW. Describe the GAM4Water approach (see GAM4water_0.0.4.R) and
// how Sentinel-2 imagery validates/corrects water extent.

== Frontend Design
// TODO: NEW.
//   - Route layout (src/routes/): (map), feature, archive,
//     admin/{jobs, requests, features, settings}.
//   - Map interaction model and state management.
//   - Admin dashboard information architecture.

// =============================================================================
// 7. Implementation
// =============================================================================
= Implementation

== Infrastructure as Code
All cloud infrastructure for this project is defined using Terraform configuration files, enabling reproducible deployments and version-controlled infrastructure. The Terraform codebase manages resources across both AWS and Cloudflare platforms from a unified configuration.

The Cloudflare resources are defined declaratively, as shown in @terraform-cloudflare. Similarly, AWS Lambda functions, IAM roles, SQS queues, and Step Functions are all provisioned through Terraform, ensuring that the entire infrastructure can be recreated from scratch or replicated to a new environment with a single command.

// TODO [VERIFY SNIPPET]: cross-check resource names and attributes against
// the current terraform/ module. Bucket/DB names may differ from the
// schematic version carried over from the interim.
#figure(
```hcl
resource "cloudflare_r2_bucket" "data" {
  account_id = var.cloudflare_account_id
  name       = var.r2_bucket_name
}

resource "cloudflare_d1_database" "main" {
  account_id = var.cloudflare_account_id
  name       = "sat-water-temps-db"
}
```,
caption: [Terraform configuration for Cloudflare resources #text(red)[*(VERIFY against current terraform/)*]]
) <terraform-cloudflare>

== Data Processing Pipeline — ECOSTRESS
// TODO [OUTDATED OPENING]: "orchestrated by AWS Step Functions" is wrong —
// the current architecture has no Step Function. Rewrite as: a pair of
// Lambdas (Initiator + Processor) connected by an SQS queue.
The ECOSTRESS data processing pipeline is implemented as a series of AWS Lambda functions orchestrated by AWS Step Functions. All Lambda functions are packaged into a single Docker image deployed to Amazon Elastic Container Registry (ECR), with each function having a different entry point. Docker packaging was necessary because the processing code depends on geospatial libraries such as `rasterio` and `geopandas`, which require native C libraries (GDAL, libcurl) that cannot be installed via standard Lambda deployment packages.

=== Initiator Lambda
// TODO [OUTDATED PROSE + SNIPPET]: the description and code below reflect
// the old AppEEARS-based initiator and must be replaced. The current
// initiator (lambda_functions/ecostress/initiator.py):
//   - uses `earthaccess.login()` + `earthaccess.search_data(short_name=
//     "ECO_L2T_LSTE", version="002", bounding_box=..., temporal=...)`,
//     NOT AppEEARS submit_task
//   - iterates polygons from static/polygons_new.geojson, groups granules
//     by (AID, date), extracts per-band COG hrefs (LST/QC/water/cloud/
//     EmisWB, plus optional LST_err/height)
//   - sends one SQS message per (AID, date) directly — no Step Function
//   - supports trigger_type="manual" via Function URL for admin-initiated
//     backfills, and records each run in the `data_requests` table
//   - honours `data_delay_days` from app_settings (default 2) for the
//     lookback window
// Replace the snippet with a ~10-line excerpt from the current handler,
// e.g. the earthaccess.search_data + SQS send_message block.
The pipeline begins with the *Initiator Lambda*, triggered daily by a CloudWatch Event Rule. This function authenticates with AppEEARS and submits a data request for all regions of interest defined in the GeoJSON file. Upon successful task submission, it starts the Step Function state machine to monitor the request (@initiator-code).

// TODO [OUTDATED CODE SNIPPET]: remove and replace with a snippet from the
// current lambda_functions/ecostress/initiator.py.
#figure(
```python
def handler(event, context):
    token = get_token(user, password)
    roi = gpd.read_file("static/polygons_new.geojson")
    task_request = build_task_request(product, layers, roi.__geo_interface__, sd, ed)
    task_id = submit_task(headers, task_request)
    sfn_client.start_execution(
        stateMachineArn=state_machine_arn,
        input=json.dumps({"task_id": task_id, "wait_seconds": 30})
    )
```,
caption: [Initiator Lambda handler #text(red)[*(OUTDATED — replace)*]]
) <initiator-code>

// TODO: the initiator timeout bump to 900s (commit 7699a3c) needs
// re-verification. It was bumped for the AppEEARS workflow; under the
// current CMR-STAC direct-search workflow the relevant cost is
// earthaccess.search_data latency per polygon. Confirm current timeout
// in terraform/ and explain why it is what it is.

=== Step Function State Machine
// TODO [OUTDATED — DELETE THIS SUBSECTION]: there is no Step Function in
// the current architecture. The entire subsection below (including the
// @stepfn-backoff figure) must be removed. If exponential backoff is still
// relevant anywhere (e.g. internal retries), reuse the citation there; if
// not, also drop @exponential-backoff from the bibliography references.
The Step Function implements an exponential backoff polling pattern @exponential-backoff to handle AppEEARS' variable processing times. If the task is not complete, the state machine doubles the wait interval and retries, preventing unnecessary API calls while ensuring timely detection of completed tasks (@stepfn-backoff).

#figure(
```json
"DoubleWait": {
  "Type": "Pass",
  "Parameters": {
    "task_id.$": "$.task_id",
    "wait_seconds.$": "States.MathAdd($.wait_seconds, $.wait_seconds)"
  },
  "Next": "WaitDynamic"
}
```,
caption: [Exponential backoff state definition #text(red)[*(OUTDATED — delete)*]]
) <stepfn-backoff>

=== Manifest Processor Lambda
// TODO [OUTDATED — DELETE THIS SUBSECTION]: the Manifest Processor Lambda
// no longer exists. Its responsibilities (grouping granules by scene and
// enqueuing SQS messages) have been absorbed into the Initiator Lambda.
// Remove this subsection entirely.
Once AppEEARS marks the task as complete, the *Manifest Processor Lambda* retrieves the file manifest and implements a Fan-Out pattern. Files are grouped by "scene" (combination of area ID and date), and each scene is pushed as a separate message to an SQS queue. This decouples manifest processing from data processing, enabling parallel execution.

=== Processor Lambda
// TODO [OUTDATED PROSE]: "Downloads all raster files ... from AppEEARS" is
// wrong. The current processor opens Cloud-Optimised GeoTIFFs directly
// from the hrefs passed in the SQS message (S3 in Lambda, HTTPS under
// local_fill). Nothing is "downloaded from AppEEARS". Rewrite accordingly
// and reference lambda_functions/ecostress/processor.py.
The *Processor Lambda* is triggered by SQS messages and performs the core data processing. For each scene, it:
1. Downloads all raster files (LST, LST_err, QC, water mask, cloud mask, etc.) from AppEEARS
2. Applies quality filters by masking invalid QC values and cloud-contaminated pixels
3. Generates filtered GeoTIFF and CSV files containing temperature data
4. Creates PNG visualisations with multiple colour scales (relative, fixed, grayscale)
5. Uploads all outputs to Cloudflare R2 storage
6. Inserts metadata records into Cloudflare D1 database

The core filtering logic is shown in @processor-code.

// TODO [OUTDATED CODE SNIPPET]: `df["QC"].isin(INVALID_QC_VALUES)` is no
// longer used — QC filtering moved to bitmask rules (commit 630ba54) and
// the LST-accuracy rejection was removed (commit 6cd4fe5). Replace with a
// current snippet from lambda_functions/ecostress/filters.py showing the
// bitmask-based QC mask and the cloud-mask join.
#figure(
```python
def process_rasters(aid_number, date, selected_files, ...):
    # Apply quality control filtering
    df[f"{col}_filter"] = np.where(df["QC"].isin(INVALID_QC_VALUES), np.nan, df[col])
    df[f"{col}_filter"] = np.where(df["cloud"] == 1, np.nan, df[f"{col}_filter"])

    # Upload to R2 and insert metadata to D1
    upload_to_r2(s3_client, bucket_name, tif_key, filter_tif_path)
    insert_metadata_to_d1(feature_id, date, metadata, csv_key, tif_key, png_r2_keys)
```,
caption: [Processor Lambda data filtering and upload #text(red)[*(OUTDATED — replace)*]]
) <processor-code>

// TODO: describe the migration from the INVALID_QC_VALUES enumeration to
// bitmask-based QC rules (commit 630ba54), and the removal of the
// over-aggressive LST accuracy rejection (commit 6cd4fe5). Reference
// lambda_functions/ecostress/filters.py.

== Data Processing Pipeline — Landsat
// TODO: NEW. Parallel structure to the ECOSTRESS subsections. Highlight
// that the modular refactor let us reuse lambda_functions/common (storage,
// raster I/O, parquet, metadata helpers) for Landsat with minimal new code.

== Local Processor Runtime (`local_fill`)
// TODO: NEW. Describe the in-process CLI (lambda_functions/local_fill/).
//   - Motivation: debugging the pipeline locally and backfilling single
//     features without dispatching through SQS.
//   - Two runtime modes: `--runtime cloud` (prod D1 + R2) and
//     `--runtime local` (Wrangler local D1 + R2).
//   - ECOSTRESS HTTPS COG support (commit 09ddbfe) and why HTTPS is
//     preferred over S3 for local development.

== Hybrid Storage Architecture
The system employs a hybrid storage architecture to optimise both cost and performance:

*Cloudflare D1* (SQLite-based serverless database) stores:
- Feature metadata (location names, latest dates)
- Temperature statistics per observation (min/max/mean temperature, pixel counts)
- Processing job logs for observability
- R2 file paths pointing to the actual data

*Cloudflare R2* (S3-compatible object storage) stores:
- Raw temperature CSV files with pixel-level readings
- Processed GeoTIFF rasters
- PNG visualisations at multiple colour scales

This separation ensures D1 stays within free-tier row limits while R2 handles bulk data storage with zero egress fees.

// TODO: NEW — add a paragraph describing the Parquet path (migration 0018):
// why Parquet supplements the CSV files for efficient columnar queries
// and what workflow now reads from Parquet.

== Frontend Implementation
The frontend is built with SvelteKit and deployed to Cloudflare Pages. SvelteKit's server-side rendering capabilities are leveraged through Cloudflare's edge runtime, with API routes defined as TypeScript server endpoints that query D1 and R2 directly (@sveltekit-api). The main interface (@map-interface) displays an interactive satellite map with clickable polygons representing monitored water bodies.

// TODO [OUTDATED SCREENSHOT]: Interim Report/map-interface.png is from
// December 2025 and does not reflect the current UI (Landsat overlay,
// source toggle, pixel-inspection, threshold filter, updated colour
// palette UI, etc.). Retake against the current frontend and save to
// reports/Final Report/ (not the interim folder).
#figure(
  image("map-interface.png", width: 90%),
  caption: [Main map interface showing monitored water bodies in Southeast Asia #text(red)[*(OUTDATED — retake)*]]
) <map-interface>

// TODO [VERIFY SNIPPET]: the snippet below was a schematic example in the
// interim. Verify it still matches an actual endpoint in src/routes/api/
// (e.g. src/routes/api/feature/) or replace with a real excerpt. Signature
// and helper names (`getFeatureDates`) may have changed.
#figure(
```typescript
export const GET: RequestHandler = async ({ params, platform }) => {
  const db = platform?.env?.DB;
  const dates = await getFeatureDates(db, featureId);
  return json(dates, { headers: { 'cache-control': 'public, max-age=120' } });
};
```,
caption: [SvelteKit API endpoint accessing D1 #text(red)[*(VERIFY — may be outdated)*]]
) <sveltekit-api>

The frontend includes an administrative dashboard that displays real-time processing job status, enabling monitoring of the automated pipeline without requiring AWS Console access (@admin-dashboard).

// TODO [OUTDATED SCREENSHOT]: Interim Report/admin-dashboard.png predates
// all of /admin/requests (on-demand backfill), /admin/features (feature
// management), /admin/settings (app_settings UI from migration 0010), and
// the Landsat rows in /admin/jobs. Retake each admin sub-page and save
// under reports/Final Report/ with descriptive names.
#figure(
  image("admin-dashboard.png", width: 90%),
  caption: [Administrative dashboard showing processing job status #text(red)[*(OUTDATED — retake; add screenshots of /admin/requests, /admin/features, /admin/settings)*]]
) <admin-dashboard>

// TODO: NEW subsections for visualisation enhancements delivered after interim:
//   - Pixel-level temperature inspection (hover/click).
//   - User-defined threshold visualisation.
//   - Dynamic colour palettes that auto-scale to local temperature ranges.
//   - Admin pages: /admin/jobs, /admin/requests, /admin/features, /admin/settings.

== Authentication
// TODO: NEW. Brief coverage of Auth.js + AWS Cognito (src/hooks.server.ts,
// src/auth.ts); scripts/setup-dev-auth.sh for local development.

== Continuous Deployment
// TODO [VERIFY]: the six pipeline steps below describe the interim-era
// workflow. Cross-check against .github/workflows/ to make sure the
// current order and steps match (e.g. any added steps for Landsat,
// migration ordering relative to Pages deploy, any added lint/test gates).
A GitHub Actions workflow automates deployment whenever code is pushed to the main branch. Python dependencies are managed using `uv`, a modern package manager that generates a lockfile (`uv.lock`) ensuring deterministic builds across environments. The pipeline goes as follows:
1. Builds the Docker image containing all Lambda functions
2. Pushes the image to Amazon ECR
3. Runs `terraform apply` to update all infrastructure
4. Builds the SvelteKit application
5. Applies D1 database migrations using Wrangler CLI
6. Deploys the frontend to Cloudflare Pages

This ensures that both infrastructure and application code are deployed atomically, reducing configuration drift and enabling rapid iteration.

== Problems Encountered and Design Changes
// TODO: NEW — required by the rubric ("problems encountered, any changes
// made to the design as a result of the implementation"). Suggested items:
//   - ECOSTRESS LST-accuracy filter was over-aggressive (fix 6cd4fe5),
//     then replaced with QC bitmask rules (fix 630ba54).
//   - Initiator timeout too short under AppEEARS load → bumped to 900s
//     (fix 7699a3c).
//   - Job-level filter stats were being overwritten by per-scene stats
//     (fix ea31ed2).
//   - Schema churn around data_requests unification (0016) and status
//     columns (0005, 0009, 0020, 0021).

// =============================================================================
// 8. Evaluation
// =============================================================================
= Evaluation

== Cost Analysis
// TODO [OUTDATED NUMBERS]: every usage figure below is from December 2025
// (the interim measurement window) and pre-dates Landsat, the direct
// CMR-STAC architecture, and increased activity from the admin on-demand
// backfill path. Re-measure across a full month (ideally March or April
// 2026) with both pipelines running, pull from AWS Cost Explorer and
// Cloudflare Analytics, and update every table in this section.
A primary goal of this project was to eliminate the recurring operational costs of the legacy system. To validate this objective, actual cloud service usage was recorded over a one-month period and compared against free-tier allocations.

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
// TODO [OUTDATED OPENING]: "Lambda with Step Functions orchestration" is
// no longer true — drop Step Functions from the description.
The data processing pipeline runs on AWS Lambda with Step Functions orchestration. @aws-usage shows the measured usage against perpetual free-tier limits.

// TODO [OUTDATED TABLE]: all numbers are December 2025 figures. Also the
// "Step Functions" row must be removed entirely (no Step Function in the
// current architecture, so Step Functions free-tier utilisation is 0%).
// Re-measure with both ECOSTRESS + Landsat running for a full month.
#figure(
  table(
    columns: (auto, auto, auto, auto),
    table.header([*Service*], [*Free Tier Limit*], [*Actual Usage*], [*Utilisation*]),
    "Lambda (compute)", "400,000 GB-sec/mo", "28,756 GB-sec", "7.2%",
    "Lambda (requests)", "1,000,000 req/mo", "1,570 requests", "0.2%",
    "Step Functions", "4,000 transitions/mo", "1,706 transitions", "42.7%",
    "SQS", "1,000,000 req/mo", "276,810 requests", "27.7%",
    "Data Transfer", "100 GB/mo", "0 GB", "0%",
  ),
  caption: [AWS service usage (perpetual free tier) #text(red)[*(OUTDATED — refresh; remove Step Functions row)*]]
) <aws-usage>

Amazon ECR (Elastic Container Registry) does not have a perpetual free tier. Lambda requires Docker images to be stored in private ECR repositories, incurring storage costs of \$0.10/GB/month. The current Docker image consumes 1 GB of storage, resulting in a monthly cost of \$0.10.

=== New System: Cloudflare Usage
The frontend, API, and storage layer run entirely on Cloudflare's edge network. @cloudflare-usage shows the measured usage against free-tier limits.

// TODO [OUTDATED TABLE]: all numbers are December 2025 figures. Refresh
// against Cloudflare Analytics for the final reporting window. R2 storage
// in particular will have grown (Parquet added, more historical coverage
// retained, Landsat products added).
#figure(
  table(
    columns: (auto, auto, auto, auto),
    table.header([*Service*], [*Free Tier Limit*], [*Actual Usage*], [*Utilisation*]),
    "Workers (requests)", "100,000/day", "133/day avg", "0.1%",
    "R2 (storage)", "10 GB", "0.77 GB", "7.7%",
    "R2 (Class A ops)", "1,000,000/mo", "3,170 ops", "0.3%",
    "R2 (Class B ops)", "10,000,000/mo", "5,700 ops", "0.06%",
    "D1 (rows read)", "5,000,000/day", "2,400/day avg", "0.05%",
    "D1 (rows written)", "100,000/day", "167/day avg", "0.2%",
  ),
  caption: [Cloudflare service usage #text(red)[*(OUTDATED — refresh)*]]
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
    "Container Registry (ECR)", "N/A", "$0.10",
    "Data Processing (Lambda/SQS/etc.)", "N/A (manual)", "$0.00",
    [*Monthly Total*], [*\$30.00*], [*\$0.10*],
  ),
  caption: [Monthly cost comparison summary (USD)]
) <cost-summary>

=== 12-Month Projection
@cost-projection extrapolates the monthly costs over a 12-month period. The ECR storage cost is the only non-zero expense in the new architecture.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    table.header([*Period*], [*Legacy System*], [*New System*], [*Cumulative Savings*]),
    "1 Month", "$30.00", "$0.10", "$29.90",
    "3 Months", "$90.00", "$0.30", "$89.70",
    "6 Months", "$180.00", "$0.60", "$179.40",
    "12 Months", "$360.00", "$1.20", "$358.80",
  ),
  caption: [Projected cost comparison over 12 months (USD)]
) <cost-projection>

// TODO [OUTDATED SUMMARY]: "Step Functions at 42.7% being the highest
// utilised resource" is no longer true — Step Functions are gone. Identify
// the new tightest headroom from the refreshed tables (likely R2 storage
// or SQS/Lambda requests) and rewrite the sentence. Also confirm the
// "99.7%" figure still holds after adding Landsat.
The analysis demonstrates that the new serverless architecture achieves a cost reduction of 99.7%, with the only recurring expense being \$0.10/month for ECR storage. The annual saving of \$358.80 directly addresses stakeholder concerns regarding long-term sustainability. Importantly, the serverless model provides significant headroom for growth: current usage remains well below free-tier thresholds across all metered services, with Step Functions at 42.7% being the highest utilised resource. The pay-as-you-go pricing model ensures costs scale proportionally with actual demand rather than requiring expensive tier upgrades.

== Automation and Observability
Beyond cost reduction, the new architecture delivers significant improvements in automation and operational observability compared to the legacy system.

=== Automation Improvements
The legacy system required manual intervention for data updates: a developer had to modify script parameters, execute the retrieval code locally, and monitor progress over several hours. The new pipeline eliminates this entirely through:

- *Scheduled Execution*: CloudWatch Event Rules trigger the pipeline daily at 00:00 UTC without human intervention
- *Parallel Processing*: The Fan-Out architecture processes multiple scenes concurrently, reducing total pipeline runtime from hours to minutes
// TODO: add — on-demand backfill via /admin/requests (for one-off gaps)
// and local_fill (for developer-driven reprocessing).

=== Observability Improvements
The legacy system provided no visibility into processing status or historical job performance. Failures were only discovered when users reported missing data. The new system implements comprehensive observability:

- *Processing Logs*: Every pipeline execution is recorded in D1 with timestamps, status codes, and error messages
- *Administrative Dashboard*: A web-based interface (@admin-dashboard) displays real-time job status, enabling monitoring without AWS Console access
- *Structured Error Handling*: Failed scenes are logged with detailed context, enabling rapid diagnosis and targeted reprocessing
- *Audit Trail*: Historical processing records enable trend analysis and capacity planning

These improvements transform the system from a fragile, manually-operated tool into a self-sustaining service that can run indefinitely without developer intervention while providing full visibility into its operational state.

== Data Quality and Coverage
// TODO: NEW. Evaluate:
//   - Pixel retention rate before vs after the QC bitmask change.
//   - Temporal coverage per feature — how much gap was filled by adding
//     Landsat alongside ECOSTRESS.
//   - Spatial coverage — features with usable vs unusable data.
//   - Sentinel-2 water-mask verification results.

== Performance
// TODO: NEW.
//   - End-to-end pipeline latency (trigger → data visible in UI).
//   - Fan-out parallelism benefit (sequential baseline vs SQS-parallel).
//   - API P50/P95 latencies from Cloudflare analytics.

== User / Stakeholder Evaluation
// TODO: NEW. Decide with supervisor which is feasible:
//   - Structured walkthrough with the stakeholder(s) from requirement
//     elicitation, recording feedback against the original requirements.
//   - Short questionnaire if multiple users are realistic.
//   - Otherwise: heuristic evaluation against the non-functional requirements.

== Testing
// TODO: NEW.
//   - pytest unit suite (`uv run pytest tests/ -v`) — what it covers.
//   - TypeScript type checks (`npm run lint` → tsc --noEmit).
//   - Manual regression checks (local_fill on known-good dates).
//   - Integration testing against local Wrangler D1 + R2.

== Limitations
// TODO: NEW. Honest list. Suggested:
//   - ECR storage still incurs $0.10/mo (not truly zero-cost).
//   - [UPDATE from refreshed cost tables] — identify which service now
//     has the tightest free-tier headroom; Step Functions are gone so
//     the old "42.7% headroom" framing no longer applies.
//   - Daily cadence ceiling; no sub-daily updates.
//   - Sentinel-2 water-mask validation coverage.

// =============================================================================
// 9. Summary and Reflections
// =============================================================================
= Summary and Reflections

== Summary of Results
// TODO: bulleted recap of deliverables shipped.

== Discussion in Wider Context
// TODO: situate the work against:
//   - Other inland-water temperature monitoring systems.
//   - The broader trend toward serverless for scientific data pipelines.
//   - Open-data / reproducibility movement in environmental science.

== Implications for Stakeholders
// TODO: who benefits, how, and what would enable them to self-host or extend.

// =============================================================================
// 10. Project Management
// =============================================================================
= Project Management

== Work Plan
// TODO: Gantt chart or table mapping the six phases from the proposal to
// actual calendar weeks. Reference the interim §Timeline Assessment as the
// midpoint snapshot.

== Progress Against Plan
Progress against the six deliverables from the proposal is summarised below. Statuses are updated from the midpoint snapshot in the interim report.

// TODO: update the three statuses still marked _TODO_ before submission.
#figure(
  table(
    columns: (auto, auto, auto),
    table.header([*Deliverable*], [*Status*], [*Notes*]),
    "D1: Refactored codebase", "Complete", "SvelteKit + Terraform + Lambda",
    "D2: Sentinel-2 water mask", "_TODO_", "Verify before submission",
    "D3: CSV-based storage", "Complete", "R2 + D1 hybrid architecture; Parquet added (0018)",
    "D4: Interactive dashboard", "_TODO_", "Confirm advanced features complete",
    "D5: Landsat integration", "Complete", "lambda_functions/landsat",
    "D6: Technical documentation", "In Progress", "This report; user manual in Appendix A",
  ),
  caption: [Summary of deliverable status]
)

== Risk Management
// TODO: risks anticipated vs encountered (AppEEARS outages, free-tier limits,
// migration drift) and how each was mitigated.

== Resource Management
// TODO: tools used (uv, Terraform, Wrangler, GitHub Actions), credential /
// secret handling, cloud budget tracking.

// =============================================================================
// 11. Contributions and Reflections
// =============================================================================
= Contributions and Reflections

== Contributions
// TODO: enumerate value-adds:
//   - ~99.7% cost reduction via serverless replatform.
//   - Multi-sensor (ECOSTRESS + Landsat) fusion on free-tier infrastructure.
//   - Sentinel-2 water-mask verification pipeline.
//   - local_fill CLI — novel local development ergonomic for a cloud pipeline.
//   - Unified D1 data_requests model.
//   - Fully IaC-managed deployment.

== Innovation and Novelty
// TODO: what is genuinely new compared to the legacy SEGP system and the
// cited related work.

== Personal Reflection
// TODO: required by the rubric. Critical appraisal:
//   - What went well.
//   - What you would do differently (e.g. freeze the schema earlier).
//   - Skills developed (serverless, IaC, geospatial Python, SvelteKit).
//   - Supervisor / stakeholder collaboration experience.

== Future Work
// TODO: concrete next steps, e.g.:
//   - MODIS integration for a longer historical baseline.
//   - Automated anomaly detection / alerting.
//   - Extend to additional geographies.
//   - Public API documentation.

// =============================================================================
// Bibliography  (counts toward word/page limit per slide 8)
// =============================================================================
#bibliography("bibliography.yaml")

// =============================================================================
// Appendices (optional; NOT counted toward word/page limit)
// =============================================================================
#pagebreak()
#heading(numbering: none, level: 1)[Appendix A — User Manual]
// TODO: how to use the web app; how to run local_fill; how an admin
// triggers a backfill.

#pagebreak()
#heading(numbering: none, level: 1)[Appendix B — Developer / Deployment Guide]
// TODO: prerequisites, setup, terraform apply, wrangler deploy,
// environment variables, where credentials live.

#pagebreak()
#heading(numbering: none, level: 1)[Appendix C — Test Data and Results]
// TODO: sample outputs, screenshots of jobs dashboard, coverage tables.

#pagebreak()
#heading(numbering: none, level: 1)[Appendix D — Supporting Material]
// TODO: questionnaires, raw evaluation data, additional diagrams.
