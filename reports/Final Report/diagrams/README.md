# Final Report diagrams

Mermaid sources for the three architectural diagrams referenced by
`reports/Final Report/Final Report.typ`:

- `high-level.mmd`      → `../High Level Overview.svg`     (Figure: System architecture)
- `db-schema.mmd`       → `../DB Schema.svg`               (Figure: D1 schema)
- `ecostress-flow.mmd`  → `../EcoStress Updater Flow.svg`  (Figure: Updater flow)

The `.typ` file embeds the rendered SVGs; the `.mmd` sources are committed so
the diagrams stay diff-friendly.

## Re-rendering

Requires Node. Run from the repository root:

```bash
cd "reports/Final Report"
npx -p @mermaid-js/mermaid-cli mmdc -i diagrams/high-level.mmd    -o "High Level Overview.svg"    -t neutral -b transparent
npx -p @mermaid-js/mermaid-cli mmdc -i diagrams/db-schema.mmd     -o "DB Schema.svg"              -t neutral -b transparent
npx -p @mermaid-js/mermaid-cli mmdc -i diagrams/ecostress-flow.mmd -o "EcoStress Updater Flow.svg" -t neutral -b transparent
```

The `neutral` theme and transparent background print legibly in both light and
dark PDF viewers. Commit both the `.mmd` sources and the `.svg` outputs so the
report compiles without Node installed.
