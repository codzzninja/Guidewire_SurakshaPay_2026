/** Initial dashboard load — reduces layout shift vs plain “Loading…”. */

function Bar({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded-lg bg-slate-200/90 animate-pulse ${className}`}
      aria-hidden
    />
  );
}

export default function DashboardSkeleton() {
  return (
    <div className="min-h-[100dvh] pb-safe safe-pb max-w-lg mx-auto px-4 pt-6 space-y-5">
      <div className="flex justify-between gap-3">
        <div className="space-y-2 flex-1">
          <Bar className="h-6 w-36" />
          <Bar className="h-4 w-48" />
        </div>
        <Bar className="h-4 w-14 shrink-0 mt-1" />
      </div>
      <div className="rounded-2xl bg-white border border-slate-100 p-4 shadow-card space-y-3">
        <Bar className="h-3 w-32" />
        <Bar className="h-8 w-44" />
        <Bar className="h-4 w-full max-w-[220px]" />
      </div>
      <div className="space-y-2">
        <Bar className="h-5 w-28" />
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-2xl border-2 border-slate-100 p-4 space-y-2"
          >
            <Bar className="h-4 w-24" />
            <Bar className="h-3 w-full" />
          </div>
        ))}
      </div>
      <div className="rounded-2xl bg-white border border-slate-100 p-4 space-y-2">
        <Bar className="h-4 w-40" />
        <Bar className="h-10 w-full" />
      </div>
      <p className="text-center text-sm text-slate-500 pt-2">Just a moment…</p>
    </div>
  );
}
