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
#import "@preview/muchpdf:0.1.2": muchpdf

// -----------------------------------------------------------------------------
// Cover pages -- embedded from the submitted cover PDF
// -----------------------------------------------------------------------------
#{
  set page(numbering: none, margin: 0pt)
  if sys.inputs.at("cover", default: "") != "" {
   muchpdf(read(sys.input.at("cover"), encoding: none), width: 100%)
   pagebreak()
  }
}

// -----------------------------------------------------------------------------
// Acknowledgements
// -----------------------------------------------------------------------------
#heading(numbering: none)[Acknowledgements]

I would like to thank my supervisor, Dr Tomas Maul, for his guidance throughout the project. His feedback and regular check-ins helped keep the work focused and the design decisions well-reasoned.

I am grateful to Dr Matteo Redana, Dr Celine Chong and Prof Christopher Gibbins who provided the requirements for this platform and offered feedback throughout development. Their willingness to engage with the project on a regular basis through the weekly email updates made it possible to align the implementation with real operational needs.

Finally, this project would not have been possible without the foundation laid by the previous SEGP team led by Abdullah Usmani. Their initial web application established that satellite-derived surface temperature data could be visualised usefully in the browser, and it gave this project a clear starting point and a concrete problem to solve rather than a blank canvas.
#pagebreak()

// -----------------------------------------------------------------------------
// Abstract
// -----------------------------------------------------------------------------
#heading(numbering: none)[Abstract]

Surface water temperature is an important indicator for aquatic ecosystems, water quality, and climate-related change. A previous final-year project produced a web application for viewing satellite-derived temperatures for reservoirs and downstream rivers in Southeast Asia, but its long-term use was limited by recurring hosting costs, a manually operated retrieval workflow, ECOSTRESS-only coverage, and limited client-side exploration.

This dissertation transforms that proof-of-concept into an automated, multi-sensor observation platform. The redesigned system combines a Cloudflare-hosted SvelteKit frontend with AWS Lambda processing, direct STAC and Cloud-Optimised GeoTIFF ingestion, Cloudflare R2 object storage, D1 metadata, and Terraform-managed deployment. It adds Landsat 8/9 alongside ECOSTRESS, records per-pixel filtering reasons, and exposes public map, archive, dashboard, download, threshold-filtering, hover-inspection, and point-history workflows. Administrative users can monitor jobs, diagnose rejected pixels, adjust ingestion settings, and run historical backfills without editing code.

Evaluation shows that the new architecture meets the main operational goals. Recurring cost fell from the legacy \$30.00/month baseline to \$0.03/month for ECR image storage, a 99.9% reduction, while steady-state processing remains within free-tier limits. The production archive contains over 10,800 processed scenes across both sensors, with average per-scene processing times of 13.5 s for ECOSTRESS and 15.7 s for Landsat. A task-based survey of 25 students rated ease of finding temperature data 4.44/5 and overall usefulness 4.32/5, while two domain stakeholders rated insight usefulness and Landsat coverage 5/5.

The project improves access to and transparency of satellite-derived water-temperature observations, but it does not validate absolute temperatures against field measurements. The final platform is therefore best understood as a low-cost research-support tool for screening, exploring, exporting, and auditing observations, with filter statistics and no-data outcomes available to guide scientific interpretation.
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
Surface water temperature data is an important indicator for ecological research because it is used to model species distributions, track thermal habitat shifts, and improve biodiversity forecasts in lakes and rivers @lswt-ecology-prediction @lake-thermal-regions @river-temp-ecology. A web-based interface is useful because it makes the temperature records accessible to researchers and the general public without requiring them to download imagery, run geospatial processing scripts, or use specialist GIS software.

An existing application to access that data for lakes and rivers in Southeast Asia was developed under a previous SEGP project @segp. It ingested data from NASA's ECOSTRESS sensor @ecostress and had rudimentary visualisation features. While the original system functioned as a proof-of-concept, it was not suitable for continued use as a research platform. Data retrieval was manual and slow and hosting costs were not acceptable to the stakeholders. In addition, the interface had limited data exploration features @segp. 

== Aims
The overall aim was to transform the legacy system from a costly, manually operated proof-of-concept into a sustainable, automated, multi-sensor observation platform: re-architected on serverless cloud infrastructure, with an automated and extended ingestion pipeline, and a modern interactive frontend in place of the static server-rendered one.

== Objectives
The initial project proposal set six objectives @proposal. @objectives-status summarises their implementation status at the time of writing.

#figure(
  table(
    columns: (auto, auto),
    table.header([*Objective*], [*Status*]),
    [O1: Data storage & retrieval optimisation], "Implemented",
    [O2: Sentinel-2 water-mask verification], "Implemented via OPERA DSWx-HLS",
    [O3: Enhanced visualisation features], "Implemented",
    [O4: Multi-platform satellite integration], "Implemented",
    [O5: Zone differentiation], "Removed from scope",
    [O6: Code maintainability & documentation], "Implemented",
  ),
  caption: [Implementation status of the six project objectives]
) <objectives-status>

The original Sentinel-2 water-mask objective was delivered through a different route from the proposal. Instead of integrating the GAM4Water model, the final pipeline integrates NASA's OPERA DSWx-HLS surface-water product as an optional Landsat water mask. This product is derived from Harmonized Landsat Sentinel-2 surface reflectance, using Landsat OLI and Sentinel-2 MSI inputs @opera-dswx-hls @opera-dswx-atbd. Zone differentiation remained out of scope so that the final phase could prioritise the automated multi-sensor pipeline, water-mask integration, and production evaluation.


// =============================================================================
// 2. Motivation  (carried over from interim §Motivation)
// =============================================================================
= Motivation <motivation>

The project priorities were shaped through consultation with environmental research stakeholders who intended to use or maintain the system after handover. Dr Matteo Redana was the primary stakeholder and expected project recipient, with additional input from Dr Celine Chong Xin Yi and Professor Chris Gibbins. Their interest was not simply in a software prototype, but in long-term access to reliable reservoir temperature records. This made recurring cost, automated ingestion, and multi-sensor coverage central motivations for the redesign.

== Cost Reduction
One of the biggest limitations of the original system, as identified by stakeholders, was the hosting cost. The backend was hosted on Heroku and incurred US\$5/mo in costs @heroku-pricing. Data was stored on Supabase, whose Pro plan includes 100 GB of storage and starts from a US\$25 monthly plan; this was the tier assumed once the legacy system exceeded the 1 GB free storage allowance @supabase-pricing. The resulting US\$30/mo recurring cost was unacceptable for a research platform intended to be handed over for continued use.

== Data Retrieval Automation and Optimization

The original system ingested data via a script run manually on the developer's workstation, which was unacceptable for a platform whose value depends on continuous updates as new satellite observations are published. The script retrieved data via AppEEARS, NASA's web service for ordering analysis-ready remote-sensing data @appeears, took hours to run even for a single day, and required code edits to change dates or features fetched @segp.

== Single-Sensor Coverage
The legacy system only ingested data from the ECOSTRESS sensor. Because ECOSTRESS flies on the ISS, it revisits the same location at irregular times @ecostress-orbit, leaving unpredictable gaps that make it difficult for researchers to identify temperature trends or anomalies with confidence.

== Lack of Client-Side Interactivity
The legacy interface allowed only limited exploration: users could select a date and overlay colour mode and view a temperature overlay and histogram @segp, but could not inspect an individual pixel's temperature, filter pixels by temperature threshold, compare observations interactively, or query the temperature history of a fixed point on the map.

== Code Quality and Reproducibility
The original system had several maintainability issues: environment-specific configuration was hardcoded into application logic, and the local testing path differed from the version deployed on Heroku @segp. Error handling and logging were also limited, often producing cryptic failures or no useful diagnostic information.

In addition, cloud resources were created manually with little documentation, so a new maintainer could not reliably recreate the deployed environment. At handover, the deployed Heroku dyno was already in a crashed state, and the system had no automated recovery path.

// =============================================================================
// 3. Related Work
// =============================================================================
= Related Work <related-work>

== Analysis of the Existing System

The legacy system is the closest related work because it addressed the same problem domain: browsing satellite-derived reservoir temperature data through a web interface @segp. It demonstrated that ECOSTRESS observations could be processed into map overlays and shown to non-specialist users without requiring them to work directly with satellite products or GIS tools.

For this dissertation, the existing system therefore served as both a baseline and a set of design constraints to revisit. Since its limitations are already covered in @motivation, this chapter reviews technologies and approaches relevant to those gaps.

== Remote Sensing of Water Surface Temperature
=== Thermal Satellite Data Sources
Thermal satellites infer surface temperature from emitted infrared radiation rather than measuring water temperature directly. Their outputs are therefore best treated as remotely sensed surface-temperature estimates, with accuracy depending on atmospheric correction, cloud screening, land-water separation, and sensor resolution. For software systems that ingest and visualise these datasets, the most relevant sensor properties are the ones that affect acquisition scheduling, preprocessing, storage volume, and frontend interaction: spatial resolution, revisit pattern, and ease of automated access.

For environmental scientists, these data sources are most useful when they support questions about spatial and temporal patterns rather than isolated absolute readings. Surface-water temperature records can support analysis of thermal habitat, algal-bloom risk, stratification-related oxygen stress, and climate-driven changes in lakes and rivers @lswt-ecology-prediction @lake-thermal-regions @river-temp-ecology @reservoir-do-warming @hab-inland-waters. However, those uses depend on reliable filtering: cloud, land-water mixing, invalid retrievals, and areas the satellite did not observe must be excluded or clearly treated as missing data before the remaining pixels are interpreted as water-surface temperature.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    table.header([*Source*], [*Resolution*], [*Temporal pattern*], [*Main trade-off*]),
    "ECOSTRESS", "70 m", "Irregular ISS overpasses at varying local times", "Useful for diurnal observations, but less predictable for routine monitoring",
    "Landsat 8/9", "30 m", "Each satellite repeats every 16 days; pair offset by eight days", "Regular long-term record, but lower revisit frequency than MODIS",
    "MODIS", "1 km", "Daily", "High temporal frequency, but too coarse for many reservoirs",
  ),
  caption: [Comparison of thermal satellite data sources]
) <thermal-products>

