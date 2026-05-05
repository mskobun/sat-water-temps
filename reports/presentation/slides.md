---
theme: default
title: Satellite Water Temperature Monitoring
colorSchema: light
transition: fade-out
fonts:
  sans: Hanken Grotesk
  serif: Gloock
  mono: Fira Mono
css: style.css
---

<div class="cover-slide">
  <div class="cover-eyebrow">Final Year Project · G53IDS · University of Nottingham</div>
  <h1 class="cover-title">Satellite Water<br>Temperature<br>Monitoring</h1>
  <hr class="cover-rule" />
  <p class="cover-subtitle">Transforming a fragile proof-of-concept into an automated, multi-sensor research-support platform</p>
  <div class="cover-meta">
    <span>Maksim Skobun</span>
    <span class="sep">·</span>
    <span>May 2026</span>
    <span class="sep">·</span>
    <span>Supervisor: Dr Tomas Maul</span>
  </div>
</div>

---
title: Why this matters
---

<h2 class="slide-title">Why this matters</h2>

<div class="context-grid">
  <div class="context-lead">
    <div class="context-kicker">Research need</div>
    <p>Surface-water temperature helps researchers reason about ecological stress, habitat shifts, water quality, and climate-related change in lakes and rivers.</p>
  </div>
  <div class="context-card">
    <div class="context-num">01</div>
    <h3>Satellite data is abundant</h3>
    <p>ECOSTRESS and Landsat already observe monitored reservoirs, but raw products are hard to use without geospatial tooling.</p>
  </div>
  <div class="context-card">
    <div class="context-num">02</div>
    <h3>Researchers need access</h3>
    <p>A web platform lets non-specialists browse, inspect, export, and share observations without downloading source rasters.</p>
  </div>
  <div class="context-card">
    <div class="context-num">03</div>
    <h3>Interpretation needs caution</h3>
    <p>Cloud, land-water mixing, missing coverage, and unvalidated retrievals must stay visible in the final interface.</p>
  </div>
</div>

---
title: The legacy system could not continue unchanged
---

<h2 class="slide-title">The legacy system could not continue unchanged</h2>

<div class="problem-list">
  <div class="problem-entry">
    <div class="problem-num">01</div>
    <div>
      <div class="problem-label">$30 / month fixed cost</div>
      <div class="problem-desc">Heroku Eco dyno plus Supabase Pro created a recurring cost even when the research platform was idle.</div>
    </div>
  </div>
  <div class="problem-entry">
    <div class="problem-num">02</div>
    <div>
      <div class="problem-label">Manual AppEEARS retrieval</div>
      <div class="problem-desc">Routine updates required a developer to edit script parameters, submit orders, poll for completion, and run processing locally.</div>
    </div>
  </div>
  <div class="problem-entry">
    <div class="problem-num">03</div>
    <div>
      <div class="problem-label">ECOSTRESS-only coverage</div>
      <div class="problem-desc">The ISS orbit gives useful high-resolution observations, but irregular revisit times leave unpredictable gaps for trend analysis.</div>
    </div>
  </div>
  <div class="problem-entry">
    <div class="problem-num">04</div>
    <div>
      <div class="problem-label">Limited exploration and reproducibility</div>
      <div class="problem-desc">Users could not inspect point history or filter pixels interactively, and new maintainers could not rebuild the cloud environment from source.</div>
    </div>
  </div>
</div>

---
title: Goals and scope
---

<h2 class="slide-title">Goals and scope</h2>

