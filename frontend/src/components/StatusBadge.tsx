import { isPending, statusBadgeClasses, statusLabel } from "../lib/status";

export function StatusBadge({ status }: { status: string }) {
  const pulsing = isPending(status);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${statusBadgeClasses(
        status
      )}`}
    >
      {pulsing && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden />
      )}
      {statusLabel(status)}
    </span>
  );
}
