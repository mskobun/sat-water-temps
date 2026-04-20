#set page(margin: 2.5cm, numbering: "1")
#set text(size: 11pt, font: "Times New Roman")
#set par(justify: true)
#show raw: set text(font: "FiraCode Nerd Font")
#show raw.where(block: true): set par(justify: false)
#set heading(numbering: "1.1")
#import "@preview/oxdraw:0.1.0": *

// Title page
#align(center)[
  #set page(numbering: none)
  #text(size: 14pt)[University of Nottingham Malaysia
  
  School of Computer and Mathematical Sciences]


  #align(horizon)[
  #text(size: 14pt)[Interim Report]

  #text(size: 28pt, weight: "bold")[Satellite Water Temperature Web Application Enhancement]

  
  #text(size: 14pt)[Maksim Skobun
  
  Supervised by Dr. Tomas Maul]
  ]

  #align(bottom)[
    #text(size: 14pt)[December 2025]
  ]
]

#pagebreak()
#outline()
#pagebreak()

= Introduction
Surface water temperature is a critical environmental indicator influencing aquatic ecosystems, water quality, and climate-related processes. However, in Southeast Asia, there remains a lack of continuous, high-resolution monitoring of inland water temperatures. The existing Satellite Water Temperature Web Application, developed under a previous SEGP project, was designed to visualize near–real-time temperature data derived primarily from NASA's ECOSTRESS sensor @ecostress. This system enables users to explore spatial and temporal variations in reservoir and downstream river temperatures, supporting research in hydrology, ecology, and climate impact studies.

While the original system demonstrated the concept, there are several limitations that hinder its real-world use. The data retrieval process is inefficient and manual, taking many hours to complete and requiring modifying the code to adjust the data retrieval parameters. In addition, the system relies on paid-tier hosting for the data storage and retrieval, threatening the long-term sustainability of the project. Consequently, the immediate priority of this project is to establish a robust, zero-cost infrastructure that can support the advanced visualization features planned for the final release. This project aims to address these limitations by implementing a modern serverless architecture with an automated, observable data processing pipeline that runs on free-tier hosting.

= Motivation

== Cost Reduction

A critical limitation of the original system is the cost of hosting. The backend was hosted on Heroku and incurred a monthly cost of \$5, while data was stored on Supabase which would have incurred a monthly cost of \$25 once more than 1 month of historical data was stored. This was identified as a major limitation by the stakeholders, who were concerned about the long-term sustainability of the project.

== Data Retrieval Automation

The original system relies on a script that has to be run manually to retrieve the temperature data from AppEEARS (Application for Extracting and Exploring Analysis Ready Samples) @appeears, NASA's web service for accessing remote sensing data including ECOSTRESS. The script takes hours to run, requires modifying the code to adjust the data retrieval parameters and does not log failed processing attempts.

== Code Quality and Reproducibility

The original system is written in Python and contains many anti-patterns and a lack of documentation. File paths and parameters are hardcoded and not easily configurable. While the documentation contains deployment instructions, it is not comprehensive and does not cover all the details of the system.

= Related work
== Analysis of the existing system
The primary point of reference for this project is the existing system developed by the SEGP project team @segp. The system demonstrated the feasibility, but suffered from suboptimal architecture decisions that hindered its scalability and maintainability.


