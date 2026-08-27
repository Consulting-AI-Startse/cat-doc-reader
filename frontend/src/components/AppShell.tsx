import { Link, Outlet } from "react-router-dom";

export function AppShell() {
  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="sticky top-0 z-20 border-b border-neutral-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-2.5">
          <Link to="/" className="flex items-center">
            <img src="/cat-logo-mark.png" alt="Caterpillar" className="h-6" />
          </Link>
          <span className="h-5 w-px bg-neutral-200" />
          <span className="text-sm font-semibold text-neutral-500">Document Reader</span>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