ECOSTRESS provides land-surface-temperature estimates at 70 m resolution @ecostress-l2t. Its ISS orbit means observations occur at different local times @ecostress-orbit. Landsat 8 and Landsat 9 provide surface-temperature estimates through their Thermal Infrared Sensor products @landsat-c2-st, with a more predictable acquisition cycle @landsat-acquisition. MODIS provides a daily land-surface-temperature product, but its 1 km resolution is too coarse for the smaller reservoirs in this project @modis-lst.

=== Filtering Out Bad Pixels <water-masks>

Thermal satellite pixels cannot be used directly as water-temperature observations. A given pixel may correspond to land, represent a mixed land–water shoreline, be contaminated by cloud or cloud shadow, or contain a low-confidence temperature retrieval. To ensure reliable measurements, masks are applied: auxiliary datasets or algorithms that determine which pixels should be retained or discarded.

The most immediate source of masking information is the set of layers provided with the temperature product itself. ECOSTRESS includes quality-control, cloud, and water-mask layers; its cloud detection is based on a thermal Bayesian thresholding approach @ecostress-l2t @ecostress-psd. Similarly, Landsat Collection 2 provides a per-pixel quality band in which cloud, cloud shadow, snow, and water flags are derived using the CFMask algorithm @landsat-c2-st. These native masks are convenient because they are spatially and temporally aligned with the temperature data, but their accuracy is limited by the information available within a single observation.

External water-masking approaches improve classification by incorporating additional spectral, temporal, multi-sensor, or learned information beyond the thermal product itself. These approaches can be grouped by the kind of evidence or algorithm they add:

- *Spectral index methods* derive water masks directly from optical reflectance (e.g., NDWI and related indices). They provide scene-specific water detection but remain sensitive to threshold selection, shoreline mixing, and confusion with shadows or dark surfaces @ndwi @fisher-2016-water-indices.

- *Temporal or historical water datasets* use long-term observations to estimate water occurrence. The JRC Global Surface Water dataset aggregates decades of Landsat imagery to identify persistent water bodies @jrc-global-surface-water. These products are effective for defining stable water extents but may not capture short-term variability such as reservoir fluctuations.

- *Multi-sensor water classification products* combine observations from multiple sensors and/or time steps to improve robustness. NASA's OPERA Dynamic Surface Water Extent (DSWx) products generate 30 m water classifications from Harmonized Landsat–Sentinel-2 inputs (DSWx-HLS) or Sentinel-1 SAR (DSWx-S1) @opera-dswx-hls @opera-dswx-s1 @opera-dswx-atbd. DSWx-HLS has also been validated against high-resolution reference datasets @opera-dswx-validation. These products can reduce sensitivity to sensor-specific limitations by drawing on multiple inputs, but require alignment with the thermal observations.

- *Learned or statistical classification methods* train models from labelled or reference data rather than relying on a fixed index threshold. For example, GAM4Water uses generalised additive models for surface-water extent mapping @gam4water, while other studies compare machine-learning classifiers such as random forests and support vector machines for mapping complex water bodies @bangira-2019-complex-water. These methods can improve classification in complex scenes, but introduce training-data, validation, and inference requirements.

Cloud masking identifies clouds and cloud shadows that affect a single satellite scene, rather than a stable surface class like water. CFMask is widely used in Landsat processing and has been systematically evaluated against other operational approaches by Foga et al. @foga-2017-cloud. More recent convolutional neural network-based methods report improved performance, particularly in detecting cloud shadows, though at the cost of additional model complexity and input requirements @jeppesen-2019-cnn-cloud @wieland-2019-cnn-cloud.

== Compute Models for Periodic Batch Workloads
Traditional Virtual Private Servers (VPS) and other always-on hosting models charge for provisioned capacity continuously, creating idle cost when the system is neither processing data nor serving users. Adzic and Chatley (2017) show that for sporadic workloads, migrating to an execution-billed cloud model can reduce operational cost by minimising idle resource billing @serverless-computing. Periodic ingestion workloads — work that appears only when new data is published and arrives as many independent units that can be processed in parallel — are a natural fit for this model.

Several compute models compete in this space, with different trade-offs between idle cost, dependency flexibility, startup latency, and runtime caps:

- *Long-running workers (VM or always-on container).* A self-managed worker on a virtual machine, a Kubernetes deployment, or a PaaS dyno @heroku-pricing is the simplest model conceptually. Capacity is provisioned continuously, so idle cost is non-zero, but startup latency is also zero because workers are always warm.

- *Function-as-a-Service (FaaS).* AWS Lambda @aws-lambda is the canonical example: user code is packaged as a function and the platform invokes it once per event (HTTP request, queue message, scheduled trigger). Lambda accepts container images up to 10 GB and supports invocations of up to 15 minutes @aws-lambda-quotas, which accommodates native dependency stacks. The trade-off is cold-start latency when a fresh sandbox is initialised, on the order of hundreds of milliseconds to seconds depending on image size; recent literature surveys this trade-off across providers and mitigation strategies @faas-cold-start-survey.

- *Isolate-based serverless.* Cloudflare Workers @cloudflare-workers runs JavaScript in "V8 isolates" — lightweight sandboxes within a shared V8 process — with effectively zero startup cost. The execution environment is correspondingly constrained: no filesystem, no arbitrary binaries, and a strict CPU-time cap per request. The model favours short, latency-sensitive request handling over heavy data processing.

- *Serverless containers.* Google Cloud Run @cloud-run runs an arbitrary container image and scales automatically to zero when idle, billing per request and CPU-second. AWS Fargate @aws-fargate @aws-fargate-pricing runs ECS or EKS tasks without a managed cluster but does not scale to zero by default; ECS scheduled tasks @ecs-scheduled-tasks provide a periodic-launch variant for batch jobs. This category sits between long-running workers and FaaS — fewer runtime constraints than FaaS, but no native per-event invocation model, so a queue consumer must be supplied by the user.

- *Managed batch and stream platforms.* AWS Batch @aws-batch and Apache Spark are designed for long-running jobs over large static datasets, while Apache Kafka and AWS Kinesis @aws-kinesis target continuous, high-rate event ingestion. Both add orchestration overhead and target workloads at the extremes of the size/rate spectrum rather than periodic, modestly-sized batches.

#figure(
  table(
    columns: (3.5cm, auto, auto, auto, auto),
    table.header([*Property*], [*Long-running worker*], [*Serverless containers* \ (Cloud Run, Fargate)], [*Function-as-a-Service* \ (Lambda)], [*Isolate-based serverless* \ (Workers)]),
    "Idle cost", "Yes", "No", "No", "No",
    "Scales to zero", "No", "Yes", "Yes", "Yes",
    "Can run", "Any code", "Any container", "Any container (≤10 GB)", "Only JavaScript",
    "Cold start", "None", "Hundreds of ms - seconds", "Hundreds of ms - seconds", "Sub-millisecond",
    "Max runtime", "Unbounded", "Unbounded", "15 minutes", "Tens of seconds",
    "Parallel processing", "Manual", "Manual", "Native\n(Event Sources)", "Native (Queues)",
  ),
  caption: [Comparison of compute models for periodic, container-packaged batch work]
) <processing-strategies>

== Infrastructure as Code
When infrastructure is configured manually through interactive configuration tools such as cloud dashboards, the deployed environment can easily diverge from what was intended or documented. This may make reproducibility as well as failure recovery more difficult @infra-as-code. Infrastructure as Code (IaC) addresses this by treating infrastructure like the rest of the codebase: checked into version control, reviewed, and applied automatically.

All IaC tools follow a declarative execution model. The user describes the desired end state and the tool compares it to the current infrastructure, computing the changes to apply. They differ on two axes: scope and definition language. For scope, provider-specific tools like AWS CloudFormation @cloudformation and AWS CDK @aws-cdk tend to be updated more quickly and expose more features for their specific cloud provider, while provider-agnostic tools such as Terraform @terraform and Pulumi @pulumi can describe and manage resources across many platforms. In terms of definition language, AWS CloudFormation and Terraform define infrastructure in a dedicated configuration language (YAML or JSON for CloudFormation, HCL for Terraform), while AWS CDK and Pulumi are libraries used from a general-purpose programming language.

== Browser-Based Visualisation of Gridded Geospatial Data <browser-viz>
Visualising a per-pixel data layer such as a temperature raster in the browser typically combines a basemap that provides geographic context with an overlay that carries the data. 

Two open-source libraries are widely used. Leaflet @leaflet has been established since 2011 and renders using DOM and Canvas APIs, with a large plugin ecosystem built up over that time. MapLibre GL JS @maplibre is a more recent library that renders through WebGL and has native support for vector tiles.

The overlay layer itself admits several delivery strategies, each making a different trade-off between server-side preprocessing, network volume, and browser-side interactivity:

- *Pre-rendered raster overlays.* The server renders coloured image tiles for the data layer and the browser displays them as a tile source. The client-side implementation is straightforward, with the bulk of the work moved to the server-side tile rendering and storage; however, any interactive features such as filtering or switching the colour scheme require a roundtrip to the server, since the browser only has access to the rendered images and not to per-pixel data.

- *Vector tiles.* Geometry and attributes are encoded into a binary tile grid such as Mapbox Vector Tile @mvt-spec and rendered client-side, typically through MapLibre. This enables interactivity without a roundtrip to the server, but generating and storing the tile pyramid incurs processing and storage costs whose value is largely confined to browser visualisation. The format is also designed for vector geometry rather than dense raster grids: encoding a per-pixel temperature field as point or polygon features is awkward and inflates tile size compared to a true raster delivery format.

- *Client-rendered overlays.* Libraries such as deck.gl @deckgl upload geometry and attributes directly to the GPU and recolour or pick individual objects in the browser. There is no tiling step, but the full layer (or its visible portion) must be loaded into browser memory, so the approach scales by data volume rather than by viewport.

The appropriate strategy depends on what kind of interactivity is required, as well as how much server-side compute/storage can be sacrificed for smoother frontend performance.

== Open Formats for Tabular Data Archives
Per-pixel satellite observations over time form a tabular dataset: each row is one (pixel, date) pair carrying a value and supporting metadata. Several open file formats are candidates for archiving and serving such data on the public web, with different trade-offs in schema fidelity, compression, the ability to query a subset of the file without downloading it whole, and the breadth of tools that can read it.