+ *Monolithic architecture*: The backend was built as a monolithic Flask application hosted on Heroku. This is convenient for development, but means it incurred constant hosting costs, regardless of usage. The cheapest Heroku server, or "dyno" as Heroku refers to them costs \$5/mo @heroku-pricing. More powerful and expensive "dynos" might be required as the system gets used by more users.
+ *Storage constraints*: The system used Supabase Storage to store temperature data and images. The free tier of Supabase allows for 1GB of storage, which is not enough to store historical temperature data for more than a month. In addition, Supabase's pricing structure only allows to purchase additional storage in a bundle of 100GB for \$25/mo @supabase-pricing, which is in excess of what is needed and would significantly increase the cost of keeping the system running.
+ *Manual Data Processing Pipeline*: The script to fetch new data from AppEEARS is not automated or run on any cloud, unlike the rest of the system. Fetching new satellite data requires a developer to modify the script's code and run it on their local machine. The script sequentially downloads and processes data for hundreds of features, taking hours to run.
+ *Fragile Client-Side Logic*: The frontend is built using "vanilla JavaScript", making heavy use of manual DOM manipulation. This imperative approach tightly couples the logic to the specific HTML structure. As noted in modern software engineering literature, this pattern leads to brittle codebases where minor UI changes break functionality, making the addition of complex interactive features hard to maintain.
== Evaluation of Serverless Architecture
Traditional Virtual Private Servers (VPS) or Platform as a Service (PaaS) solutions like Heroku charge for reserved compute capacity, resulting in idle costs even though the system is not processing data or serving users. Adzic and Chatley (2017) demonstrate that for sporadic workloads, migrating to a serverless model can significantly reduce operational costs by minimizing idle resource billing @serverless-compiuting. "Function-as-a-Service" (FaaS) model allows the system to scale up when processing new batches of data, as well as scale to zero when not serving any users, ensuring the project operates entirely within free-tier limits.

In addition to idle cost, traditional architectures require reserving resources in specific physical locations, creating a tradeoff between latency and cost of keeping idle servers in as many regions as possible. Modern FaaS platforms like Cloudflare Workers solve this: the function code is stored in every "edge" location of their Content Delivery Network (CDN) @cloudflare-workers. User's requests are then routed to the closest "edge" location, where a server almost instantaneously loads the function code and processes the request, ensuring superior latency anywhere in the world.

== Infrastructure as Code
A significant limitation in many software projects is the "reproducibility crisis." The legacy system relied on manual environment setup ("ClickOps"), a practice Morris (2016) identifies as a primary cause of "configuration drift" and deployment failure @infra-as-code.

To solve this, Infrastructure as Code (IaC) software can be used. With it, the infrastructure can be treated as normal code: checked in to version control, rolled back, redeployed to multiple environments. Terraform is the industry standard IaC solution, having plug-ins for every major cloud service provider.

= Methodology
== Requirement Elicitation

A meeting was held with stakeholders to review the limitations of the current system. It was established that data reliability and low-cost deployment were the highest priority non-functional requirements. Therefore, it was decided to dedicate Phase 1 entirely to replatforming the system to zero-cost cloud solutions and automating the data processing pipeline. 

== Technology Selection
=== Storage
The architectural design process was initially driven by the need to resolve the storage cost bottlenecks of the legacy system. Researching alternatives to Supabase's S3-compatible storage, Cloudflare R2 stood out with the free plan offering 10GB of data storage and zero egress fees, meaning no matter how many downloads from the storage will be done, they will not be charged for. In addition, even over the limit – R2 has cheaper monthly storage costs than any of the alternatives compared.

#figure(
  [#table(columns: 4, table.header([*Feature*], "Supabase Storage", [AWS S3 (`us-east-1` Region)], "Cloudflare R2"),
  "Free Tier Limit", "1 GB", "5 GB (for 12 months only)", "10 GB",
  "Monthly Storage Cost (over limit)", "$0.021/GB", "$0.023/GB (First 50TB)", "$0.015/GB",
  "Egress Fees", "$0.03/GB (over limit)", "$0.09/GB (over limit)", "Not Charged",
  "Minimum Monthly Spend", "$25 (over 1 GB)", "Pay-as-you-go", "Pay-as-you-go")],
  caption: "Comparison of S3-compatible storage services (USD)"
)

=== Frontend/API Ecosystem
Following the selection of R2, it made natural sense to use Cloudflare Workers for serving frontend files and API endpoints. Workers are hosted on the same Cloudflare network, ensuring superior latency and are integrated into Cloudflare's ecosystem, allowing easy linking of R2 buckets to the workers. Free plan of Workers allows up to 100 thousand requests daily, which is well within system requirements.

=== Data Processing Pipeline
While a pure Cloudflare solution would have been better for simplicity, Workers face strict limits on execution time and memory. In the Free tier, these limits are 10ms of CPU time per request and 128MB of memory. While this is enough for serving JSON APIs and frontend files, it is unsustainable for processing data from ECOSTRESS. AppEEARS itself is quite slow, often taking tens of minutes to process a request and several seconds to download one of the resulting files.

