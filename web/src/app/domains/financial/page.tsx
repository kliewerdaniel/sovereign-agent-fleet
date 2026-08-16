import { fetchDomains } from "@/lib/fleet";
import { UnwiredNote } from "@/components/DomainPanel";

export const dynamic = "force-dynamic";

export default async function FinancialDomainPage() {
  const model = await fetchDomains();
  return (
    <div className="max-w-3xl mx-auto px-5 py-8 space-y-6">
      <div className="flex items-center gap-3">
        <span className="divider-label">domain · financial</span>
        <span className="pill pill-warn">not yet wired</span>
      </div>
      <UnwiredNote domain="financial" wired={model.wired} />
    </div>
  );
}
