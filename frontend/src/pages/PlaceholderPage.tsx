import { PageHeader } from "@/components/ui/PageHeader";

export function PlaceholderPage({ title, phase }: { title: string; phase?: number }) {
  return (
    <>
      <PageHeader title={title} />
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center">
        <p className="text-sm font-medium text-slate-700">Not built yet</p>
        <p className="mt-1 text-sm text-slate-500">
          This page is implemented in {phase ? `Phase ${phase}` : "a later phase"} of the roadmap.
        </p>
      </div>
    </>
  );
}