Therefore, a workflow based on AWS Lambda was chosen @aws-lambda. A Lambda function can be any Docker image and can run up to 15 minutes. Coupled with other AWS technologies like Step Functions and SQS (Simple Queue Service) a complex data processing workflow can be built in a serverless fashion. Lambda also has a generous free tier of 400 thousand GB-seconds a month (where GB is the memory allocated to the Lambda), which is more than enough for a pipeline that updates from ECOSTRESS data daily.

=== DevOps and Infrastructure Strategy

To address the "configuration drift" and reproducibility issues identified in the legacy system, the project adopted a strict Infrastructure as Code (IaC) methodology. Given the requirement of supporting both AWS and Cloudflare platforms, Terraform was the only suitable solution. Terraform's provider-agnostic architecture allows to define the entire stack in a unified language. 

The project utilized a "GitOps" framework @gitops, where the Git repository was used as the single source of truth for deploying both infrastructure and code changes. A GitHub Actions pipeline was set up to automatically update the code and apply Terraform changes on commits to the production branch.
= Design
== High-Level Overview
The system architecture, as shown in @high-level, is divided into two zones. Cloudflare zone handles synchronous user requests that simply retrieve data from the database and object storage and display it to the user. AWS zone on the other hand is responsible for asynchronously processing new data from AppEEARS and updating the database and object storage.
#figure(
  [#image("High Level Overview.png")],
  caption: "High-Level System Architecture"
) <high-level>
== Data Storage
The system uses both Cloudflare R2 object storage and D1 SQL database. D1 database is used for fast access to feature metadata, as well as storing processing logs for the ECOSTRESS updater. R2 is used to store pixel-level temperature readings as well as tif/png visualizations.

While it is possible to store temperature data in D1 since it is a CSV file, doing so is impractical. Each CSV has thousands of rows and it is always accessed in a predictable pattern (load all of them at once). Since D1 charges per row read/written, keeping the CSV files and creating a "pointer" to it in the metadata table is more efficient.

#figure(
  [#image("DB Schema.png")],
  caption: "D1 Database Schema"
)
== ECOSTRESS Updater

ECOSTRESS Updater is responsible for fetching and processing new data from AppEEARS into the system. The pipeline is as follows:
1. *Daily Trigger*: A CloudWatch Event Rule triggers the *Initiator Lambda* daily at 00:00 UTC. The *Initiator Lambda* submits a task to AppEEARS to collect information for regions of interest.
2. *Asynchronous Polling*: Since AppEEARS processing times are unpredictable, taking from minutes to sometimes hours, an AWS Step Function is used to wait for the request to complete. The Step Function calls the *Status Checker Lambda*, which polls AppEEARS whether the task is done. If yes, the pipeline goes to the next step, otherwise the Step Function will retry with exponential backoff @exponential-backoff (doubling the wait time between attempts each time). Using a Step Function with backoff prevents "busy waiting" and minimizes compute costs during long delays.
3. *Task Fan-Out*: Once the AppEEARS task is done, the *Manifest Processor Lambda* retrieves the file list. Instead of processing files sequentially, it implements a "Fan-Out" pattern: it splits the task into individual "scenes" (combination of area ID + date) and pushes a message for each scene into an *SQS Queue*. This decouples retrieval from processing, allowing multiple *Processor Lambdas* to fire in parallel, significantly reducing total pipeline runtime.
4. *Parallel Processing*: The *Processor Lambda* consumes messages from the *SQS Queue*. For each scene it downloads all the data for the scene from AppEEARS, processes the data and uploads the results and metadata to R2 and D1 respectively.
#figure(
  [#image("EcoStress Updater Flow.png")],
  caption: "Internal Logic of ECOSTRESS Updater"
) <updater-design>
= Implementation 
== Infrastructure as Code
All cloud infrastructure for this project is defined using Terraform configuration files, enabling reproducible deployments and version-controlled infrastructure. The Terraform codebase manages resources across both AWS and Cloudflare platforms from a unified configuration.