<div class="obj-list">
  <div class="obj-row">
    <div class="obj-tag">O1</div>
    <div class="obj-name">Optimise storage and retrieval</div>
    <div class="obj-status">R2 + D1 + Parquet</div>
  </div>
  <div class="obj-row">
    <div class="obj-tag">O2</div>
    <div class="obj-name">Improve water-mask verification</div>
    <div class="obj-status">OPERA DSWx-HLS for Landsat</div>
  </div>
  <div class="obj-row">
    <div class="obj-tag">O3</div>
    <div class="obj-name">Add richer public visualisation</div>
    <div class="obj-status">Hover, thresholds, point history</div>
  </div>
  <div class="obj-row">
    <div class="obj-tag">O4</div>
    <div class="obj-name">Integrate multiple satellite sources</div>
    <div class="obj-status">ECOSTRESS + Landsat 8/9</div>
  </div>
  <div class="obj-row descoped">
    <div class="obj-tag">O5</div>
    <div class="obj-name">Zone differentiation</div>
    <div class="obj-status">Removed from scope</div>
  </div>
  <div class="obj-row">
    <div class="obj-tag">O6</div>
    <div class="obj-name">Make the platform maintainable after handover</div>
    <div class="obj-status">Terraform, CI/CD, docs, tests</div>
  </div>
</div>

---
title: Remote-sensing constraints
---

<h2 class="slide-title">Remote-sensing constraints</h2>

<div class="sensor-compare">
  <div class="sensor-col">
    <div class="sensor-status-label">Selected</div>
    <div class="sensor-name">ECOSTRESS</div>
    <div class="sensor-res">70 m</div>
    <div class="sensor-revisit">ISS orbit · irregular local times</div>
    <div class="sensor-note">High spatial detail for small reservoirs, but revisit timing is unpredictable and gaps are common.</div>
  </div>
  <div class="sensor-divider"></div>
  <div class="sensor-col">
    <div class="sensor-status-label">Selected</div>
    <div class="sensor-name">Landsat 8/9</div>
    <div class="sensor-res">30 m</div>
    <div class="sensor-revisit">16-day repeat · offset satellites</div>
    <div class="sensor-note">Predictable long-term record and OPERA water-mask option, but still affected by cloud and missing coverage.</div>
  </div>
  <div class="sensor-divider"></div>
  <div class="sensor-col sensor-rejected">
    <div class="sensor-status-label">Rejected</div>
    <div class="sensor-name">MODIS</div>
    <div class="sensor-res">1 km</div>
    <div class="sensor-revisit">Daily · Terra + Aqua</div>
    <div class="sensor-note">Daily coverage is attractive, but the pixels are too coarse for many target reservoirs.</div>
  </div>
</div>

---
title: Architecture
background: '#141413'
---

<div class="section-slide">
  <div class="section-number">01</div>
  <h2 class="section-title">Architecture and implementation</h2>
</div>

---
title: Multi-cloud architecture
---

<h2 class="slide-title">Multi-cloud architecture</h2>

<div class="arch-mermaid">

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#f0eee6', 'primaryTextColor': '#2d2d2b', 'primaryBorderColor': '#d8d6ce', 'lineColor': '#87867f', 'secondaryColor': '#e4eeea', 'tertiaryColor': '#faf9f5', 'clusterBkg': '#f0eee6', 'clusterBorder': '#d8d6ce', 'edgeLabelBackground': '#faf9f5', 'fontFamily': 'Hanken Grotesk'}}}%%
flowchart LR
  subgraph sources["NASA / USGS source catalogues"]
    cmr["CMR-STAC<br/>ECOSTRESS + OPERA"]
    usgs["USGS STAC<br/>Landsat C2 L2"]
  end

  subgraph aws["AWS ingestion zone · us-west-2"]
    schedule["CloudWatch schedules<br/>+ admin backfills"]
    search["Source initiators<br/>ECOSTRESS + Landsat"]
    queue["SQS fan-out queue"]
    lambda["Processor Lambda<br/>native geospatial stack"]
  end

  subgraph cf["Cloudflare serving zone"]
    app["Pages · SvelteKit app + API"]
    d1[("D1 metadata<br/>features · observations · jobs")]
    r2[("R2 objects<br/>GeoTIFF · PNG · Parquet")]
  end

  subgraph users["Users"]
    public(["Public researcher"])
    admin(["Administrator"])
  end

  public --> app
  admin --> app
  app <--> d1
  app <--> r2
  app -. signed trigger .-> search
  schedule --> search
  search --> cmr
  search --> usgs
  search --> queue
  queue --> lambda
  lambda --> d1
  lambda --> r2

  classDef external fill:#f6f3ea,stroke:#d8d6ce,color:#2d2d2b
  classDef aws fill:#2a6049,stroke:#1a4031,color:#ffffff
  classDef cloudflare fill:#f1dfc7,stroke:#b98245,color:#3b2a1d
  class cmr,usgs,public,admin external
  class schedule,search,queue,lambda aws
  class app,d1,r2 cloudflare
