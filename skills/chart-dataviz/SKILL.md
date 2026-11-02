---
name: chart-dataviz
description: Creating charts, plots, and data visualizations from data files (CSV, JSON, query results) using matplotlib or Mermaid diagrams. Use when the user asks to chart, plot, graph, or visualize data, or wants a diagram (flowchart, sequence, ER) rendered as an image.
---

# Charts & Data Visualization

## Two distinct jobs — don't mix them up

1. **Data charts** (distributions, trends, comparisons) → matplotlib/plotly from real data.
2. **Structure diagrams** (flowcharts, sequences, ER, gantt) → Mermaid text → rendered image.

## Mermaid

Write `diagram.mmd`, then render:
```bash
npx -y @mermaid-js/mermaid-cli -i diagram.mmd -o diagram.png -w 1600
```
Keep diagrams small and legible; split anything over ~15 nodes into subgraphs. Common syntax gotchas: node labels containing special characters need quotes — `A["label (with parens)"]`.

## Matplotlib

```python
import pandas as pd, matplotlib.pyplot as plt
df = pd.read_csv("data.csv")
ax = df.plot(x="date", y="value", kind="line", figsize=(10, 5))
ax.set_title("…"); ax.set_ylabel("…")
plt.tight_layout(); plt.savefig("chart.png", dpi=150)
```

Rules for quality output:
- Always label axes and units; title states the takeaway, not the columns ("Sales doubled in Q3" > "Sales by quarter").
- Verify the data shape before plotting: `df.head()`, `df.dtypes` — dates as strings and numbers as objects are the top failure causes.
- For time series, parse dates (`pd.to_datetime`) so spacing is truthful.
- Save to file and **view the image** before delivering; iterate on legibility (font size, ticks) from what you see.
- Dark background? Set `plt.style.use("dark_background")` and ensure tick/label contrast.
- Many series → facet (`df.groupby` + subplots) rather than a 15-line spaghetti chart.

## Choosing chart types

- Comparison → bar. Trend over time → line. Composition → stacked bar (avoid pies beyond 3–4 slices). Distribution → histogram/box. Relationship → scatter.
- Avoid dual axes and 3D — both mislead.
