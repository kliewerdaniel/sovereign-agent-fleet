"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Radio } from "lucide-react";
import { fleetApi } from "@/lib/fleet";

// Honest, always-visible status: this surface reads a LIVE control plane.
// When the API is unreachable we say so plainly (constraint: never claim live
// if it isn't).
export function LiveBanner() {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => {
    let alive = true;
    const ping = async () => {
      try {
        await fleetApi.health();
        if (alive) setOk(true);
      } catch {
        if (alive) setOk(false);
      }
    };
    ping();
    const t = setInterval(ping, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  if (ok === null) return null;
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={`px-5 py-1.5 text-xs flex items-center gap-2 border-b ${
        ok
          ? "border-[var(--color-accent-dim)] bg-[rgba(52,211,153,0.06)] text-[var(--color-accent)]"
          : "border-[var(--color-danger)] bg-[rgba(240,88,75,0.08)] text-[var(--color-danger)]"
      }`}
    >
      <Radio size={13} className={ok ? "live-dot" : ""} />
      {ok
        ? "LIVE CONTROL PLANE · reads the real signed hash-chain · writes call the fleet control plane (D17)"
        : "CONTROL PLANE OFFLINE · start fleet/api on :8788 to see live data"}
    </motion.div>
  );
}