- *Plain text formats.* CSV and JSON are universal, human-readable, and supported by virtually every tool out of the box. They carry no enforced schema or column types, compress poorly compared to binary alternatives, and require the consumer to download the entire file before any query can be evaluated.

- *Cloud-native columnar formats.* Apache Parquet @parquet-spec is a columnar binary file format designed for efficient analytical reads. Unlike row-oriented formats such as CSV, Parquet stores each column contiguously, which allows repeated values (such as longitude and latitude coordinates that recur across many observations) to compress heavily. Parquet files are subdivided into row groups, each with embedded min/max statistics that query engines can use to skip groups that do not match a filter, reducing the amount of data that must be downloaded.

- *Geographic feature formats.* GeoJSON @geojson and the more recent GeoParquet @geoparquet are designed for vector geometry, where each row carries an explicit feature shape (point, line, or polygon). They are well suited to discrete features such as administrative boundaries or point measurements, but a dense regular pixel grid maps awkwardly onto this model: every pixel must be encoded as its own feature, and the per-row geometry column repeats coordinate values that could otherwise be represented as a pair of plain numeric columns.


The format choice also constrains how the archive is queried at consumption time. Serving CSV or JSON typically requires either a server-side query endpoint that re-reads the file on each request, or a whole-file download into the browser. Parquet's row-group structure with embedded statistics enables a third option: columnar query engines compiled to WebAssembly, such as DuckDB-Wasm @duckdb-wasm, can run SQL directly in the browser and read Parquet files over HTTP range requests, fetching only the row groups that match a filter. This makes browser-side analytical queries practical without duplicating query logic in a server endpoint, while leaving the same files usable by any other Parquet-aware tool (pandas, R, Spark, the DuckDB CLI) for offline analysis.

// =============================================================================
// 4. Description of the Work  (NEW -- required by rubric, not in interim)
// =============================================================================
= Description of the Work <description>

The delivered system is a public web application and automated data pipeline for browsing, processing, and exporting surface-temperature observations from ECOSTRESS and Landsat for monitored water bodies.

== Functional Specification <functional-spec>
*Public (unauthenticated) users* can:

- Browse an interactive map of all monitored water bodies shown over satellite imagery.
- Select a feature and inspect its latest temperature observation as a per-pixel overlay.
- Toggle between ECOSTRESS and Landsat observations, filter by temperature threshold, and inspect point history.
- Download processed GeoTIFF and Parquet outputs, or export CSV files generated on demand from Parquet.

*Administrative users* additionally have access to:

- Job, request, and feature dashboards for monitoring processing status and data freshness.
- Per-scene filter statistics that explain why pixels were rejected.
- An on-demand backfill interface for arbitrary date ranges on either sensor.
- Settings for routine ingestion and catch-up behaviour.

== Non-Functional Requirements

- *Cost:* the system must operate within the free-tier limits of all cloud services used at expected steady-state volumes.
- *Reproducibility:* the system must be fully rebuildable from source by a new developer without manual environment setup or undocumented steps.
- *Observability:* administrators must be able to monitor pipeline health and diagnose failures.
- *Automation:* no manual step required for routine daily operation.
- *UI responsiveness:* per-pixel overlay rendering and threshold filtering must complete within one second of user interaction once observation data is loaded in the browser.
- *Mobile support:* the public viewer must be usable on mobile screen sizes without horizontal scrolling, and primary actions (map navigation, feature selection, point history inspection) must work with touch input.
- *Browser support:* the public viewer must perform correctly on current versions of Chrome and Safari, including their mobile counterparts.

== User Roles
Two user roles exist: public viewers, with unrestricted access to all visualisation and download functionality, and administrators, with additional access to the management and backfill pages. Administrative routes are protected by authentication; unauthenticated requests are redirected to a login page. Administrator accounts are invite-only.

// =============================================================================
// 5. Methodology
// =============================================================================
= Methodology <methodology>

== Development Methodology
Source code was managed with Git and hosted on GitHub. Development proceeded through small, self-contained changes, with larger features developed on short-lived branches before merging. A GitHub Actions workflow deployed the frontend, infrastructure, and Lambda image from the repository, making deployment repeatable rather than dependent on manual console changes.

Weekly progress emails were sent to the supervisor and external stakeholders throughout the project. Each update summarised completed work, planned work, and open questions, giving stakeholders regular opportunities to redirect priorities.

Key technical decisions were shared before implementation. Landsat integration was proposed to stakeholders in March 2026 before development began, and final-phase feedback redirected effort towards data-quality filtering rather than additional interface features.

== Technology Selection

=== Satellite Data Sources
ECOSTRESS remained the baseline sensor because it was already used by the legacy system and provides 70 m tiled surface-temperature products @ecostress-l2t. Its ISS orbit gives observations at varying local times @ecostress-orbit, but the revisit pattern is irregular compared with a sun-synchronous satellite.

Landsat 8/9 Collection 2 Level-2 Surface Temperature was added because it is freely distributed by USGS @landsat-c2-st and has a more predictable acquisition cycle: each satellite repeats every 16 days, with Landsat 8 and 9 offset by eight days @landsat-acquisition. This complements ECOSTRESS without introducing a paid data dependency.

MODIS @modis-lst was considered but rejected for this implementation because its 1 km thermal pixels are too coarse for the smaller reservoirs in the monitored set.

=== Data Access Strategy
The data-access choice was between keeping the legacy AppEEARS-mediated workflow and moving to direct catalogue-driven access. Direct access to cloud-hosted Cloud-Optimised GeoTIFFs (COGs) @cog-spec reduced orchestration complexity because the processor could read source assets directly rather than waiting for a separate order-and-download stage.

NASA and USGS both publish suitable catalogues through STAC (SpatioTemporal Asset Catalog) @stac-spec, a JSON-based catalogue standard for describing geospatial assets by time, footprint, and file links. ECOSTRESS scenes are discovered through `earthaccess` @earthaccess against NASA CMR-STAC, while Landsat scenes are discovered through `pystac-client` @pystac-client against the USGS STAC service. In both cases, `rasterio` @rasterio can open the returned COG assets with HTTP/S3 range requests.

Critically, the returned source assets are stored on AWS S3 in `us-west-2` region, a fact that directly informed the compute platform choice described in @data-processing-pipeline.

=== Storage
Temperature observations produce bulk files (GeoTIFFs, PNGs, and Parquet archives) as well as queryable metadata. The bulk files fit object storage better than a relational database, while dates, file paths, job states, and summary statistics remain relational. Cloudflare R2 was selected for object storage because it is S3-compatible, includes 10 GB-month of free storage, and does not charge egress fees @cloudflare-r2-pricing. This made it cheaper than the legacy Supabase Storage assumption and AWS S3 for the project's expected access pattern @supabase-pricing @aws-s3-pricing.

#figure(
  [#table(columns: 4, table.header([*Feature*], "Supabase Storage", [AWS S3 (`us-east-1` Region)], "Cloudflare R2"),
  "Free Tier Limit", "1 GB", "5 GB (for 12 months only)", "10 GB",
  "Monthly Storage Cost (over limit)", "$0.021/GB", "$0.023/GB (First 50TB)", "$0.015/GB",
  "Egress Fees", "$0.03/GB (over limit)", "$0.09/GB (over limit)", "Not Charged",
  "Minimum Monthly Spend", "$25 (over 1 GB)", "Pay-as-you-go", "Pay-as-you-go")],
  caption: [S3-compatible storage service comparison]
) <storage-comparison>

Cloudflare D1 was selected for relational metadata. Its free tier covers the metadata scale measured in @cloudflare-usage, while keeping the frontend API colocated with R2 and Cloudflare Pages @cloudflare-d1-pricing.

=== Data Processing Pipeline <data-processing-pipeline>
Both ECOSTRESS and Landsat source assets are hosted on AWS S3 in `us-west-2` region, and processing each scene requires repeated range reads against COG files. This made hosting the processor on AWS the efficient choice, as no egress fees are incurred if the processor is hosted in the same region. Additionally, latency inside the same AWS region is within single-digit milliseconds, much faster than the latency of a cross-provider HTTP request, which helps bring down total execution time and therefore cost if an execution-billed model is used.

Within AWS, Lambda @aws-lambda was selected because the workload arrives in scheduled batches, each scene can be processed independently, and there is no need to keep idle workers allocated between runs. Lambda supports container images up to 10 GB and 15-minute invocations @aws-lambda-quotas, which accommodates the native geospatial dependencies and per-scene processing time. Its free tier is evaluated against measured production usage in @aws-usage.

Amazon SQS provides the fan-out layer: each initiator emits one message per scene, and Lambda processes those messages in parallel.

=== Map Rendering
The frontend needs to display an interactive temperature pixel grid with hover, click actions, and threshold filtering. MapLibre GL JS @maplibre paired with deck.gl @deckgl was selected over Leaflet because its WebGL-based rendering model is better suited to responsive interaction over dense per-pixel temperature layers, allowing the browser GPU to draw and filter many points without creating one DOM/SVG object per pixel. Leaflet supports markers, polygons, GeoJSON, and raster overlays, but an interactive pixel-level temperature surface would require custom canvas/WebGL overlays and manual hit-testing. MapLibre and deck.gl provide a rendering model better suited to large geospatial layers with hover, click, and threshold filtering, where any interactive feature, such as filtering or switching the colour scheme, is handled in the browser without a server roundtrip (see @browser-viz). The accepted trade-off is reduced support for very old browsers, which is acceptable given the stakeholder browser profile of current Chrome and Safari.

=== Frontend/API Ecosystem
Cloudflare Pages is used to host the frontend and API. Static assets and API routes benefit from Cloudflare's global edge network, which Cloudflare reports places 95% of the Internet-connected population within 50 ms of a Cloudflare data centre, with most users within 20 ms @cloudflare-network. The Pages platform also keeps the frontend and API close to D1 and R2 on the same provider network, reducing the latency added by metadata and object-storage requests.

SvelteKit @sveltekit was selected because it combines Svelte's declarative component model with server-rendered pages, API routes, and an officially maintained Cloudflare adapter in one application framework.

=== DevOps and Infrastructure Strategy
The deployment strategy treats infrastructure and application delivery as repository-managed artefacts. Terraform defines AWS and Cloudflare resources in one configuration language @terraform, while GitHub Actions runs tests, builds the Lambda image, applies infrastructure changes, runs migrations, and deploys the SvelteKit frontend.

