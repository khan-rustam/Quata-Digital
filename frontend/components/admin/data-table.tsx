import * as React from "react";
import { cn } from "@/lib/utils";
import { Checkbox } from "@/components/ui/checkbox";

export type Column<T> = {
  key: string;
  header: React.ReactNode;
  cell: (row: T) => React.ReactNode;
  className?: string;
};

export type DataTableProps<T extends { id: number | string }> = {
  columns: Column<T>[];
  rows: T[];
  empty?: string;
  loading?: boolean;
  selectable?: boolean;
  selectedIds?: Array<T["id"]>;
  onSelectionChange?: (ids: Array<T["id"]>) => void;
};

export function DataTable<T extends { id: number | string }>({
  columns,
  rows,
  empty = "Nothing to show yet.",
  loading = false,
  selectable = false,
  selectedIds = [],
  onSelectionChange,
}: DataTableProps<T>) {
  const allChecked = selectable && rows.length > 0 && rows.every((r) => selectedIds.includes(r.id));
  const someChecked = selectable && rows.some((r) => selectedIds.includes(r.id)) && !allChecked;

  function toggleAll() {
    if (!onSelectionChange) return;
    if (allChecked) {
      onSelectionChange(selectedIds.filter((id) => !rows.some((r) => r.id === id)));
    } else {
      const merged = Array.from(new Set([...selectedIds, ...rows.map((r) => r.id)]));
      onSelectionChange(merged);
    }
  }

  function toggleRow(id: T["id"]) {
    if (!onSelectionChange) return;
    onSelectionChange(
      selectedIds.includes(id)
        ? selectedIds.filter((x) => x !== id)
        : [...selectedIds, id]
    );
  }

  const totalCols = columns.length + (selectable ? 1 : 0);

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card ring-soft">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface-soft text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              {selectable && (
                <th className="px-4 py-3 w-10">
                  <Checkbox
                    checked={allChecked}
                    indeterminate={someChecked}
                    onCheckedChange={toggleAll}
                    ariaLabel="Select all"
                  />
                </th>
              )}
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={cn("text-left font-medium px-4 py-3", c.className)}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr>
                <td colSpan={totalCols} className="px-4 py-10 text-center text-muted-foreground">
                  Loading…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={totalCols} className="px-4 py-10 text-center text-muted-foreground">
                  {empty}
                </td>
              </tr>
            ) : (
              rows.map((row) => {
                const selected = selectable && selectedIds.includes(row.id);
                return (
                  <tr
                    key={row.id}
                    className={cn(
                      "hover:bg-surface-soft/60 transition-colors",
                      selected && "bg-brand-soft/40"
                    )}
                  >
                    {selectable && (
                      <td className="px-4 py-3.5 align-middle">
                        <Checkbox
                          checked={!!selected}
                          onCheckedChange={() => toggleRow(row.id)}
                          ariaLabel={`Select row ${row.id}`}
                        />
                      </td>
                    )}
                    {columns.map((c) => (
                      <td key={c.key} className={cn("px-4 py-3.5 align-middle", c.className)}>
                        {c.cell(row)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function BulkActionsBar({
  count,
  onClear,
  children,
}: {
  count: number;
  onClear: () => void;
  children: React.ReactNode;
}) {
  if (count === 0) return null;
  return (
    <div className="sticky top-16 z-10 -mx-1 mb-3 flex items-center justify-between gap-3 rounded-2xl border border-primary/30 bg-brand-soft/60 px-4 py-2.5 ring-soft backdrop-blur">
      <div className="text-sm">
        <span className="font-semibold">{count}</span> selected
        <button onClick={onClear} className="ml-3 text-xs text-muted-foreground hover:text-foreground underline">
          Clear
        </button>
      </div>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}