The Cloudflare resources are defined declaratively, as shown in @terraform-cloudflare. Similarly, AWS Lambda functions, IAM roles, SQS queues, and Step Functions are all provisioned through Terraform, ensuring that the entire infrastructure can be recreated from scratch or replicated to a new environment with a single command.

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
caption: [Terraform configuration for Cloudflare resources]
) <terraform-cloudflare>

== Data Processing Pipeline
The ECOSTRESS data processing pipeline is implemented as a series of AWS Lambda functions orchestrated by AWS Step Functions. All Lambda functions are packaged into a single Docker image deployed to Amazon Elastic Container Registry (ECR), with each function having a different entry point. Docker packaging was necessary because the processing code depends on geospatial libraries such as `rasterio` and `geopandas`, which require native C libraries (GDAL, libcurl) that cannot be installed via standard Lambda deployment packages.

=== Initiator Lambda
The pipeline begins with the *Initiator Lambda*, triggered daily by a CloudWatch Event Rule. This function authenticates with AppEEARS and submits a data request for all regions of interest defined in the GeoJSON file. Upon successful task submission, it starts the Step Function state machine to monitor the request (@initiator-code).

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
caption: [Initiator Lambda handler]
) <initiator-code>

=== Step Function State Machine
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
caption: [Exponential backoff state definition]
) <stepfn-backoff>

=== Manifest Processor Lambda
Once AppEEARS marks the task as complete, the *Manifest Processor Lambda* retrieves the file manifest and implements a Fan-Out pattern. Files are grouped by "scene" (combination of area ID and date), and each scene is pushed as a separate message to an SQS queue. This decouples manifest processing from data processing, enabling parallel execution.

=== Processor Lambda
The *Processor Lambda* is triggered by SQS messages and performs the core data processing. For each scene, it:
1. Downloads all raster files (LST, LST_err, QC, water mask, cloud mask, etc.) from AppEEARS
2. Applies quality filters by masking invalid QC values and cloud-contaminated pixels
3. Generates filtered GeoTIFF and CSV files containing temperature data
4. Creates PNG visualizations with multiple color scales (relative, fixed, grayscale)
5. Uploads all outputs to Cloudflare R2 storage
6. Inserts metadata records into Cloudflare D1 database

The core filtering logic is shown in @processor-code.

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
caption: [Processor Lambda data filtering and upload]
) <processor-code>

== Hybrid Storage Architecture
The system employs a hybrid storage architecture to optimize both cost and performance:

*Cloudflare D1* (SQLite-based serverless database) stores:
- Feature metadata (location names, latest dates)
- Temperature statistics per observation (min/max/mean temperature, pixel counts)
- Processing job logs for observability
- R2 file paths pointing to the actual data

*Cloudflare R2* (S3-compatible object storage) stores:
- Raw temperature CSV files with pixel-level readings
- Processed GeoTIFF rasters
- PNG visualizations at multiple color scales

This separation ensures D1 stays within free-tier row limits while R2 handles bulk data storage with zero egress fees.

== Frontend Implementation
The frontend is built with SvelteKit and deployed to Cloudflare Pages. SvelteKit's server-side rendering capabilities are leveraged through Cloudflare's edge runtime, with API routes defined as TypeScript server endpoints that query D1 and R2 directly (@sveltekit-api). The main interface (@map-interface) displays an interactive satellite map with clickable polygons representing monitored water bodies.

#figure(
  image("map-interface.png", width: 90%),
  caption: [Main map interface showing monitored water bodies in Southeast Asia]
) <map-interface>

#figure(
```typescript
export const GET: RequestHandler = async ({ params, platform }) => {
  const db = platform?.env?.DB;
  const dates = await getFeatureDates(db, featureId);
  return json(dates, { headers: { 'cache-control': 'public, max-age=120' } });
};
```,
caption: [SvelteKit API endpoint accessing D1]
) <sveltekit-api>

The frontend includes an administrative dashboard that displays real-time processing job status, enabling monitoring of the automated pipeline without requiring AWS Console access (@admin-dashboard).

#figure(
  image("admin-dashboard.png", width: 90%),
  caption: [Administrative dashboard showing processing job status]
) <admin-dashboard>

