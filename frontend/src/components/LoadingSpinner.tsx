export function LoadingSpinner({ label = "Загрузка" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-gray-500" role="status" aria-live="polite">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-gray-200 border-t-brand" />
      <span>{label}</span>
    </div>
  );
}