// =============================================================================
// 6. Design
// =============================================================================
= Design <design>

== High-Level Overview
The system architecture is divided into a serving zone and an ingestion zone. Cloudflare hosts the public application, API routes, metadata database, and object storage. AWS hosts the asynchronous ingestion pipeline that discovers new source scenes, processes them, and writes the resulting artefacts back to Cloudflare storage.

This split leverages the strengths of each provider. Cloudflare's global edge network ensures low-latency read access to static assets, the metadata and object storage, while AWS Lambda's per-message parallel invocation model can handle the heavy lifting of raster-processing tasks cost-effectively, due to the generous free-tier quotas and colocation to the source data.
#figure(
  image("High Level Overview.png", width: 100%),
  caption: [High-level system architecture]
) <high-level>

== Data Storage
The storage design separates queryable metadata from bulk observation artefacts.

*D1* stores structured metadata that needs to be queried and filtered:
- Feature metadata: water-body names, polygon identifiers, latest observation date.
- Per-observation summary statistics: min/max/mean/median/std temperature, pixel counts, per-flag rejection counts.
- Scene-level raster geometry: CRS, affine transform coefficients, pixel size.
- Job records: timestamps, duration, status, error message.
- Application settings.

*R2* stores the bulk per-pixel outputs for each observation:
- GeoTIFF raster.
- PNG visualisations.
- Parquet file per feature per year.


#figure(
  image("DB Schema.png", width: 100%),
  caption: [D1 database schema]
) <db-schema>

== Ingestion Pipeline
Both sensors share the same pipeline structure: trigger, catalogue search, queue fan-out, and shared processing.

1. *Trigger*. Scheduled runs start once per day; administrators can also submit a manual date/feature-specific backfill.

2. *Search and enqueue*. The initiator queries the relevant STAC catalogue, skips observations already recorded in D1, and emits one SQS message per missing scene.

3. *Process and store*. The shared processor clips each scene to the target feature, applies the quality filter stack described in @quality-control, writes derived artefacts to R2, and records metadata and filter statistics in D1.

#figure(
  image("EcoStress Updater Flow.png", width: 100%),
  caption: [Shared ingestion pipeline]
) <updater-design>

== Data Quality Design
The temperature pipeline is designed around a conservative interpretation of satellite-derived water temperature. A value is retained only when the source product marks it as usable, the pixel is classified as water, and the value remains plausible after physical-range and local spatial checks. The filtering sequence therefore removes common failure modes: invalid retrievals, cloud or cloud shadow, land and mixed shoreline pixels, missing source coverage, implausible temperatures, and isolated spatial anomalies.

This filtering is intentionally not presented as scientific validation. It improves the credibility of displayed values, but it can reduce spatial coverage and cannot remove every coherent error such as broad haze, sun glint, or a biased retrieval affecting neighbouring pixels together. The system design therefore records rejected-pixel causes instead of exposing only a cleaned raster. The final GeoTIFF and map layer show retained pixels, while the flag raster and `filter_stats` histogram preserve whether removed pixels failed because of cloud, non-water classification, missing source data, physical range, or spatial inconsistency.

This audit-trail design matters because different rejection reasons have different scientific meanings. A shoreline pixel removed as non-water, a cold patch removed as cloud shadow, and a pixel missing because the satellite did not observe that area all disappear from the final temperature map, but they should not be interpreted the same way when assessing gaps or anomalies.

== Frontend Design
The frontend is divided into three areas: the public map, a historical archive and public dashboard, and the administrative area restricted to authenticated users.

The public map is the primary interface for exploratory use. Users select a water body, inspect the latest observation, compare sources, filter by temperature threshold, and open point history from the map. The archive and dashboard provide secondary views for downloading historical outputs and scanning cross-feature freshness.

The public interface is designed for both desktop and phone-width use. On larger screens, the map, feature sidebar, date controls, and point-history panel can remain visible together; on mobile, controls collapse into drawers and full-screen panels so map inspection remains usable without horizontal scrolling. Keyboard shortcuts support repeated map workflows such as feature search, exiting a selected feature, and stepping between observations.

The administrative area gives pipeline operators visibility into system health without requiring access to AWS or Cloudflare consoles. It surfaces job status, per-scene filter statistics, per-water-body failure summaries, and a backfill interface for triggering on-demand ingestion.

All UI components are built with shadcn-svelte @shadcn-svelte, giving the interface a consistent component vocabulary across the public and administrative areas.

// =============================================================================
// 7. Implementation
// =============================================================================
= Implementation <implementation>
The implementation turns the design into three connected subsystems: a Cloudflare-hosted web application, an AWS processing pipeline, and a reproducible deployment path.

Cloudflare Pages runs the SvelteKit application and API routes. Those routes read D1 metadata and return R2 object keys, while static assets and generated observation files are served from R2. The processing code runs in AWS Lambda in a container with native Python libraries such as `rasterio`, `shapely`, and `pyarrow` for raster clipping, geometry operations, and Parquet output.

The Lambda side is deployed as one container image with different entry points for the ECOSTRESS initiator, Landsat initiator, and shared processor. Terraform assigns those entry points to separate Lambda functions while reusing the same ECR image for all three.

== Serverless Data Pipeline
=== Direct STAC/COG ingestion
The ECOSTRESS initiator uses `earthaccess` @earthaccess against NASA CMR-STAC, while the Landsat initiator uses `pystac-client` @pystac-client against the USGS Landsat STAC service. Each initiator discovers scenes for the monitored region, checks D1 for existing observations, and sends one SQS message for each missing feature/date/source combination.

In practical terms, STAC is used as the discovery layer rather than as the data store. The ECOSTRESS and Landsat initiators query by spatial footprint, time range, and collection, then extract source-product asset URLs: ECOSTRESS temperature, quality, cloud, and water bands; and Landsat surface-temperature, `ST_QA`, and `QA_PIXEL` assets. The Landsat initiator also includes the selected water-mask mode in the SQS message.

The processor opens source assets directly as Cloud-Optimised GeoTIFFs @stac-spec @cog-spec using the asset links returned by the catalogue search. Manual backfills call the same initiator functions through Lambda Function URLs, but optionally pass an explicit source, feature list and date range from the admin request.

=== Shared queue-driven processing
All scene-level work is handled by a single SQS-triggered processor Lambda. The queue message declares the source sensor, feature identifier, observation date, discovered scene asset links, and processing settings such as the Landsat water-mask mode. The top-level router dispatches the message to the matching ECOSTRESS, Landsat, or backfill handler.

The queue boundary also improves reliability. If the processor Lambda fails because of a timeout, out-of-memory error, transient dependency failure, or temporary Lambda unavailability, the failed SQS message is not deleted. After the visibility timeout expires, SQS makes it available for another Lambda invocation, and partial batch failure reporting ensures successful records in the same batch are not unnecessarily retried.

For each scene, the processor clips the raster to the target polygon, mosaics overlapping inputs when necessary, applies source-specific masks, runs common sanity checks, and writes processed outputs plus summary metadata. If a scene overlaps the polygon but yields no valid pixels, the job is marked as `nodata` rather than as a failure so operators can distinguish missing observations from broken pipeline execution.

=== Sensor-specific quality filtering <quality-control>
The two sensors differ mainly in how valid pixels are defined before the shared physical-range and spatial-outlier checks are applied. Here, product-native masks mean the quality, cloud, and water layers distributed with each temperature product; the underlying ECOSTRESS and Landsat masking algorithms are introduced in @water-masks.

#figure(
  table(
    columns: (auto, 1.6fr, 1.6fr),
    table.header([*Check*], [*Landsat 8/9*], [*ECOSTRESS*]),
    [Temperature validity],
    [`QA_PIXEL` fill; surface-temperature nodata; no `ST_QA` threshold],
    [Mandatory QA: best/nominal; data quality: not bad L1B],
    [Cloud mask],
    [`QA_PIXEL` cloud/shadow bits],
    [ECOSTRESS cloud layer],
    [Water mask],
    [`QA_PIXEL` water bit or OPERA `B01_WTR` @opera-dswx-hls],
    [ECOSTRESS water layer],
    [Fallback behaviour],
    [Landsat `QA_PIXEL` water bit if OPERA is unavailable],
    [None required],
  ),
  caption: [Sensor-specific first-stage filtering]
)

For ECOSTRESS, mandatory QA values `best` and `nominal` are accepted; `cloud detected` and `not produced` are rejected. Data-quality values are accepted unless they indicate missing or bad L1B input. The separate ECOSTRESS `LST` accuracy bits are kept for diagnostics rather than used as a rejection threshold, because validation scenes showed that accepting only the highest accuracy category removed plausible water observations.

For Landsat, `QA_PIXEL` contains confidence information and the Collection 2 surface-temperature product also includes an `ST_QA` uncertainty band. The current implementation does not threshold those graded fields. It rejects fill and missing temperature pixels, then uses the `QA_PIXEL` cloud, cloud-shadow, and water flags unless OPERA is enabled for water classification.

OPERA DSWx-HLS is used as an optional enhanced water mask rather than as a proven replacement for every Landsat scene. Its advantage is that it is a validated Level-3 water product @opera-dswx-validation and implements the five-test DSWE decision rule on Harmonized Landsat–Sentinel-2 inputs, classifying each pixel as open surface water, partial surface water, or not water rather than using only the single-scene `QA_PIXEL` water bit @opera-dswx-atbd. When OPERA is enabled, the Landsat processor performs a separate CMR search for the matching `B01_WTR` raster, opens the returned tile or tiles, reprojects the categorical OPERA raster to the Landsat temperature grid, and treats open-water and partial-surface-water classes as retained water pixels.

The spatial check is a local Hampel identifier over a 5x5 window. It computes a neighbourhood median and median absolute deviation using only pixels that survived earlier masks, then rejects a pixel when its deviation exceeds the robust threshold. A 2 K minimum deviation floor is used so that very smooth water surfaces do not cause harmless product-noise differences to be labelled as outliers. This is a mitigation for isolated contamination, not a guarantee of scientific accuracy: broad haze, warm inflow plumes, or real thermal gradients can be spatially coherent and therefore require human interpretation or independent validation.

The filter results are preserved as a per-pixel bit-flag raster and summarised into `temperature_metadata.filter_stats`. This gives the administrative dashboard an explanation layer rather than only a binary success/failure outcome.

