### How it works

1. **Counts by label** ¨C Every node¡¯s `labels` list is iterated, incrementing a counter in `node_counts_by_label`.
2. **Counts by relationship type** ¨C Similar, from the `type` field.
3. **Numeric aggregations** ¨C For every property value that is an `int` or `float`, the code collects:
   - `count`