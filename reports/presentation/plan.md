# Presentation Plan

**Format:** 15 min presentation/demo + 5 min Q&A  
**Audience:** examiner and supervisor  
**Aim:** show how the report's work turns a fragile proof-of-concept into a sustainable research-support platform, without getting stuck in low-level implementation details.

## Narrative Arc

The presentation should follow the report's argument:

1. Surface-water temperature is useful, but satellite data needs careful processing before non-specialists can use it.
2. The inherited platform proved the idea, but failed the operational needs: cost, manual ingestion, single-sensor gaps, limited interaction, weak reproducibility.
3. The final system solves those needs through automated multi-sensor ingestion, a low-cost Cloudflare/AWS split, browser-side analysis over Parquet, and admin-facing observability.
4. Evaluation shows the platform meets the operational objectives, while the scientific limitation remains: it provides screened remote-sensing estimates, not field-validated water-temperature truth.

## Slide Plan

| # | Slide | Purpose |
|---|-------|---------|
| 1 | Title | Position the project as a transformation from proof-of-concept to operational platform. |
| 2 | Why this matters | Give the ecological/research motivation before discussing software. |
| 3 | Legacy system limits | Explain why the inherited system could not continue unchanged. |
| 4 | Goals and scope | Tie objectives to the report, including Landsat, OPERA, removed zone differentiation, and no in-situ validation. |
| 5 | Remote-sensing constraints | Explain ECOSTRESS/Landsat/MODIS trade-offs and why filtering/missingness matters. |
| 6 | System architecture | One conceptual view of Cloudflare serving + AWS ingestion + NASA/USGS sources. |
| 7 | Automated data pipeline | Show scheduled/manual triggers, STAC search, COG reads, SQS fan-out, processing, and R2/D1 outputs. |
| 8 | Data products and browser analysis | Explain GeoTIFF, PNG, Parquet, DuckDB-WASM, MapLibre/deck.gl, point history, and exports. |
| 9 | Quality and transparency | Reframe filter flags as an audit-trail design: users can see why pixels are missing or rejected. |
| 10 | Public and admin experience | Cover frontend, archive, dashboard, mobile support, authentication, diagnostics, settings, and backfill. |
| 11 | Live demo route | Keep the demo focused on Banglang: map, pixel inspection, point history, downloads, admin backfill/diagnostics. |
| 12 | Evaluation results | Present cost, scene counts, processing time, user survey, and stakeholder scores. |
| 13 | Testing, deployment, and handover | Show reproducibility work: tests, type checks, Terraform, GitHub Actions, user/developer guides. |
| 14 | Limitations and future work | Scientific caveat, D1 write bottleneck, large Parquet shards, cloud-mask improvement, alerts/API/evaluation. |
| 15 | Conclusion | End with three contributions and the careful claim about screening/exploration/export/audit. |

## Timing

| Segment | Duration | Slides |
|---------|----------|--------|
| Motivation and scope | 3 min | 1-5 |
| Architecture and implementation | 4 min | 6-10 |
| Live demo | 5 min | 11 |
| Evaluation and handover | 2 min | 12-13 |
| Limitations and close | 1 min | 14-15 |

## Live Demo Flow

Water body: **Banglang**. Check the data beforehand so the latest observation, point history, and downloads are all responsive.

1. Open the public map and select Banglang.
2. Switch between ECOSTRESS and Landsat observations.
3. Inspect a pixel, then adjust palette and threshold controls.
4. Open point history and explain that DuckDB-WASM queries Parquet in the browser.
5. Show archive downloads: GeoTIFF, Parquet, and on-demand CSV.
6. Open the public dashboard for cross-feature freshness.
7. In admin, trigger or show a recent backfill request.
8. Show job history and diagnostics as the operator-facing audit trail.
9. Show settings briefly for catch-up and Landsat water-mask controls.

## Q&A Prep Areas

- Why the architecture uses both Cloudflare and AWS.
- Why Lambda/SQS fits periodic scene processing.
- Why STAC/COG direct access replaced AppEEARS.
- Why Landsat improves coverage but does not remove validation needs.
- Why Parquet + DuckDB-WASM avoids a server-side time-series API.
- What the filter statistics can and cannot prove scientifically.
- What remains limited by D1 write concurrency and large Landsat shards.