The flags are stored as bit positions rather than as mutually exclusive classes. A single rejected pixel can therefore carry multiple reasons, for example both cloud and non-water, while the displayed temperature layer simply hides all pixels with any rejection bit set. The `filter_stats` summary counts how many pixels had each bit set, allowing the admin interface to show dominant rejection causes without loading the full flag raster.

#figure(
  table(
    columns: (auto, auto, auto),
    table.header([*Bit*], [*Meaning*], [*Applied from*]),
    "0", "Sensor quality-control rejection", "ECOSTRESS QC checks; Landsat invalid/fill state",
    "1", "Cloud rejection", "ECOSTRESS cloud band; Landsat QA_PIXEL cloud bits",
    "2", "Non-water rejection", "Sensor-native water mask",
    "3", "No-data / missing-coverage rejection", "Missing or zero-valued raster cells",
    "4", "Out-of-range temperature rejection", "Shared physical range check",
    "5", "Spatial outlier rejection", "Shared Hampel neighbourhood test",
    "6", "OPERA non-water rejection", "OPERA DSWx-HLS water mask on Landsat runs",
  ),
  caption: [Per-pixel filter flags]
) <processor-code-filter>

== Storage and Data Delivery
=== Hybrid D1 and R2 storage
D1 stores the queryable index and operational record: features, observations, job records, data requests, settings, summary statistics, filter histograms, raster geometry, and R2 object keys. R2 stores the bulk rasters, previews, and Parquet archives.

API routes first query D1, then use the returned R2 keys to serve or link the corresponding GeoTIFF, PNG, and Parquet objects.

=== Columnar temperature storage
The main storage change compared to the legacy system is the move from CSV archival data to year-sharded Parquet as the sole per-pixel storage format. No separate CSV archive is written; when users request CSV output, the frontend generates it on demand from Parquet using DuckDB-WASM's built-in export.

Parquet addresses two implementation goals at once. It compresses repeated coordinate columns more effectively than plain CSV, and it can be queried directly in the browser through DuckDB-WASM @duckdb-wasm without adding a server-side time-series API. 

The parquet files are split (sharded) into multiple files to balance compression and browser loading behaviour. The shard key was chosen empirically rather than by convention. Test archives were generated for the largest monitored features and densest observation histories to compare compression and browser loading behaviour. Sharding by feature and date produced files that loaded quickly, but compressed poorly due to no repeated latitude/longitude columns. Only sharding by feature meanwhile provided the best compression ratio, but over time would grow unbounded to potentially hundreds of megabytes for the largest features. Ultimately, sharding by feature and year was chosen as a compromise: repeated latitude/longitude columns compressed well across many observations while keeping the largest Landsat shards at roughly 50 MB.

The measured storage and cost effects of this design are evaluated in @cost-summary and @cost-projection.

=== Derived artefacts
Each successful observation produces three forms of output. GeoTIFF is retained as the highest-fidelity processed raster for export and GIS inspection. PNG previews provide immediate visual feedback in the web application. Parquet stores the queryable per-pixel archive used for point history and on-demand CSV export.

== Public Web Application
=== Interactive map and overlay rendering
The public map composes MapLibre GL JS @maplibre and deck.gl @deckgl in the same view. MapLibre renders the basemap and monitored water-body polygons. Upon loading the feature, the application first adds the PNG preview as a lightweight raster layer, then replaces it with a deck.gl overlay as soon as Parquet data loads for pixel-level interactivity.

When a feature is selected, the route state determines the active feature, source, date, temperature unit, map view, and selected point. Those values are mirrored into URL search parameters so a specific view can be refreshed or shared without losing context.

#figure(
  image("map-interface.png", width: 90%),
  caption: [Public map interface]
) <map-interface>

=== Browser-side point-history queries
The feature sidebar and point-history panel use the same Parquet archive rather than a dedicated server endpoint per query. Once the relevant shard is available, DuckDB-WASM runs in the browser and retrieves the time series of the nearest pixel to the selected map point. Stored raster row, column, CRS, and affine-transform metadata allow the frontend to highlight the corresponding pixel footprint on the map.

This approach moves repeated point-history queries out of the backend after the initial file fetch. The implementation constraint is bundle size: DuckDB-WASM binaries are large, so the final implementation loads the WASM assets from a CDN rather than bundling them into the SvelteKit output @cloudflare-pages-limits. The resulting panel is shown in @point-history.

=== Responsive layout for mobile
The mobile implementation uses the same feature and observation state as the desktop map, but swaps layout containers at phone-width breakpoints. Map overlay controls collapse into a bottom drawer, and the point-history view opens as a full-screen modal instead of a side-anchored panel (@mobile-views).

=== Historical archive and public dashboard
The archive supports detailed export for a single feature, including on-demand CSV generation from Parquet. The dashboard supports cross-feature scanning by showing latest observation status, recent trend, source, and freshness.

#figure(
  image("historical-archive.png", width: 80%),
  caption: [Historical archive page]
) <historical-archive>

#figure(
  image("public-dashboard.png", width: 80%),
  caption: [Public dashboard]
) <public-dashboard>

== Administrative Tooling
=== Authentication and protected routes
The administrative area is protected with Auth.js @authjs using AWS Cognito @cognito as the identity provider. Cognito handles login and token issuance, while the SvelteKit server hook protects `/admin/*` pages and `/api/admin/*` endpoints. This keeps operational tooling behind a normal web login without requiring administrators to use the AWS or Cloudflare consoles.

=== Operational monitoring views
The administrative UI reads the operational state already recorded in D1. Jobs, requests, feature summaries, filter statistics, thumbnails, failures, and catch-up settings are exposed through SvelteKit admin routes and API endpoints.

#figure(
  image("admin-dashboard.png", width: 80%),
  caption: [Administrative jobs dashboard]
) <admin-dashboard>

#figure(
  image("admin-diagnostics.png", width: 80%),
  caption: [Administrative diagnostics view]
) <admin-diagnostics>

=== Ingestion settings
The settings page exposes the small number of pipeline parameters that operators may need to adjust without redeploying code. Catch-up controls govern how scheduled ingestion recovers from short upstream outages: an enable toggle, an overlap window that re-checks recent dates for late-published granules, and a maximum automatic catch-up window that bounds how far back a single scheduled run will go. These are the operator-facing surface of the catch-up mitigation discussed in @projectmgmt.

The Landsat water-mask mode selector chooses between the sensor-native `QA_PIXEL` water bit and the OPERA DSWx-HLS product as the source of the water classification used by the Landsat processor. The selected mode is propagated through the SQS message into the processor (see @quality-control) and recorded against each resulting observation, so the rejected-pixel breakdown surfaced on the diagnostics view distinguishes OPERA-driven non-water rejections (bit 6 in @processor-code-filter) from `QA_PIXEL`-driven ones (bit 2).

#figure(
  image("admin-settings.png", width: 80%),
  caption: [Administrative settings page exposing catch-up controls and the Landsat water-mask mode]
) <admin-settings>

=== Manual backfill interface
The backfill interface is a control-plane layer over the same ingestion workflow. An administrator chooses a source and date range; the admin API records the request in D1, signs the Function URL call, and triggers the appropriate initiator. Manual runs bypass automatic catch-up logic so operators can reprocess an exact historical interval.

#figure(
  image("admin-backfill.png", width: 60%),
  caption: [Manual backfill interface]
) <admin-backfill>

== Security Model
The system applies different trust boundaries to its public and administrative surfaces. The public map and API endpoints are unauthenticated by design: all data they expose is already publicly available from NASA and USGS, and no user data is collected. The administrative area is protected at the SvelteKit server hook level, which redirects unauthenticated requests before any D1 or R2 access occurs.

Backfill triggers cross from the Cloudflare admin API into AWS through signed Lambda Function URL requests using `aws4fetch` @aws4fetch. The signing user can invoke only the initiator functions, while Lambda execution permissions are scoped to queue access, image pull access, and the storage/database bindings required by the processor. R2 buckets remain private, and Earthdata credentials are injected through deployment secrets rather than committed source files.

Network-level abuse protection is inherited from the hosting platform rather than implemented in application code. Public traffic is fronted by Cloudflare's edge network, which provides automatic DDoS mitigation and bot management for all traffic served through it @cloudflare-ddos @cloudflare-bot-management. The public surface is limited to read-only API calls against D1 and Parquet downloads from R2, neither of which incur egress charges, so abuse cannot cause write-side damage or egress cost. Workers requests and D1 row-reads are metered, but edge mitigation absorbs malicious traffic before it reaches application code, and the steady-state headroom against the relevant free-tier limits (see @cloudflare-usage) is large enough that ordinary traffic spikes do not approach paid usage.

At the application layer, all D1 SQL queries use the parameterised version of the `.bind()` API and administrative endpoints validate their inputs before any side effect.

== Deployment Automation <cd-pipeline>
Infrastructure provisioning is implemented declaratively in Terraform @terraform across AWS and Cloudflare. GitHub Actions supplies the deployment path: Python dependencies are locked with `uv` @uv, exported to `requirements.txt`, baked into an AWS Lambda Python 3.12 Docker image, tagged with the commit SHA and `latest`, and pushed to ECR. Terraform then updates the Lambda functions to reference the current ECR image digest, while a separate frontend job builds the SvelteKit application, applies D1 migrations, and deploys the Pages bundle.

Alongside production deployment, the `local_fill` CLI supports development and debugging by running either processor in-process for one feature/date pair. It can write to local Wrangler-managed D1/R2 stores or to the cloud runtime, making the processing path testable without scheduled triggers or queue fan-out.

// =============================================================================
// 8. Evaluation
// =============================================================================
= Evaluation <evaluation>

The evaluation considers cost, automation and observability, data quality and coverage, performance, and user experience, followed by testing, requirements traceability, and limitations.

== Cost Analysis
Cost was evaluated as a recurring operational constraint rather than only as a deployment expense. The aim was to determine whether the platform could be handed over for long-term use without requiring stakeholders to maintain a paid server or storage subscription. The analysis therefore compares the fixed monthly cost of the legacy architecture against measured and projected usage from the implemented serverless architecture.

=== Legacy System Costs
The interim report identified the legacy Heroku and Supabase deployment as the main cost risk for long-term operation @interim-report. That architecture incurred fixed monthly costs regardless of actual usage:

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