== Continuous Deployment
A GitHub Actions workflow automates deployment whenever code is pushed to the main branch. Python dependencies are managed using `uv`, a modern package manager that generates a lockfile (`uv.lock`) ensuring deterministic builds across environments. The pipeline goes as follows:
1. Builds the Docker image containing all Lambda functions
2. Pushes the image to Amazon ECR
3. Runs `terraform apply` to update all infrastructure
4. Builds the SvelteKit application
5. Applies D1 database migrations using Wrangler CLI
6. Deploys the frontend to Cloudflare Pages

This ensures that both infrastructure and application code are deployed atomically, reducing configuration drift and enabling rapid iteration.

= Evaluation
== Cost Analysis

A primary goal of this project was to eliminate the recurring operational costs of the legacy system. To validate this objective, actual cloud service usage was recorded over a one-month period (December 2025) and compared against free-tier allocations.

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
The data processing pipeline runs on AWS Lambda with Step Functions orchestration. @aws-usage shows the measured usage for December 2025 against perpetual free-tier limits.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    table.header([*Service*], [*Free Tier Limit*], [*Actual Usage*], [*Utilization*]),
    "Lambda (compute)", "400,000 GB-sec/mo", "28,756 GB-sec", "7.2%",
    "Lambda (requests)", "1,000,000 req/mo", "1,570 requests", "0.2%",
    "Step Functions", "4,000 transitions/mo", "1,706 transitions", "42.7%",
    "SQS", "1,000,000 req/mo", "276,810 requests", "27.7%",
    "Data Transfer", "100 GB/mo", "0 GB", "0%",
  ),
  caption: [AWS service usage for December 2025 (perpetual free tier)]
) <aws-usage>

Amazon ECR (Elastic Container Registry) does not have a perpetual free tier. Lambda requires Docker images to be stored in private ECR repositories, incurring storage costs of \$0.10/GB/month. The current Docker image consumes 1 GB of storage, resulting in a monthly cost of \$0.10.

=== New System: Cloudflare Usage
The frontend, API, and storage layer run entirely on Cloudflare's edge network. @cloudflare-usage shows the measured usage against free-tier limits.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    table.header([*Service*], [*Free Tier Limit*], [*Actual Usage*], [*Utilization*]),
    "Workers (requests)", "100,000/day", "133/day avg", "0.1%",
    "R2 (storage)", "10 GB", "0.77 GB", "7.7%",
    "R2 (Class A ops)", "1,000,000/mo", "3,170 ops", "0.3%",
    "R2 (Class B ops)", "10,000,000/mo", "5,700 ops", "0.06%",
    "D1 (rows read)", "5,000,000/day", "2,400/day avg", "0.05%",
    "D1 (rows written)", "100,000/day", "167/day avg", "0.2%",
  ),
  caption: [Cloudflare service usage for December 2025]
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

The analysis demonstrates that the new serverless architecture achieves a cost reduction of 99.7%, with the only recurring expense being \$0.10/month for ECR storage. The annual saving of \$358.80 directly addresses stakeholder concerns regarding long-term sustainability. Importantly, the serverless model provides significant headroom for growth: current usage remains well below free-tier thresholds across all metered services, with Step Functions at 42.7% being the highest utilized resource. The pay-as-you-go pricing model ensures costs scale proportionally with actual demand rather than requiring expensive tier upgrades.

== Automation and Observability

Beyond cost reduction, the new architecture delivers significant improvements in automation and operational observability compared to the legacy system.

=== Automation Improvements

The legacy system required manual intervention for data updates: a developer had to modify script parameters, execute the retrieval code locally, and monitor progress over several hours. The new ECOSTRESS Updater pipeline eliminates this entirely through:

- *Scheduled Execution*: CloudWatch Event Rules trigger the pipeline daily at 00:00 UTC without human intervention
- *Parallel Processing*: The Fan-Out architecture processes multiple scenes concurrently, reducing total pipeline runtime from hours to minutes

=== Observability Improvements

The legacy system provided no visibility into processing status or historical job performance. Failures were only discovered when users reported missing data. The new system implements comprehensive observability:

