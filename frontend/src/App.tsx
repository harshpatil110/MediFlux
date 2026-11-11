import { useState, useEffect } from "react";
import { 
  Activity, 
  ArrowRight, 
  CheckCircle2, 
  Layers, 
  Package, 
  Store, 
  Truck, 
  Factory, 
  ShieldCheck, 
  Cpu,
  RefreshCw
} from "lucide-react";

interface HealthStatus {
  status: string;
  app: string;
  version: string;
}

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTier, setActiveTier] = useState<number>(0);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/health");
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      } else {
        setHealth(null);
      }
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const tiers = [
    {
      id: "pharmacy",
      name: "Pharmacy Edge Node",
      role: "Retail POS & Patient Counter",
      icon: Store,
      metric: "Single-unit dispense trigger",
      status: "Ready",
    },
    {
      id: "stockist",
      name: "Stockist Hub",
      role: "Sub-district Consolidation",
      icon: Layers,
      metric: "Buffer threshold eval",
      status: "Listening",
    },
    {
      id: "distributor",
      name: "Distributor Layer",
      role: "Regional Depot & Logistics",
      icon: Truck,
      metric: "Wholesale PO forwarding",
      status: "Connected",
    },
    {
      id: "manufacturer",
      name: "Manufacturer Plant",
      role: "CDSCO Batch Production",
      icon: Factory,
      metric: "Dynamic batch scheduling",
      status: "Standby",
    },
  ];

  return (
    <div className="min-h-screen bg-[#E8E4D3] text-[#031211] font-sans">
      {/* Editorial Top Navigation */}
      <header className="border-b border-[#D8D3C3] bg-[#E8E4D3]/90 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-xl font-bold tracking-tight text-[#031211] font-serif">
              MEDIFLUX
            </span>
            <span className="text-xs uppercase tracking-widest px-2 py-0.5 bg-[#DFDBCA] text-[#5C584E] border border-[#D8D3C3]">
              Pharma 4-Tier OS
            </span>
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-[#5C584E]">Backend Status:</span>
              {loading ? (
                <span className="inline-flex items-center gap-1.5 text-[#5C584E]">
                  <RefreshCw className="w-3 h-3 animate-spin" /> Checking
                </span>
              ) : health?.status === "ok" ? (
                <span className="inline-flex items-center gap-1.5 text-emerald-800 font-medium">
                  <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse"></span>
                  Online ({health.version})
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-amber-800">
                  <span className="w-2 h-2 rounded-full bg-amber-600"></span>
                  Awaiting backend (:8000)
                </span>
              )}
            </div>

            <button
              onClick={fetchHealth}
              className="text-xs text-[#5C584E] hover:text-[#031211] border border-[#D8D3C3] px-3 py-1 bg-white hover:bg-[#F4F1E6] transition-colors"
            >
              Ping API
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-6 py-12">
        {/* Editorial Hero Banner */}
        <section className="mb-12 border-b border-[#D8D3C3] pb-10">
          <p className="text-xs font-mono uppercase tracking-widest text-[#5C584E] mb-2">
            Phase 1 Foundation — Task 1 Complete
          </p>
          <h1 className="text-4xl md:text-5xl font-serif font-bold text-[#031211] tracking-tight leading-tight max-w-3xl">
            Instantaneous single-unit retail demand propagation.
          </h1>
          <p className="mt-4 text-[#5C584E] text-base md:text-lg max-w-2xl leading-relaxed">
            When 1 strip of medicine is sold at a retail counter, MediFlux triggers an autonomous multi-agent cascade upstream through the stockist, distributor, and plant.
          </p>
        </section>

        {/* 4-Tier Interactive Architecture Flow */}
        <section className="mb-12">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-mono uppercase tracking-wider text-[#031211] font-semibold flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#00AEBB]" /> 4-Tier Autonomous Supply Chain Pipeline
            </h2>
            <span className="text-xs text-[#5C584E]">Click a tier to inspect role</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {tiers.map((tier, index) => {
              const Icon = tier.icon;
              const isSelected = activeTier === index;
              return (
                <div
                  key={tier.id}
                  onClick={() => setActiveTier(index)}
                  className={`cursor-pointer p-5 transition-all border ${
                    isSelected
                      ? "bg-white border-[#00AEBB] shadow-sm"
                      : "bg-white/60 hover:bg-white border-[#D8D3C3]"
                  }`}
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="p-2 border border-[#D8D3C3] bg-[#F4F1E6]">
                      <Icon className="w-5 h-5 text-[#031211]" />
                    </div>
                    <span className="text-xs font-mono text-[#5C584E]">
                      Tier 0{index + 1}
                    </span>
                  </div>

                  <h3 className="font-semibold text-[#031211] text-base mb-1">
                    {tier.name}
                  </h3>
                  <p className="text-xs text-[#5C584E] mb-4">
                    {tier.role}
                  </p>

                  <div className="pt-3 border-t border-[#E0DCCC] flex items-center justify-between text-xs">
                    <span className="font-mono text-[#5C584E]">{tier.status}</span>
                    {isSelected && (
                      <span className="text-[#00AEBB] font-medium flex items-center gap-1">
                        Active <ArrowRight className="w-3 h-3" />
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Detail Matrix / Technical Foundations */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {/* Card 1: Architectural Compliance */}
          <div className="p-6 bg-white border border-[#D8D3C3]">
            <div className="flex items-center gap-2 mb-3 text-[#031211] font-semibold text-sm">
              <ShieldCheck className="w-4 h-4 text-[#00AEBB]" />
              Strict Architectural Guardrails
            </div>
            <p className="text-xs text-[#5C584E] mb-4 leading-relaxed">
              Zero deferred technologies in MVP. In-process asyncio event bus and AST safety guards enforce security without Docker, Kafka, Redis, or WASM.
            </p>
            <ul className="text-xs space-y-2 text-[#5C584E]">
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#00AEBB]" /> No Redis (In-memory cache & Supabase)
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#00AEBB]" /> No Docker (Bare-metal python & node)
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#00AEBB]" /> No Kafka (In-process EventBus)
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#00AEBB]" /> No WASM (Static AST guardrails)
              </li>
            </ul>
          </div>

          {/* Card 2: AI Multi-Agent Engine */}
          <div className="p-6 bg-white border border-[#D8D3C3]">
            <div className="flex items-center gap-2 mb-3 text-[#031211] font-semibold text-sm">
              <Cpu className="w-4 h-4 text-[#00AEBB]" />
              Agent & Graph Orchestration
            </div>
            <p className="text-xs text-[#5C584E] mb-4 leading-relaxed">
              LangGraph workflows coordinate state transitions from prescription extraction to downstream replenishment and cold-chain compliance.
            </p>
            <div className="space-y-2 font-mono text-xs">
              <div className="p-2 bg-[#F4F1E6] border border-[#E0DCCC] flex justify-between">
                <span>cascade.py</span>
                <span className="text-[#00AEBB]">Compiled</span>
              </div>
              <div className="p-2 bg-[#F4F1E6] border border-[#E0DCCC] flex justify-between">
                <span>prescription.py</span>
                <span className="text-[#00AEBB]">Ready</span>
              </div>
              <div className="p-2 bg-[#F4F1E6] border border-[#E0DCCC] flex justify-between">
                <span>coldchain.py</span>
                <span className="text-[#00AEBB]">Ready</span>
              </div>
            </div>
          </div>

          {/* Card 3: Free LLM Routing */}
          <div className="p-6 bg-white border border-[#D8D3C3]">
            <div className="flex items-center gap-2 mb-3 text-[#031211] font-semibold text-sm">
              <Package className="w-4 h-4 text-[#00AEBB]" />
              Deterministic LLM Routing
            </div>
            <p className="text-xs text-[#5C584E] mb-4 leading-relaxed">
              Cost-free inference pipeline using NVIDIA-hosted endpoints, OpenRouter free models, and local Ollama with SHA-256 deterministic caching.
            </p>
            <div className="space-y-2 text-xs text-[#5C584E]">
              <div className="flex justify-between py-1 border-b border-[#E0DCCC]">
                <span>Primary</span>
                <span className="font-mono text-[#031211]">NVIDIA NIM (Llama 3.1)</span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#E0DCCC]">
                <span>Secondary</span>
                <span className="font-mono text-[#031211]">OpenRouter Free</span>
              </div>
              <div className="flex justify-between py-1">
                <span>Offline Fallback</span>
                <span className="font-mono text-[#031211]">Ollama Local</span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <footer className="pt-6 border-t border-[#D8D3C3] flex flex-col md:flex-row items-center justify-between text-xs text-[#5C584E] gap-4">
          <p>© 2026 MediFlux India. Built with spec-driven AI-IDE workflow.</p>
          <div className="flex items-center gap-4 font-mono">
            <span>FastAPI v0.1.0</span>
            <span>•</span>
            <span>React 18 + Vite</span>
            <span>•</span>
            <span>LangGraph</span>
          </div>
        </footer>
      </main>
    </div>
  );
}