The legacy system stored per-pixel outputs as uncompressed CSV files. While no storage growth projections were provided in the SEGP report @segp, the interim report measured 0.77 GB for one month of ECOSTRESS output @interim-report. On that basis, the legacy storage path is estimated to grow by approximately 0.77 GB/month. This would exceed Supabase's 1 GB free storage allowance after roughly six weeks of continuous operation, before any Landsat integration or larger historical backfill.

=== New System: AWS Usage
The data processing pipeline runs on AWS Lambda with SQS-based fan-out. AWS usage was recalculated from the manual monthly backfill runs used to populate the two-year archive, rather than from routine timer runs. These backfills queued 13,492 ECOSTRESS scenes for 2024-04-21 to 2026-04-21 and 14,973 Landsat scenes for 2024-05-01 to 2026-04-21.

Steady-state usage was projected from the same backfill records by averaging per-scene Lambda durations across all process jobs with recorded durations (6.1 s/scene for ECOSTRESS across 11,952 scenes over 730 days; 10.1 s/scene for Landsat across 17,270 scenes over 720 days) and multiplying the implied daily scene rates by 30 days at the 3 GB memory allocation. @aws-usage shows both the measured backfill totals and the resulting steady-state estimates against free-tier limits.

#figure(
  table(
    columns: (auto, auto, auto, auto, auto, auto),
    table.header([*Service*], [*Free Tier Limit*], [*Backfill Usage*], [*Backfill Util.*], [*Steady-State Usage*], [*Steady-State Util.*]),
    "Lambda (compute)", "400,000 GB-sec/mo", "~755,000 GB-sec", "~188.8%", "~30,700 GB-sec", "~7.7%",
    "Lambda (requests)", "1,000,000 req/mo", "29,269 invocations", "~2.9%", "~1,300 requests", "~0.13%",
    "SQS", "1,000,000 req/mo", "29,222 messages", "~2.9%", "~1,200 messages", "~0.12%",
  ),
  caption: [AWS usage: two-year manual backfill totals and projected steady-state monthly usage @aws-lambda-pricing @aws-sqs-pricing]
) <aws-usage>

The backfill workload exceeded the monthly Lambda compute free tier, while request and SQS volumes remained far below their monthly free-tier limits. At AWS Lambda's x86 price of \$0.0000166667 per GB-second after the free tier @aws-lambda-pricing, the measured compute overage is approximately \$5.92 if attributed to a single billing month. This is a one-time archive-population cost; routine scheduled ingestion sits comfortably within all free-tier limits.

Amazon ECR (Elastic Container Registry) does not have a perpetual free tier for the project's private repository storage. ECR private repositories are billed at \$0.10/GB-month @aws-ecr-pricing. The current image is 326 MB, giving an actual ECR cost of approximately \$0.03/month.

=== New System: Cloudflare Usage
The frontend, API, and storage layer run entirely on Cloudflare's edge network. @cloudflare-usage shows the measured usage against free-tier limits; figures are from the December 2025 interim window. R2 storage has grown since then with the addition of Parquet files and expanded Landsat coverage, but the removal of redundant gzipped CSV files (which previously accounted for approximately 6 GB) brought storage back well within the free tier.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    table.header([*Service*], [*Free Tier Limit*], [*Actual Usage*], [*Utilisation*]),
    "Workers (requests)", "100,000/day", "133/day avg", "0.1%",
    "R2 (storage)", "10 GB", "3.9 GB", "39%",
    "R2 (Class A ops)", "1,000,000/mo", "~7,300 ops", "~0.7%",
    "R2 (Class B ops)", "10,000,000/mo", "5,700 ops", "0.06%",
    "D1 (rows read)", "5,000,000/day", "2,400/day avg", "0.05%",
    "D1 (rows written)", "100,000/day", "167/day avg", "0.2%",
  ),
  caption: [Cloudflare usage against free-tier limits]
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
After removing redundant gzipped CSV files, R2 storage stands at approximately 3.9 GB (39% of the 10 GB free tier). Steady-state ingestion adds approximately 0.29 GB per month, derived from the two-year backfill averages in @aws-usage combined with the measured per-scene stored output size. This projection excludes one-off historical backfills. At this growth rate, R2 storage remains within the free tier for approximately 21 months. @cost-projection shows the projected costs alongside the fixed ECR charge; no R2 overage is incurred within the 12-month window.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    table.header([*Period*], [*Legacy System*], [*New System*], [*Cumulative Savings*]),
    "1 Month", "$30.00", "$0.03", "$29.97",
    "3 Months", "$90.00", "$0.09", "$89.91",
    "6 Months", "$180.00", "$0.18", "$179.82",
    "12 Months", "$360.00", "$0.36", "$359.64",
  ),
  caption: [Projected 12-month cost comparison]
) <cost-projection>

In steady-state operation the new architecture reduces recurring cost from \$30.00/month to \$0.03/month (ECR image storage only), a 99.9% reduction. The measured two-year manual backfill exceeded the monthly Lambda compute free tier by approximately 355,000 GB-seconds, corresponding to roughly \$5.92 of one-time compute overage @aws-lambda-pricing. R2 storage is projected to remain within the free tier for approximately 21 months from April 2026; beyond that point, overage would accrue at \$0.015/GB-month @cloudflare-r2-pricing. The backfill charge does not recur during normal scheduled operation.

== Automation and Observability
The new architecture also changes how ingestion and failures are operated.

=== Automation Improvements
The legacy system required manual intervention for every routine update: a developer modified script parameters, executed the retrieval code locally, and monitored an AppEEARS server-side task that took hours to complete. The new pipeline removes the developer from the routine path entirely. Scheduled ingestion, on-demand administrative backfill, parallel scene processing, and local reprocessing for investigation are all available without code changes (see @cd-pipeline and @implementation for the underlying mechanisms).

An equivalent routine ECOSTRESS workload (31.6 scenes per daily run across all monitored features) now completes end-to-end in approximately five minutes with no manual step, against hours-to-days for the legacy AppEEARS path. Short source-catalogue delays are absorbed by the next scheduled catch-up run rather than requiring a manual rerun.

=== Observability Improvements
The new system records every pipeline execution in D1 with timestamps, status codes, per-bit filter statistics and error messages, and surfaces this through the admin dashboard (@admin-dashboard) without requiring AWS Console access. Failed scenes are logged with enough context for targeted reprocessing, and the historical record supports trend analysis and capacity planning. By contrast, the legacy system had no structured logging or job tracking: failures were only discovered by manually inspecting output files or noticing that expected data was absent from the interface.

== Data Quality and Coverage <filter-stats>
Production filter statistics provide direct evidence of how much source data survived the pipeline and why rejected pixels were removed. Because each processed scene records per-bit rejection counts, the evaluation can distinguish missing coverage, non-water classification, cloud rejection, and shared range or spatial checks rather than reporting only a final accepted-pixel percentage.

Temporal coverage was the primary motivation for adding Landsat. The production job records provide a direct comparison: Landsat contributed 7,540 processed scenes against ECOSTRESS's 3,341 over the same monitoring window, a 2.3× increase in total scene ingestion. Because Landsat's 16-day orbital repeat is offset from ECOSTRESS's variable revisit schedule, the two sensors often cover the same feature on different days.

The aggregate filter statistics from the production database illustrate how sparse the accepted data is relative to the raw input. Across 3,341 ECOSTRESS scenes totalling 313 million pixels, only 11.4% of pixels are accepted; the equivalent figure for 7,540 Landsat scenes (3.2 billion pixels) is 9.5%. The dominant rejection causes are non-water classification and no-data or missing coverage: sensor tiles are large relative to the water bodies being monitored, so the majority of each clipped raster is land, and a significant additional fraction is made up of pixels that the satellite did not observe on that pass. Cloud cover, which is frequent in the tropical Southeast Asian environments the platform monitors, is a further major contributor; its rejection rate varies considerably by season and feature.

From an environmental-science perspective, these figures have two implications. First, the system should be used as an observation archive with explicit missingness rather than as a continuous sensor stream. A water body may have no usable observation on a given pass because of cloud, incomplete satellite coverage, or water-mask failure. Second, the accepted-pixel percentages are not evidence that the system is discarding "too much" data: much of the rejected area is land outside the reservoir, shoreline mixture, or pixels with no valid satellite measurement. The useful measure for a researcher is therefore not raw acceptance rate alone, but whether the retained pixels form a spatially plausible water surface and whether the rejection pattern is understandable.

The displayed values are screened remote-sensing estimates rather than direct field measurements; the platform exposes accepted-pixel counts, per-bit rejection breakdowns, and per-scene diagnostics to support interpretation of missingness.

== Performance <performance>
The main performance improvement is architectural: direct STAC and COG access removes the AppEEARS order-and-poll stage, and SQS fan-out allows many processor instances to run in parallel. Measured against production job records, individual ECOSTRESS scenes complete in 13.5 s on average (7–48 s range across 4,268 jobs) and Landsat scenes in 15.7 s (5–294 s range across 12,785 jobs). With 50 concurrent workers, a full month of ECOSTRESS across all monitored features (750 to 1,050 scenes) processes in approximately five minutes. The largest recorded backfill, 1,271 Landsat scenes covering two months (December 2025 – January 2026), completed in under seven minutes. The legacy AppEEARS workflow required submitting a task to NASA's servers and waiting hours to days before data was available for download; the same data volume now takes minutes from trigger to stored result.

The 50-worker ceiling is not a Lambda or SQS constraint (both could sustain far higher concurrency) but a D1 one: Cloudflare D1 serialises all writes through a single writer, so concurrent processor invocations compete for the same lock. Raising the concurrency cap beyond 50 produced sporadic write failures in integration testing (see @implementation). The pipeline is therefore bottlenecked on the metadata store rather than on compute, and a migration to a database that supports concurrent writers would directly translate into faster backfill throughput.

On the read path, the visible delay is concentrated in Parquet shard download rather than in the general interface. Static assets, API metadata responses, and PNG previews are served from Cloudflare's edge network and appear quickly; users see a pre-generated preview while the Parquet shard downloads in the background. For smaller features and ECOSTRESS shards this transition is fast, but the largest Landsat annual shards reach approximately 50 MB and can produce a noticeable wait on slower connections. This is an intentional trade-off: loading Parquet shards to the client directly avoids maintaining a server-side time-series query API, reducing storage and server-compute cost. Once the shard is loaded, threshold filtering, hover tooltips, palette switching, and point-history queries run locally in deck.gl and DuckDB-WASM.

