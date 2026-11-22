/**
 * The strip at the top of every page in the portfolio demo: says plainly that this is
 * sample data, and offers the two things a visitor needs to explore it.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { runBillingCycle } from "./mockApi";
import { resetDemo } from "./store";

export default function DemoBanner() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);

  const refresh = (text: string) => {
    void queryClient.invalidateQueries();
    setMessage(text);
    window.setTimeout(() => setMessage(null), 4000);
  };

  const simulate = () => {
    const { created, sent } = runBillingCycle();
    refresh(
      created || sent
        ? `Billing run: ${created} new invoice(s), ${sent} sent to the fake Riverty.`
        : "Billing run: nothing is due right now.",
    );
  };

  const reset = () => {
    resetDemo();
    refresh("Sample data restored.");
  };

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 lg:px-6">
      <p className="min-w-0 flex-1">
        <span className="font-semibold">Demo — sample data.</span>{" "}
        Runs entirely in your browser; no real invoices are sent. Changes are kept on this device.
        {message && (
          <span role="status" className="ml-2 font-medium">
            {message}
          </span>
        )}
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={simulate}
          title="Does what the hourly background jobs do: invoices due months and sends pending invoices. Put [reject], [retry] or [timeout] in an agreement's description to choose Riverty's answer."
          className="rounded-md border border-amber-300 bg-white px-3 py-1 font-medium hover:bg-amber-100"
        >
          Simulate billing run
        </button>
        <button
          type="button"
          onClick={reset}
          className="rounded-md border border-amber-300 bg-white px-3 py-1 font-medium hover:bg-amber-100"
        >
          Reset data
        </button>
      </div>
    </div>
  );
}