- *Processing Logs*: Every pipeline execution is recorded in D1 with timestamps, status codes, and error messages
- *Administrative Dashboard*: A web-based interface (@admin-dashboard) displays real-time job status, enabling monitoring without AWS Console access
- *Structured Error Handling*: Failed scenes are logged with detailed context, enabling rapid diagnosis and targeted reprocessing
- *Audit Trail*: Historical processing records enable trend analysis and capacity planning

These improvements transform the system from a fragile, manually-operated tool into a self-sustaining service that can run indefinitely without developer intervention while providing full visibility into its operational state.

= Progress

This section evaluates the project's progress against the objectives and deliverables outlined in the original proposal @proposal.

== Completed Objectives

=== Data Storage and Retrieval Optimization (Objective 1)
This objective has been fully achieved. The system has been migrated from the costly Supabase/Heroku stack to a zero-cost architecture using Cloudflare R2 and D1. The hybrid storage design separates metadata (D1) from bulk data (R2), optimizing both query performance and storage costs. The original \$30/month operational cost has been reduced to \$0.10/month.

=== Code Maintainability and Documentation (Objective 6)
Significant progress has been made on this objective. The frontend has been completely rewritten from "vanilla JavaScript" to SvelteKit with TypeScript, providing type safety and component-based architecture. The backend has been refactored from a monolithic Flask application to modular Lambda functions with clear separation of concerns. All infrastructure is now defined declaratively using Terraform, enabling reproducible deployments. A continuous deployment pipeline ensures changes are tested and deployed atomically.

=== CSV-Based Storage (Deliverable D3)
Fully implemented. Temperature data is stored as CSV files in R2 with metadata pointers in D1. This approach keeps database row counts within free-tier limits while maintaining efficient data access patterns.

=== Interactive Visualization Dashboard (Deliverable D4 — Partial)
The foundation for interactive visualization is in place. The map interface displays monitored water bodies with clickable polygons, and an administrative dashboard provides real-time processing job status. However, advanced features such as pixel-level temperature inspection and threshold-based filtering remain to be implemented in the next phase.

== Remaining Work

=== Sentinel-2 Water Mask Verification (Objective 2, Deliverable D2)
The GAM4Wter model for water mask correction using Sentinel-2 imagery has not yet been verified or integrated. This is planned for the next phase of development.

=== Enhanced Visualization Features (Objective 3)
While the basic visualization infrastructure exists, the following features are pending:
- Pixel-level temperature inspection on hover/click
- User-defined threshold visualization
- Dynamic color palettes that auto-scale to local temperature ranges

=== Multi-Platform Satellite Integration (Objective 4, Deliverable D5)
Integration of Landsat 8/9 data to supplement ECOSTRESS observations has not yet begun. This will require extending the data processing pipeline to handle additional data sources with clear labeling of satellite origin.

=== Zone Differentiation (Objective 5)
The differentiation between upstream (reservoir) and downstream (river) regions has not yet been implemented. This feature requires additional geospatial processing to separate data layers by zone type.

== Timeline Assessment

The original proposal outlined a 20-week timeline divided into six phases. The current progress corresponds approximately to the completion of Phases 1–2 (System Setup and Data Optimization), with substantial work completed ahead of schedule on Phase 5 (Refactorization). The automated data processing pipeline, while not explicitly scheduled until Phase 4, was prioritized early due to stakeholder requirements for data reliability.

#figure(
  table(
    columns: (auto, auto, auto),
    table.header([*Deliverable*], [*Status*], [*Notes*]),
    "D1: Refactored codebase", "Complete", "SvelteKit + Terraform + Lambda",
    "D2: Sentinel-2 water mask", "Not Started", "Planned for next phase",
    "D3: CSV-based storage", "Complete", "R2 + D1 hybrid architecture",
    "D4: Interactive dashboard", "Partial", "Basic interface complete; advanced features pending",
    "D5: Landsat integration", "Not Started", "Planned for next phase",
    "D6: Technical documentation", "In Progress", "This report; user documentation pending",
  ),
  caption: [Summary of deliverable status]
)

The project remains on track to deliver all planned functionality by the end of the development period. The early focus on infrastructure and automation provides a solid foundation for the visualization and data integration features planned for the remaining weeks.

#bibliography("bibliography.yaml")