== User / Stakeholder Evaluation

=== Ongoing Stakeholder Engagement
The external stakeholders (Dr Matteo Redana, Dr Celine Chong, and Prof Christopher Gibbins) had access to the live deployment throughout the project and provided feedback iteratively via the weekly email updates described in @methodology. Cloud account ownership was transferred to the external stakeholder during the project so the system can continue operating after handover.

=== Stakeholder Evaluation
Two domain stakeholders completed a structured evaluation after using the final deployment. They rated the platform on the same five-point scale used in the general user survey, with additional questions targeting environmental usefulness, Landsat integration, per-pixel history, and administrative observability. Because there were only two responses, @stakeholder-evaluation presents the individual scores rather than summary statistics.

#figure(
  table(
    columns: (auto, auto, auto),
    table.header([*Question*], [*Stakeholder 1*], [*Stakeholder 2*]),
    "Ease of finding temperature data", "5", "5",
    "Ease of exploring historical data", "5", "5",
    "Loading speed", "4", "5",
    "Visual design", "5", "4",
    "Usefulness", "5", "5",
    "Useful insight into water-temperature patterns", "5", "5",
    "Landsat improves temporal coverage", "5", "5",
    "Per-pixel inspection and time-series history sufficient", "4", "5",
    "Admin interface gives sufficient pipeline visibility", "4", "5",
    "Recommendation likelihood", "5", "5",
  ),
  caption: [Stakeholder evaluation results]
) <stakeholder-evaluation>

The qualitative responses align with the system's main design priorities. The most valuable features identified were data download and the reservoir-name search bar, indicating that both research export and navigation were useful to stakeholders. The requested future improvements were updated wetted-area filtering and a more attractive welcome page. The former reinforces the scientific limitation discussed in @filter-stats: the current masks make rejected pixels visible and auditable, but further work on water-area filtering remains valuable before the platform is used for stronger environmental claims. The latter is a lower-risk presentation improvement that would not change the core data pipeline.

=== User Survey
A task-based usability survey was conducted with 25 participants recruited from the University of Nottingham Malaysia student body. Participants were asked to explore the live deployment and complete representative tasks: browsing the map, selecting a water body, reading the current observation, toggling between ECOSTRESS and Landsat, inspecting pixel temperatures, opening point history, and adjusting threshold and palette controls. Following the walkthrough, participants rated five aspects of the platform on a five-point scale and provided an overall recommendation likelihood score. @usability-survey summarises the descriptive results.

#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    table.header([*Question*], [*Mean (n=25)*], [*Median*], [*Min*], [*Max*]),
    "Ease of finding temperature data", "4.44", "4", "3", "5",
    "Ease of exploring historical data", "4.20", "4", "3", "5",
    "Loading speed", "4.12", "4", "2", "5",
    "Visual design", "4.44", "5", "3", "5",
    "Usefulness", "4.32", "5", "2", "5",
    "Recommendation likelihood", "4.48", "5", "3", "5",
  ),
  caption: [Usability survey results]
) <usability-survey>

Written feedback clustered around five themes: clearer onboarding or instructions for new users; comparison between multiple water bodies; more space or clarity for the temporal trend chart; more contextual information about each water body, such as river name and location; and a public commenting or verification mechanism.

The lowest individual score remained loading speed (one respondent rating 2/5). This is consistent with the Parquet trade-off discussed in @performance: the general interface and previews load quickly, but large annual Parquet shards can take longer before full per-pixel interaction and point-history queries are available.

*Limitations.* The survey used a sample of 25 University of Nottingham Malaysia students, rather than the platform's intended users (reservoir operators and ecological researchers). The results are therefore indicative of general usability rather than domain-expert acceptance.

== Testing
The data pipeline is covered by 105 passing Python unit tests. They cover processor logic, ECOSTRESS and Landsat quality masks, catch-up and duplicate handling, raster clipping and mosaicking, database helpers, Parquet slicing, and local processor arguments. The frontend passes TypeScript and Svelte component checks with zero errors or warnings. Manual checks on the live deployment covered map interaction, source switching, threshold filtering, per-pixel inspection, point-history queries, and downloads. Each path was exercised on Chrome and Safari on macOS, Safari on iOS, and Chrome on Android, covering both desktop and mobile layouts. These checks confirm that all items in the functional specification (@functional-spec) were delivered and are accessible to the appropriate user roles.

== Requirements and Objectives Traceability

@traceability maps each retained objective and non-functional requirement to the primary evidence in this report and records the delivery result.

#figure(
  table(
    columns: (auto, auto, auto),
    table.header([*Requirement / Objective*], [*Evidence*], [*Result*]),
    [O1: Data storage & retrieval optimisation],
      [Hybrid R2+D1 store; Parquet-only per-pixel archive; on-demand CSV export; storage and read usage measured in @cloudflare-usage and @cost-projection],
      [Met],
    [O2: Sentinel-2 water-mask verification],
      [OPERA DSWx-HLS integrated as an optional Landsat water mask; product derived from Harmonized Landsat Sentinel-2 inputs; per-run and global controls available in the admin workflow],
      [Met],
    [O3: Enhanced visualisation features],
      [Manually checked pixel inspection, threshold filtering, browser-side point history, and per-observation downloads],
      [Met],
    [O4: Multi-platform satellite integration],
      [7,540 Landsat scenes processed alongside 3,341 ECOSTRESS scenes; source selection available in UI; @filter-stats],
      [Met],
    [O6: Code maintainability & documentation],
      [Terraform IaC for all cloud resources; 105 passing backend tests; zero frontend type-checking errors; Appendices A and B (user and deployment guides); repository developer documentation],
      [Met],
    [Cost NFR (<\$5/month recurring)],
      [Steady-state recurring cost \$0.03/month (ECR only); <\$0.05/month including projected R2 overage; @cost-summary, @cost-projection],
      [Met],
    [Automation NFR (no manual ingestion)],
      [Daily scheduled ingestion, source-catalogue catch-up, SQS fan-out, and administrative on-demand backfill],
      [Met],
    [UI responsiveness NFR (interactions \<1 s)],
      [Threshold, hover, palette, and point-history interactions run locally after the relevant Parquet shard has loaded; @performance],
      [Met],
    [Observability NFR],
      [Admin dashboard shows per-job status, duration, thumbnail, and filter-flag breakdown; failed scenes logged with reprocessing context; no AWS Console access required; see Automation and Observability section],
      [Met],
  ),
  caption: [Requirements and objectives traceability]
) <traceability>

== Limitations
A small residual cost of \$0.03 per month remains for ECR container-image storage (the current image is 326 MB at \$0.10/GB-month) @aws-ecr-pricing. R2 storage sits at approximately 3.9 GB after the removal of redundant CSV files, with roughly 6.1 GB of headroom before the 10 GB free-tier limit. At the current growth rate of ~0.29 GB/month, overage is not expected for approximately 21 months.

The scientific limitation is more important than the operational one. The platform improves access to screened satellite-derived surface-temperature estimates, but it does not validate those estimates against in-situ measurements. OPERA DSWx-HLS adds a validated external option for Landsat water masking, but it is still a satellite-derived classification rather than field truth, and ECOSTRESS continues to use its co-acquired native water band. The Hampel and physical-range checks reduce visible artefacts but cannot detect all coherent cloud, haze, or retrieval-bias cases. Environmental use should therefore treat the system as a screening and exploration tool until a formal validation study compares accepted pixels against independent water masks and field measurements.

// =============================================================================
// 9. Summary and Reflections
// =============================================================================
= Summary and Reflections <summary>

== Summary of Results
The project implemented five of the six proposed objectives and removed the zone-differentiation stretch objective from scope in consultation with the supervisor. The platform became operationally sustainable, automated for routine ingestion, multi-sensor rather than ECOSTRESS-only, and substantially more interactive for end users. Evaluation showed recurring cost reduced to \$0.03/month (see @cost-summary), while users gained OPERA-backed Landsat masking, per-pixel inspection, threshold filtering, archive downloads, and point-history queries in the browser.

The most important qualification is that the project improves the delivery and transparency of satellite-derived observations; it does not convert those observations into field-validated water-temperature measurements. The final system is therefore best understood as a research-support platform for screening, exploration, and export, with filter evidence available to guide interpretation.

== Implications for Stakeholders
For reservoir operators and ecological researchers in Southeast Asia, the practical implication is that the platform no longer depends on paid always-on hosting for routine operation. Because the stack is defined in Terraform and documented in the repository, a successor maintainer can more readily reproduce the infrastructure in their own Cloudflare and AWS accounts. The local reprocessing path and the on-demand backfill interface together mean that filling gaps in historical coverage, for example after a sensor outage, does not require editing the scheduled ingestion code.

For environmental scientists, the practical implication is more cautious: the platform can help identify candidate warm events, inspect spatial temperature patterns, and export records for external modelling, but it should be paired with field data or independent masks before supporting strong ecological claims. This is why the system records rejected-pixel causes and no-data outcomes rather than presenting every missing or filtered pixel as a normal map gap.

// =============================================================================
// 10. Project Management
// =============================================================================
= Project Management <projectmgmt>

== Work Plan
Project work was organised into two phases. The first phase, weeks 1 to 11, focused on the non-functional foundations identified during requirement elicitation: replacing the paid legacy stack, automating ECOSTRESS ingestion, and defining infrastructure in Terraform. The second phase, weeks 12 to 26, built on that foundation with Landsat integration, browser-side visualisation, the administrative dashboard, and the Parquet storage path.

== Progress Against Plan
Progress against the proposal is reported in the objectives table in @objectives-status and the traceability table in @traceability. In project-management terms, the main change was that zone differentiation was removed from scope, while the storage, automation, Landsat integration, visualisation, and documentation work were completed.

== Risk Management
The main operational risk that remains outside the system's control is upstream data availability. Both ECOSTRESS and Landsat are external satellite products, so the pipeline can only process observations after NASA CMR or USGS STAC has published the corresponding catalogue items and source assets. This risk materialised during final deployment, when ECOSTRESS catalogue searches temporarily returned no recent granules for the monitored region even though the scheduled ingestion job itself was healthy. Without additional handling, that kind of provider-side delay would appear as a silent data gap.