```

</div>

---
title: Why this architecture works
---

<h2 class="slide-title">Why this architecture works</h2>

<div class="highlights">
  <div class="highlight-entry">
    <div class="highlight-counter">01</div>
    <div class="highlight-main">
      <div class="highlight-tag">Process beside the source data</div>
      <div class="highlight-body">ECOSTRESS, Landsat, and OPERA COG assets are hosted in AWS <strong>us-west-2</strong>. Running Lambda there avoids source-data egress and keeps range-read latency low.</div>
    </div>
  </div>
  <div class="highlight-entry">
    <div class="highlight-counter">02</div>
    <div class="highlight-main">
      <div class="highlight-tag">Fan out only when work exists</div>
      <div class="highlight-body">SQS turns each missing scene into an independent message. Lambda scales for scheduled ingestion and backfills, then returns to zero idle compute cost.</div>
    </div>
  </div>
  <div class="highlight-entry">
    <div class="highlight-counter">03</div>
    <div class="highlight-main">
      <div class="highlight-tag">Serve cheaply from Cloudflare</div>
      <div class="highlight-body">Pages, D1, and R2 keep the public app, metadata, and derived artefacts close together while staying inside free-tier limits for steady-state use.</div>
    </div>
  </div>
  <div class="highlight-entry">
    <div class="highlight-counter">04</div>
    <div class="highlight-main">
      <div class="highlight-tag">Move analysis to the browser</div>
      <div class="highlight-body">Parquet plus DuckDB-WASM supports point history and CSV export without a server-side time-series API or duplicate CSV archive.</div>
    </div>
  </div>
</div>

---
title: Data products and browser analysis
---

<h2 class="slide-title">Data products and browser analysis</h2>

<div class="product-layout">
  <div class="product-main">
    <div class="product-title">The archive is designed for both users and researchers</div>
    <p>Each successful observation is stored once, then reused across the public map, downloads, dashboards, point history, and external analysis workflows.</p>
  </div>
  <div class="product-card">
    <div class="product-kind">GeoTIFF</div>
    <p>Highest-fidelity processed raster for GIS inspection and reproducible export.</p>
  </div>
  <div class="product-card">
    <div class="product-kind">PNG</div>
    <p>Fast preview layer so users see the observation before analytical data finishes loading.</p>
  </div>
  <div class="product-card">
    <div class="product-kind">Parquet</div>
    <p>Year-sharded columnar archive queried in the browser by DuckDB-WASM and exported as CSV on demand.</p>
  </div>
  <div class="product-card">
    <div class="product-kind">deck.gl</div>
    <p>Client-side pixel rendering, hover inspection, threshold filtering, palette changes, and map picking.</p>
  </div>
</div>

---
title: Quality and transparency
---

<h2 class="slide-title">Quality and transparency</h2>

<div class="quality-layout narrative">
  <div>
    <p class="quality-intro">The system is intentionally conservative: accepting a cloudy, land, or invalid pixel as water temperature is worse than showing an explicit gap.</p>
    <div class="quality-stats">
      <div>
        <div class="quality-stat-num">11.4%</div>
        <div class="quality-stat-label">ECOSTRESS pixels accepted</div>
      </div>
      <div>
        <div class="quality-stat-num">9.5%</div>
        <div class="quality-stat-label">Landsat pixels accepted</div>
      </div>
      <div>
        <div class="quality-stat-num">3.5B</div>
        <div class="quality-stat-label">raw pixels summarised across production scenes</div>
      </div>
      <div>
        <div class="quality-stat-num">5×5</div>
        <div class="quality-stat-label">local spatial check for isolated artefacts</div>
      </div>
    </div>
  </div>
  <div>
    <div class="flag-heading">Audit trail, not decoration</div>
    <div class="reason-list">
      <div class="reason-item"><span>Cloud or shadow</span><p>Observation exists, but the value should not be trusted.</p></div>
      <div class="reason-item"><span>Land or shoreline mixture</span><p>The pixel is not a clean water-surface measurement.</p></div>
      <div class="reason-item"><span>No-data or missing coverage</span><p>The satellite did not provide a valid measurement for that location.</p></div>
      <div class="reason-item"><span>Implausible or isolated outlier</span><p>Physical range and local checks remove obvious artefacts.</p></div>
    </div>
  </div>
</div>

---
title: Public and admin experience
---

<h2 class="slide-title">Public and admin experience</h2>

<div class="experience-cols">
  <div>
    <h3 class="col-heading">Public research workflows</h3>
    <ul class="conclusion-list">
      <li>Browse monitored water bodies on an interactive satellite map</li>
      <li>Switch ECOSTRESS and Landsat observations by date and source</li>
      <li>Inspect per-pixel values, threshold ranges, and point history</li>
      <li>Download GeoTIFF, Parquet, and on-demand CSV exports</li>
      <li>Use responsive map, drawer, and point-history layouts on mobile</li>
    </ul>
  </div>
  <div>
    <h3 class="col-heading">Operator workflows</h3>
    <ul class="conclusion-list">
      <li>Authenticate through Cognito-backed admin routes</li>
      <li>Monitor jobs, requests, feature freshness, and thumbnails</li>
      <li>Inspect rejection summaries without opening cloud consoles</li>
      <li>Run manual historical backfills from the web interface</li>
      <li>Configure catch-up behaviour and Landsat water-mask mode</li>
    </ul>
  </div>
</div>

---
title: "Live demo: Banglang Reservoir"
background: '#141413'
---

<div class="demo-slide">
  <div class="demo-eyebrow">Live demo route</div>
  <h2 class="demo-title">Banglang Reservoir</h2>
  <div class="demo-steps">
    <span class="demo-step">Open public map</span>
    <span class="demo-step">Select feature</span>
    <span class="demo-step">Switch ECOSTRESS / Landsat</span>
    <span class="demo-step">Inspect pixel</span>
    <span class="demo-step">Threshold + palette</span>
    <span class="demo-step">Point history</span>
    <span class="demo-step">Archive downloads</span>
    <span class="demo-step">Public dashboard</span>
    <span class="demo-step">Admin backfill</span>
    <span class="demo-step">Jobs + diagnostics</span>
  </div>
</div>

---
title: Evaluation
background: '#141413'
---

<div class="section-slide">
  <div class="section-number">02</div>
  <h2 class="section-title">Evaluation and handover</h2>
</div>

---
title: Operational evaluation
---

<h2 class="slide-title">Operational evaluation</h2>

<div class="stat-grid">
  <div class="stat-item">
    <div class="stat-rule"></div>
    <div class="stat-number">$0.03</div>
    <div class="stat-label">steady-state monthly cost</div>
    <div class="stat-note">Down from $30/month; Cloudflare remains inside free-tier usage; ECR image storage is the only recurring charge.</div>
  </div>
  <div class="stat-item">
    <div class="stat-rule"></div>
    <div class="stat-number">10,881</div>
    <div class="stat-label">processed production scenes</div>
    <div class="stat-note">3,341 ECOSTRESS + 7,540 Landsat; Landsat adds 2.3× scene volume and a predictable repeat cycle.</div>
  </div>
  <div class="stat-item">
    <div class="stat-rule"></div>
    <div class="stat-number">~5 min</div>
    <div class="stat-label">monthly ECOSTRESS run</div>
    <div class="stat-note">Direct STAC/COG access and SQS fan-out replace an hours-to-days AppEEARS order-and-poll workflow.</div>
  </div>
  <div class="stat-item">
    <div class="stat-rule"></div>
    <div class="stat-number">3.9 GB</div>
    <div class="stat-label">R2 storage after cleanup</div>
    <div class="stat-note">39% of the 10 GB free tier; projected growth remains within free tier for around 21 months.</div>
  </div>
</div>

---
title: User survey results
---

<h2 class="slide-title">User survey results</h2>

<div class="survey-layout">
  <div class="survey-summary">
    <div class="survey-kicker">Task-based usability survey</div>
    <div class="survey-big">25</div>
    <p>University of Nottingham Malaysia students used the live deployment to browse the map, select a water body, switch sources, inspect pixels, open point history, and adjust controls.</p>
    <div class="survey-note">Scores are mean ratings on a 5-point scale.</div>
  </div>
  <div class="survey-bars">
    <div class="survey-row" style="--score: 89%">
      <span>Recommendation likelihood</span>
      <div class="bar"><i></i></div>
      <b>4.48</b>
    </div>
    <div class="survey-row" style="--score: 89%">
      <span>Ease of finding data</span>
      <div class="bar"><i></i></div>
      <b>4.44</b>
    </div>
    <div class="survey-row" style="--score: 89%">
      <span>Visual design</span>
      <div class="bar"><i></i></div>
      <b>4.44</b>
    </div>
    <div class="survey-row" style="--score: 86%">
      <span>Overall usefulness</span>
      <div class="bar"><i></i></div>
      <b>4.32</b>
    </div>
    <div class="survey-row" style="--score: 84%">
      <span>Historical exploration</span>
      <div class="bar"><i></i></div>
      <b>4.20</b>
    </div>
    <div class="survey-row weak" style="--score: 82%">
      <span>Loading speed</span>
      <div class="bar"><i></i></div>
      <b>4.12</b>
    </div>
  </div>
</div>

---
title: Stakeholder evaluation
---

<h2 class="slide-title">Stakeholder evaluation</h2>

<div class="stakeholder-layout">
  <div class="stakeholder-lead">
    <div class="survey-kicker">Domain stakeholder feedback</div>
    <p>Two environmental stakeholders evaluated the final deployment, including questions about Landsat coverage, insight usefulness, point history, and admin visibility.</p>
    <div class="stakeholder-callout">
      <span>5 / 5</span>
      <p>Both stakeholders rated insight usefulness and Landsat coverage at the maximum score.</p>
    </div>
  </div>
  <div class="score-grid">
    <div class="score-row header"><span>Question</span><b>S1</b><b>S2</b></div>
    <div class="score-row"><span>Finding temperature data</span><b>5</b><b>5</b></div>
    <div class="score-row"><span>Exploring historical data</span><b>5</b><b>5</b></div>
    <div class="score-row"><span>Useful environmental insight</span><b>5</b><b>5</b></div>
    <div class="score-row"><span>Landsat coverage improvement</span><b>5</b><b>5</b></div>
    <div class="score-row"><span>Point history sufficiency</span><b>4</b><b>5</b></div>
    <div class="score-row"><span>Admin pipeline visibility</span><b>4</b><b>5</b></div>
    <div class="score-row"><span>Loading speed</span><b>4</b><b>5</b></div>
  </div>
  <div class="stakeholder-footer">
    Most useful features: data download and reservoir search. Requested improvements: wetted-area filtering and a stronger welcome page.
  </div>
</div>

---
title: Verification, deployment, and handover
---

<h2 class="slide-title">Verification, deployment, and handover</h2>

<div class="delivery-layout">
  <div class="delivery-claim">
    <div class="survey-kicker">Maintainable after handover</div>
    <p>The final system is built to be tested, redeployed, and operated by a successor without manually rebuilding cloud resources or rerunning ad hoc scripts.</p>
    <div class="delivery-metric">
      <span>105</span>
      <b>backend tests cover processing, masking, clipping, mosaicking, database helpers, Parquet slicing, and local backfill paths.</b>
    </div>
  </div>
  <div class="release-flow">
    <div class="flow-title">GitHub Actions release paths</div>
    <div class="flow-track">
      <div class="flow-node">Commit</div>
      <div class="flow-arrow">→</div>
      <div class="flow-node primary">GitHub Actions</div>
      <div class="flow-arrow">→</div>
      <div class="flow-targets">
        <span>Cloudflare Pages app</span>
        <span>D1 migrations</span>
        <span>Terraform infrastructure</span>
        <span>Lambda container images</span>
      </div>
    </div>
    <div class="delivery-rows">
      <div class="delivery-row">
        <span>01</span>
        <p><strong>Verification gates:</strong> backend tests, Svelte checks, TypeScript checks, and manual browser workflow checks before final delivery.</p>
      </div>
      <div class="delivery-row">
        <span>02</span>
        <p><strong>Rebuildable infrastructure:</strong> Terraform captures AWS and Cloudflare resources so the environment can be recreated from versioned configuration.</p>
      </div>
      <div class="delivery-row">
        <span>03</span>
        <p><strong>Operational continuity:</strong> guides document secrets, admin access, local development, deployment workflows, and historical backfill procedures.</p>
      </div>
    </div>
  </div>
</div>

---
title: Limitations and future work
---

<h2 class="slide-title">Limitations and future work</h2>

<div class="conclusion-cols">
  <div>
    <h3 class="col-heading">Limitations</h3>
    <ul class="conclusion-list">
      <li>ECR image storage remains a small paid dependency (~$0.03/month)</li>
      <li>R2 storage has ~6.1 GB of free-tier headroom; continued ingestion will eventually require storage management</li>
      <li>Temperature values are screened satellite estimates, not field-validated measurements</li>
      <li>Hampel and physical-range checks cannot detect all coherent cloud, haze, or retrieval-bias cases</li>
      <li>Best understood as a screening and exploration tool until accepted pixels are compared against field measurements</li>
    </ul>
  </div>
  <div>
    <h3 class="col-heading">Future work</h3>
    <ul class="conclusion-list">
      <li>Evaluate CNN-based cloud masks for improved cloud and cloud-shadow segmentation</li>
      <li>Add a local ingestion integration harness for end-to-end pipeline testing</li>
      <li>Integrate MODIS for a coarser-resolution historical baseline</li>
      <li>Add anomaly alerts when a feature goes too long without a successful observation</li>
      <li>Extend geographic coverage beyond Southeast Asia</li>
      <li>Document a public OpenAPI and run a broader domain-expert evaluation</li>
    </ul>
  </div>
</div>

---
title: Summary
---

<h2 class="slide-title">Summary</h2>

<div class="conclusion-stacked">
  <p class="summary-lead">Five of six proposed objectives implemented. The platform is operationally sustainable, multi-sensor, and substantially more interactive than the legacy system.</p>
  <ul class="conclusion-list">
    <li>Recurring cost reduced from $30/month to $0.03/month</li>
    <li>OPERA-backed Landsat masking added alongside ECOSTRESS</li>
    <li>Per-pixel inspection, threshold filtering, and archive downloads available to users</li>
    <li>Point-history queries run in the browser via year-sharded Parquet and DuckDB-WASM</li>
    <li>Automated ingestion with configurable catch-up and on-demand backfill via the admin dashboard</li>
  </ul>
</div>