The implemented mitigation is to make scheduled ingestion catch up from the latest already processed observation to the latest date currently visible in the source catalogue, with configurable overlap and a maximum automatic catch-up window. This means a short ECOSTRESS or Landsat publication outage does not require code changes or a manual rerun: when the missing granules appear, the next scheduled run will enqueue any unprocessed observations. For longer gaps, the administrative backfill interface and local reprocessing tools provide manual recovery paths without changing the scheduled job configuration.

== Resource Management
The main project resources that required active operational management were cloud spend and deployment credentials. Cloud spend was controlled with billing alerts in both AWS and Cloudflare, so unexpected cost growth from backfills, storage growth, or deployment activity would be surfaced while the platform was still operating against free-tier constraints. In practice, this monitoring confirmed that recurring cost stayed negligible, with the only non-zero steady-state charge being the ECR image-storage cost reported in @cost-summary.

Credential management was handled through GitHub Actions secrets. AWS access keys, Cloudflare API tokens, Earthdata credentials, and R2 keys were stored as repository secrets and injected into the deployment workflow as environment variables or Terraform inputs at runtime, rather than committed to the repository.

// =============================================================================
// 11. Contributions and Reflections
// =============================================================================
= Contributions and Reflections <contributions>

== Contributions
The project's primary contribution is an operational architecture for satellite-derived temperature data that remains inexpensive, reproducible, and maintainable after student handover. Rather than treating cost as an optimisation after implementation, the architecture uses Cloudflare R2 for low-cost object storage, Lambda for scheduled geospatial processing, and Terraform for reproducible multi-provider infrastructure. The result is a recurring steady-state cost of \$0.03/month (see @cost-summary), compared with the legacy \$30/month baseline.

The second contribution is the browser-side analysis path. Rather than exposing a server-side time-series API, per-pixel data is archived as year-sharded Parquet and queried in the browser through DuckDB-WASM. This keeps the archive accessible in a standard analytical format, avoids duplicate CSV storage, and reduces backend compute.

The third contribution is the filter-explainability layer. Each processed observation records why pixels were rejected, rather than exposing only a final valid/invalid mask. This is a software contribution with scientific relevance: it helps users distinguish between no observation, poor observation, and a plausible temperature pattern that deserves further analysis.

== Personal Reflection

The main lesson from the project is to revisit inherited assumptions early. At the start, I treated the previous system's AppEEARS-based retrieval workflow as a fixed constraint because it was already part of the legacy implementation. Later research showed that the same ECOSTRESS data could be discovered and read through STAC and cloud-hosted raster files, which made the pipeline much faster and simpler. If I were starting again, I would spend more time in the first weeks checking whether each inherited design choice was still necessary.

The second lesson is that scarcity can produce better designs. The strict cost constraint ruled out a conventional server-side analytics service, which pushed the project towards Parquet and DuckDB-WASM for browser-side point-history queries. That solution was more novel than the design I would probably have chosen without the constraint. The same was true for year-based Parquet sharding: finding a balance between load time and compression ratio became an important design problem rather than just a storage detail.

The third lesson is that stakeholder communication has to be designed into the project. The weekly email updates introduced in February made progress, blockers, and trade-offs visible, helped keep expectations realistic, and made it easier to align on priority changes such as Landsat integration and data-quality filtering. I think this regular communication contributed to the strong stakeholder evaluation because stakeholders were involved throughout the decision-making process rather than only shown the final product.

The main challenge was the breadth of unfamiliar material. Environmental remote sensing was not my domain, so I had to learn the satellite and GIS terminology, work with geospatial processing libraries, and build an interactive map interface at the same time. The infrastructure work added another learning curve because the final system spans both AWS and Cloudflare. The project therefore required more independent research than a conventional web application, but that breadth also made the final result more valuable.

== Future Work
The most useful follow-on work would extend the platform in seven directions:

- *Cloud Mask Improvement.* The current pipeline uses cloud masks built into the satellite product. Future work can evaluate CNN-based cloud masks such as `ukis-csmask` @ukis-csmask, whose underlying approach has been evaluated against FMask (the default cloud mask in the Landsat satellite product) for multi-sensor cloud and cloud-shadow segmentation @wieland-2019-cnn-cloud.
- *Local ingestion integration harness.* The data ingestion logic is unit-tested, but the processing code depends on AWS SQS and Lambda. Emulating those services locally would allow future developers to test the entire system end-to-end without a cloud round-trip.

- *MODIS integration.* A third, coarser-resolution sensor would extend the historical baseline; it would slot naturally into the existing source-aware processing design, at the cost of not resolving smaller reservoirs.
- *Automated anomaly detection and alerting.* The admin dashboard surfaces failures passively; a once-per-day check that posts to an email or messaging service when any feature has gone more than N days without a successful observation would close the observability loop.
- *Broader geographic coverage.* The pipeline is polygon-driven with no regional assumptions, so extending beyond Southeast Asia is primarily a data-management task.
- *Public API documentation.* Documenting the public API with OpenAPI would make the processed archive easier for third-party researchers to consume directly.
- *Broader domain-expert evaluation.* A larger follow-up evaluation with reservoir operators and environmental scientists could test end-to-end research tasks: identifying candidate thermal events, interpreting missing observations, using filter statistics, exporting data, and deciding when field confirmation is needed.

// =============================================================================
// Bibliography  (counts toward word/page limit per slide 8)
// =============================================================================
#bibliography("bibliography.yaml")

// =============================================================================
// Appendices (optional; NOT counted toward word/page limit)
// =============================================================================
#pagebreak()
#heading(numbering: none, level: 1)[Appendix A: User Manual]

*Browsing temperature data.* Open the deployed site at the project URL. The landing page shows a map of all monitored water bodies overlaid on satellite imagery. Click any polygon to open the feature's most recent observation: the temperature raster appears as a coloured overlay, and the sidebar shows the observation metadata (date, source, min/max/mean temperature). Hover a pixel to see its exact temperature in a tooltip; right-click a pixel to open a drawer with its time series across all available dates on the currently selected source. Use the date scrubber at the bottom of the sidebar to step between dates, and the source toggle to switch between ECOSTRESS and Landsat. The threshold slider re-colours only pixels within the chosen temperature band, and the colour-palette selector switches between relative, fixed and greyscale renderings. Downloads (GeoTIFF, Parquet, and on-demand CSV) are available from the sidebar for the current observation.

*Administrative access.* Administrators sign in at `/admin/login` using Cognito credentials issued by the project maintainer. Once signed in, `/admin/jobs` shows every processing job with its status, duration, thumbnail and per-bit filter statistics; `/admin/requests` lists every scheduled and on-demand ingestion run, and the "New Request" dialog triggers an on-demand backfill for a chosen source and date range; `/admin/features` aggregates job counts per water body; and `/admin/settings` controls scheduled catch-up behaviour, including whether catch-up is enabled, the overlap days to rescan, and the maximum automatic catch-up window.

*Running a local backfill.* After cloning the repository and installing dependencies (`npm install`; `cd lambda_functions && uv sync`), seed NASA Earthdata credentials into `~/.netrc` or `EARTHDATA_USERNAME`/`EARTHDATA_PASSWORD` environment variables. To run a single (feature, date) against the production D1 + R2: `cd lambda_functions && uv run python -m local_fill --source ecostress --feature NamTheun2 --start-date 2026-03-15`. To run against the Wrangler-local store, add `--runtime local` and first run `npm run r2:seed:local`.

#pagebreak()
#heading(numbering: none, level: 1)[Appendix B: Developer / Deployment Guide]

*Prerequisites.* Node 20, `uv` for Python, Terraform, the `wrangler` CLI (installed by `npm install`), and access to: a Cloudflare account with Pages, R2 and D1 enabled; an AWS account with permissions for Lambda, SQS, ECR, IAM, Cognito and CloudWatch; and a NASA Earthdata Login.

*One-time setup.* Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars` and fill in the required variables (Cloudflare account/API token, R2 credentials, Earthdata username/password, AWS region, and Pages settings). Run `terraform -chdir=terraform init`, then `terraform -chdir=terraform apply`. This provisions the AWS side (Lambdas, SQS queue, ECR repository, IAM role and user, Cognito user pool, and CloudWatch Event Rules) and the Cloudflare side (R2 bucket, D1 database, and Pages project). After provisioning, confirm that `wrangler.toml` contains the active D1 database binding and R2 bucket binding.

*Initial data load.* Apply the D1 schema with `npm run db:migrate:remote`. Trigger a first ingestion by either waiting for the scheduled daily trigger or calling `/admin/requests` with a manual date range.

*Routine deployment.* Every push to `main` triggers the GitHub Actions workflow described in @cd-pipeline, which runs tests, builds and pushes the Docker image, applies Terraform, applies pending D1 migrations, and deploys the SvelteKit frontend. No manual steps are required in steady state.

*Local development.* The README and `docs/LOCAL_DEVELOPMENT.md` describe the current local workflow. In short, run `npm install`, seed local D1 with `npm run db:export` and `npm run db:seed`, seed local static R2 assets with `npm run r2:seed:local`, then use `npm run wrangler:dev` for a Cloudflare-compatible local app. Processor debugging uses `uv run python -m local_fill` from `lambda_functions/`, with `--runtime local` for Wrangler-local D1/R2.

*Secrets.* The NASA Earthdata username and password, the Cloudflare API token and account ID, and the R2 access key and secret are stored as GitHub Actions secrets and passed through Terraform variables. They are *not* checked into the repository. Local development uses a repo-root `.env` for processor credentials and a `.dev.vars` file for local Auth.js/Cognito and Cloudflare Pages bindings; `scripts/setup-dev-auth.sh` helps create the local auth values.

#pagebreak()
#heading(numbering: none, level: 1)[Appendix C: Supplementary Screenshots]

This appendix collects supplementary screenshots referenced from the Implementation chapter.

#figure(
  image("point-history.png", width: 68%),
  caption: [Point-history panel]
) <point-history>

#figure(
  grid(
    columns: 3,
    column-gutter: 6pt,
    image("mobile-homepage.png", height: 10cm),
    image("mobile-feature-drawer.png", height: 10cm),
    image("mobile-point-history.png", height: 10cm),
  ),
  caption: [Public interface on a phone-width viewport: map view, feature drawer, and point-history modal]
) <mobile-views>
