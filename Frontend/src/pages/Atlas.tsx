import React, { useState, useEffect, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polygon,
  GeoJSON,
  LayersControl,
  useMap,
} from "react-leaflet";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Info, Satellite, Layers, BarChart2, Target, Loader2, AlertCircle, Activity } from "lucide-react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// ✅ Fix Leaflet default icon
const defaultIconPrototype = L.Icon.Default.prototype as unknown as Record<string, unknown>;
delete defaultIconPrototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl:       "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl:     "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const SUPPORTED_STATES = ["Madhya Pradesh", "Odisha", "Telangana", "Tripura"];

const buildBackendUrl = (path: string) => {
  const base = BACKEND_URL.endsWith("/") ? BACKEND_URL : `${BACKEND_URL}/`;
  return new URL(path.replace(/^\/+/, ""), base).toString();
};

// ── Land use colour map ──────────────────────────────────────────────────────
const LAND_USE_COLORS: Record<string, string> = {
  Forest:       "#16a34a",
  forest:       "#16a34a",
  "forest / vegetation": "#16a34a",
  AnnualCrop:   "#eab308",
  Agriculture:  "#eab308",
  agriculture:  "#eab308",
  Homestead:    "#f97316",
  homestead:    "#f97316",
  Residential:  "#f97316",
  residential:  "#f97316",
  River:        "#2563eb",
  river:        "#2563eb",
  SeaLake:      "#1d4ed8",
  "Water Body": "#2563eb",
  "water body": "#2563eb",
  Pasture:      "#84cc16",
  pasture:      "#84cc16",
  HerbaceousVegetation: "#65a30d",
  Highway:      "#6b7280",
  Industrial:   "#71717a",
  PermanentCrop:"#ca8a04",
  Unknown:      "#9ca3af",
};

function getLUColor(lu: string): string {
  return LAND_USE_COLORS[lu] || LAND_USE_COLORS["Unknown"];
}

// ── Types ─────────────────────────────────────────────────────────────────────
interface Claim {
  id: number;
  patta_holder_name: string;
  father_or_husband_name?: string;
  village_name: string;
  district: string;
  state: string;
  total_area_claimed: string;
  coordinates: string;
  claim_id: string;
  status: string;
  land_use?: string;
  ml_land_use?: string;
  ml_confidence?: number;
  claim_type?: string;
  eligible_scheme?: string;
  validation_status?: string;
  [key: string]: string | number | undefined;
}

interface SatelliteResult {
  land_use_class: string;
  confidence: number;
  source: string;
  method: string;
  thumbnail_url?: string;
  is_independent_verification?: boolean;  // set by backend
  raw_ml_label?: string;
  upload_validation?: string;
  consensus_score?: number; // 0.0 to 1.0 (Spatial harmony)
  gee_error?: string | null;
}

interface Intervention {
  priority: number;
  intervention: string;
  reason: string;
  scheme: string;
  urgency: string;
  beneficiaries_estimated: number;
}

interface ProgressRow {
  location: string;
  total_claims: number;
  verified: number;
  mismatch: number;
  not_validated: number;
  verified_pct: number;
}

// ── Map fly-to helper ─────────────────────────────────────────────────────────
const FlyTo: React.FC<{ lat: number; lon: number }> = ({ lat, lon }) => {
  const map = useMap();
  useEffect(() => { map.flyTo([lat, lon], 14, { duration: 1.2 }); }, [lat, lon]);
  return null;
};

// ── Area → polygon helper ─────────────────────────────────────────────────────
const areaToSquareBounds = (lat: number, lng: number, areaStr: string): [number, number][] => {
  try {
    let area = parseFloat(areaStr);
    if (isNaN(area)) return [];
    if ((areaStr || "").toLowerCase().includes("hectare")) area *= 10000;
    else if ((areaStr || "").toLowerCase().includes("acre")) area *= 4046.86;
    else return [];
    const side = Math.sqrt(area);
    const offsetLat = (side / 111320) / 2;
    const offsetLng = (side / (40075000 * Math.cos((lat * Math.PI) / 180) / 360)) / 2;
    return [
      [lat - offsetLat, lng - offsetLng],
      [lat - offsetLat, lng + offsetLng],
      [lat + offsetLat, lng + offsetLng],
      [lat + offsetLat, lng - offsetLng],
    ];
  } catch { return []; }
};

// ─────────────────────────────────────────────────────────────────────────────
const Atlas = () => {
  const [claims, setClaims]               = useState<Claim[]>([]);
  const [filteredClaims, setFilteredClaims] = useState<Claim[]>([]);
  const [selectedFeature, setSelectedFeature] = useState<Claim | null>(null);

  // Layers
  const [layers, setLayers] = useState({
    ifr: true, cfr: true, cr: false,
    landuse: true, waterBodies: true,
    satelliteAI: false, progressLayer: false,
  });

  // Filters
  const [query, setQuery]             = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [stateFilter, setStateFilter]   = useState("");
  const [searchResults, setSearchResults] = useState<Claim[]>([]);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [showDropdown, setShowDropdown]   = useState(false);
  const debounceRef = useRef<number | null>(null);

  // Satellite AI panel
  const [satelliteResult, setSatelliteResult]   = useState<SatelliteResult | null>(null);
  const [satelliteLoading, setSatelliteLoading]   = useState(false);
  const [activeTab, setActiveTab] = useState<"info" | "satellite" | "interventions">("info");

  // Interventions
  const [interventions, setInterventions]   = useState<Intervention[]>([]);
  const [interventionsLoading, setInterventionsLoading] = useState(false);
  const [interventionsMessage, setInterventionsMessage] = useState<string | null>(null);

  // Progress
  const [progressData, setProgressData]     = useState<ProgressRow[]>([]);
  const [progressLevel, setProgressLevel]   = useState<"state" | "district" | "village">("state");
  const [progressLoading, setProgressLoading] = useState(false);

  // Fly-to target
  const [flyTarget, setFlyTarget] = useState<{ lat: number; lon: number } | null>(null);

  // ── Load all claims ─────────────────────────────────────────────────────────
  useEffect(() => {
    fetch(buildBackendUrl("/atlas/claims"))
      .then(r => r.json())
      .then(data => {
        const enriched = (data.results || []).map((c: Claim) => ({
          ...c, status: c.status || "verified",
        }));
        setClaims(enriched);
        setFilteredClaims(enriched);
      })
      .catch(err => console.error("Atlas claims error:", err));
  }, []);

  // ── Auto-trigger scan for pending claims ────────────────────────────────────
  useEffect(() => {
    if (selectedFeature && selectedFeature.ml_land_use === "Pending Satellite Scan" && !satelliteLoading && !satelliteResult) {
      classifySatellite(selectedFeature);
    }
  }, [selectedFeature]);

  // ── Satellite AI classify ───────────────────────────────────────────────────
  const classifySatellite = async (claim: Claim) => {
    if (!claim.coordinates) return;
    const parts = String(claim.coordinates).split(",");
    const lat = parseFloat(parts[0]?.trim());
    const lon = parseFloat(parts[1]?.trim());
    if (isNaN(lat) || isNaN(lon)) return;

    setSatelliteLoading(true);
    setSatelliteResult(null);
    setActiveTab("satellite");

    try {
      const res = await fetch(buildBackendUrl("/atlas/classify-coordinates"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lat, lon,
          claim_id: claim.claim_id,
          total_area_claimed: claim.total_area_claimed,
        }),
      });

      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();

      if (data.classification && data.classification.land_use_class) {
        setSatelliteResult(data.classification);
      } else {
        // Backend returned something but no classification — use claim data directly
        const lu = claim.ml_land_use || claim.land_use || "Unknown";
        const conf = claim.ml_confidence ? Number(claim.ml_confidence) : 0.75;
        setSatelliteResult({
          land_use_class: lu,
          confidence: conf,
          source: "fra_document",
          method: `FRA document declared land use for ${claim.village_name || claim.district || claim.state}`,
        });
      }
    } catch (e) {
      console.error("Satellite classify error:", e);
      // Graceful fallback: use whatever land use we have on the claim
      const lu = claim.ml_land_use || claim.land_use;
      if (lu) {
        const conf = claim.ml_confidence ? Number(claim.ml_confidence) : 0.75;
        setSatelliteResult({
          land_use_class: lu,
          confidence: conf,
          source: "fra_document",
          method: `FRA document declared land use — ${claim.village_name || ""}, ${claim.district || ""}, ${claim.state || ""}`.trim().replace(/^,\s*|,\s*$/g, ""),
        });
      } else {
        setSatelliteResult({
          land_use_class: "Unknown",
          confidence: 0,
          source: "error",
          method: "Could not reach the backend. Check that the server is running.",
        });
      }
    } finally {
      setSatelliteLoading(false);
    }
  };

  // ── Interventions ───────────────────────────────────────────────────────────
  const loadInterventions = async (claim: Claim | null) => {
    if (!claim) {
      setInterventions([]);
      setInterventionsMessage("Please select a claim before loading interventions.");
      return;
    }

    setInterventionsLoading(true);
    setInterventionsMessage("Loading priority interventions...");
    try {
      const params = new URLSearchParams();
      if (claim.village_name) params.append("village", claim.village_name);
      if (claim.district)     params.append("district", claim.district);
      if (claim.state)        params.append("state", claim.state);
      const res = await fetch(buildBackendUrl(`/dss/interventions?${params}`));
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Server error ${res.status}: ${errorText}`);
      }
      const data = await res.json();
      const interventions = data.interventions || [];
      setInterventions(interventions);
      if (!interventions.length) {
        setInterventionsMessage(
          `No priority interventions were found for ${
            claim.village_name || claim.district || claim.state || 'this location'
          }. Try selecting another claim or refresh the dataset.`
        );
      } else {
        setInterventionsMessage(null);
      }
    } catch (e) {
      console.error("Interventions error:", e);
      setInterventions([]);
      setInterventionsMessage(
        e instanceof Error ? e.message : "Failed to load interventions."
      );
    } finally {
      setInterventionsLoading(false);
    }
  };

  // ── Progress ────────────────────────────────────────────────────────────────
  const loadProgress = async () => {
    setProgressLoading(true);
    try {
      const params = new URLSearchParams({ level: progressLevel });
      if (stateFilter) params.append("state", stateFilter);
      const res = await fetch(buildBackendUrl(`/atlas/progress?${params}`));
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setProgressData(data.results || []);
    } catch (e) {
      console.error("Progress load error:", e);
      setProgressData([]);
    } finally {
      setProgressLoading(false);
    }
  };

  // ── Layer toggle ────────────────────────────────────────────────────────────
  const toggleLayer = (layerId: string) =>
    setLayers(prev => ({ ...prev, [layerId]: !prev[layerId] }));

  // ── Marker icon ─────────────────────────────────────────────────────────────
  const createCustomIcon = (claim: Claim) => {
    // Priority: Real AI result > Claimed Land Use > Unknown
    // Explicitly ignore "Pending" strings for coloring
    const lu = (claim.ml_land_use && !claim.ml_land_use.includes("Pending"))
      ? claim.ml_land_use
      : (claim.land_use || "");
    
    let color = "#6b7280";
    if (layers.landuse) {
      color = getLUColor(lu);
    } else {
      const s = (claim.status || "").toLowerCase();
      if (s === "verified")  color = "#16a34a";
      else if (s === "pending") color = "#eab308";
      else if (s === "approved") color = "#2563eb";
      else if (s === "rejected") color = "#dc2626";
    }
    return L.divIcon({
      html: `<div style="background:${color};width:16px;height:16px;border-radius:50%;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.4)"></div>`,
      iconSize: [16, 16],
      className: "custom-marker",
    });
  };

  // ── Status badge ─────────────────────────────────────────────────────────────
  const getStatusBadge = (status: string) => {
    switch ((status || "").toLowerCase()) {
      case "verified":  return <Badge className="bg-green-600 text-white">Verified</Badge>;
      case "pending":   return <Badge className="bg-yellow-500 text-white">Pending</Badge>;
      case "approved":  return <Badge className="bg-blue-600 text-white">Approved</Badge>;
      case "rejected":  return <Badge className="bg-red-600 text-white">Rejected</Badge>;
      default:          return <Badge variant="secondary">{status || "Unknown"}</Badge>;
    }
  };

  const urgencyColor = (u: string) =>
    u === "HIGH" ? "bg-red-100 text-red-700" : u === "MEDIUM" ? "bg-yellow-100 text-yellow-700" : "bg-gray-100 text-gray-600";

  // ── Search ───────────────────────────────────────────────────────────────────
  const doSearch = async (q: string, status?: string, state?: string) => {
    if (!q && !status && !state) {
      setSearchResults([]); setFilteredClaims(claims); setShowDropdown(false); return;
    }
    setLoadingSearch(true); setShowDropdown(true);
    try {
      const params = new URLSearchParams();
      if (q)      params.append("q", q);
      if (status) params.append("status", status);
      if (state)  params.append("state", state);
      const res  = await fetch(buildBackendUrl(`/search?${params}`));
      const data = await res.json();
      const results = Array.isArray(data) ? data : (data.results || []);
      setSearchResults(results);
      if (!results.length) setFilteredClaims(claims);
    } catch { setSearchResults([]); setFilteredClaims(claims); }
    finally { setLoadingSearch(false); }
  };

  const handleQueryChange = (value: string) => {
    setQuery(value);
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(
      () => doSearch(value.trim(), statusFilter.trim(), stateFilter.trim()), 350
    );
  };

  const applyFilters = (allClaims: Claim[], status?: string, state?: string) => {
    let result = [...allClaims];
    if (status) result = result.filter(c => (c.status || "").toLowerCase() === status.toLowerCase());
    if (state)  result = result.filter(c => (c.state  || "").toLowerCase() === state.toLowerCase());
    setFilteredClaims(result);
  };

  const handleViewOnMap = (result: Claim) => {
    setFilteredClaims([result]);
    setSelectedFeature(result);
    setSearchResults([]); setShowDropdown(false); setQuery("");
    const parts = String(result.coordinates || "").split(",");
    const lat = parseFloat(parts[0]?.trim());
    const lon = parseFloat(parts[1]?.trim());
    if (!isNaN(lat) && !isNaN(lon)) setFlyTarget({ lat, lon });
  };

  const handleViewAllOnMap = () => {
    if (!searchResults.length) return;
    setFilteredClaims(searchResults); setSelectedFeature(null); setShowDropdown(false); setQuery("");
  };

  const handleResetMap = () => {
    setQuery(""); setStatusFilter(""); setStateFilter("");
    setSearchResults([]); setFilteredClaims(claims); setShowDropdown(false);
    setSelectedFeature(null); setSatelliteResult(null); setFlyTarget(null);
  };

  // ── Visible claims (layer filter) ───────────────────────────────────────────
  const visibleClaims = filteredClaims.filter(claim => {
    const lu = (claim.land_use || "").toLowerCase();
    const scheme = (claim.eligible_scheme || "").toLowerCase();
    const isIFR = lu.includes("forest") || scheme.includes("forest");
    const isCR  = lu.includes("homestead") || lu.includes("residential");
    const isCFR = lu.includes("forest") || lu.includes("river") || scheme.includes("mgnrega");
    const isWater = /river|lake|sea|water/.test(lu);
    return (
      (layers.ifr && isIFR) ||
      (layers.cr  && isCR)  ||
      (layers.cfr && isCFR) ||
      (layers.landuse) ||
      (layers.waterBodies && isWater) ||
      (!layers.ifr && !layers.cr && !layers.cfr && !layers.waterBodies)
    );
  });

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="h-screen flex">

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <div className="w-96 bg-white shadow-xl border-r flex flex-col overflow-hidden">

        {/* Header */}
        <div className="p-4 border-b bg-gradient-to-r from-green-800 to-green-600">
          <h1 className="text-xl font-bold text-white">FRA Atlas</h1>
          <p className="text-xs text-green-100">WebGIS · AI Asset Mapping · DSS</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">

          {/* Search */}
          <div className="relative">
            <Input
              value={query}
              onChange={e => handleQueryChange(e.target.value)}
              placeholder="Search by name, village, claim ID…"
              onFocus={() => searchResults.length > 0 && setShowDropdown(true)}
            />
            <div className="mt-2 flex gap-2">
              <select value={statusFilter}
                onChange={e => { setStatusFilter(e.target.value); applyFilters(claims, e.target.value, stateFilter); }}
                className="flex-1 px-2 py-1 rounded border text-sm">
                <option value="">All Status</option>
                <option value="verified">Verified</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
              <select value={stateFilter}
                onChange={e => { setStateFilter(e.target.value); applyFilters(claims, statusFilter, e.target.value); }}
                className="flex-1 px-2 py-1 rounded border text-sm">
                <option value="">All States</option>
                {SUPPORTED_STATES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            {/* Search dropdown */}
            {showDropdown && (
              <div className="absolute left-0 right-0 mt-1 bg-white shadow-lg border rounded-lg max-h-56 overflow-y-auto z-[1000]">
                {loadingSearch && <div className="p-3 text-sm text-gray-500">Searching…</div>}
                {!loadingSearch && !searchResults.length && (
                  <div className="p-3 text-sm text-gray-500">No results. Showing all {claims.length} claims.</div>
                )}
                {searchResults.map(r => (
                  <div key={r.id} className="p-3 hover:bg-gray-50 border-b flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium">{r.patta_holder_name}</p>
                      <p className="text-xs text-gray-500">{r.village_name}, {r.district}</p>
                      <p className="text-xs font-mono text-gray-400">{r.claim_id}</p>
                    </div>
                    <button onClick={() => handleViewOnMap(r)}
                      className="text-xs bg-green-700 text-white px-3 py-1 rounded hover:bg-green-800">
                      View
                    </button>
                  </div>
                ))}
                {searchResults.length > 1 && (
                  <div className="p-2 text-right">
                    <button onClick={handleViewAllOnMap}
                      className="text-xs bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700">
                      View all on map
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Layer controls */}
          <div>
            <h3 className="font-semibold text-sm mb-2 flex items-center gap-1">
              <Layers className="h-3 w-3" /> Map Layers
            </h3>
            <div className="grid grid-cols-2 gap-1 text-sm">
              {[
                { id: "ifr",          label: "IFR Claims" },
                { id: "cfr",          label: "CFR Claims" },
                { id: "cr",           label: "CR Claims" },
                { id: "landuse",      label: "Land Use AI" },
                { id: "waterBodies",  label: "Water Bodies" },
                { id: "satelliteAI",  label: "Satellite Tile" },
              ].map(layer => (
                <label key={layer.id} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox"
                    checked={layers[layer.id as keyof typeof layers]}
                    onChange={() => toggleLayer(layer.id)}
                    className="rounded border-gray-300 text-green-700" />
                  {layer.label}
                </label>
              ))}
            </div>
          </div>

          {/* Progress panel */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <h3 className="font-semibold text-sm flex items-center gap-1">
                <BarChart2 className="h-3 w-3" /> FRA Progress Tracking
              </h3>
              <div className="flex gap-1">
                {(["state", "district", "village"] as const).map(l => (
                  <button key={l}
                    onClick={() => setProgressLevel(l)}
                    className={`text-xs px-2 py-0.5 rounded ${progressLevel === l ? "bg-green-700 text-white" : "bg-gray-100 text-gray-600"}`}>
                    {l}
                  </button>
                ))}
              </div>
            </div>
            <Button size="sm" variant="outline" className="w-full text-xs" onClick={loadProgress}>
              {progressLoading ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
              Load {progressLevel}-level progress
            </Button>
            {progressData.length > 0 && (
              <div className="mt-2 space-y-1 max-h-48 overflow-y-auto">
                {progressData.map((row, i) => (
                  <div key={i} className="bg-gray-50 rounded p-2 text-xs">
                    <div className="flex justify-between font-medium">
                      <span>{row.location}</span>
                      <span className="text-green-700">{row.verified_pct}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-1 mt-1">
                      <div className="bg-green-600 h-1 rounded-full" style={{ width: `${row.verified_pct}%` }} />
                    </div>
                    <div className="text-gray-500 mt-0.5">
                      {row.verified}/{row.total_claims} verified
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Legend */}
          <div>
            <h3 className="font-semibold text-sm mb-2">Land Use Legend</h3>
            <div className="grid grid-cols-2 gap-1 text-xs">
              {Object.entries({
                "Forest / Vegetation": "#16a34a",
                "Agriculture":         "#eab308",
                "Homestead":           "#f97316",
                "Water Body":          "#2563eb",
                "Pasture":             "#84cc16",
                "Other":               "#9ca3af",
              }).map(([label, color]) => (
                <div key={label} className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: color }} />
                  <span className="text-gray-600">{label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Selected feature panel */}
          {selectedFeature && (
            <Card className="shadow-sm border-green-200">
              {/* Tab bar */}
              <div className="flex border-b text-xs">
                {[
                  { id: "info",          icon: <Info className="h-3 w-3" />,       label: "Info" },
                  { id: "satellite",     icon: <Satellite className="h-3 w-3" />,  label: "Satellite AI" },
                  { id: "interventions", icon: <Target className="h-3 w-3" />,     label: "DSS" },
                ].map(tab => (
                  <button key={tab.id}
                    onClick={() => {
                      setActiveTab(tab.id as typeof activeTab);
                      // Auto-load interventions when DSS tab is clicked
                      if (tab.id === "interventions" && interventions.length === 0 && !interventionsLoading) {
                        loadInterventions(selectedFeature);
                      }
                    }}
                    className={`flex-1 flex items-center justify-center gap-1 py-2 font-medium
                      ${activeTab === tab.id ? "border-b-2 border-green-700 text-green-700" : "text-gray-500"}`}>
                    {tab.icon} {tab.label}
                  </button>
                ))}
              </div>

              <CardContent className="text-sm p-3">

                {/* ── Info tab ─────────────────────────────────────────── */}
                {activeTab === "info" && (
                  <div className="space-y-2">
                    <p className="font-semibold">{selectedFeature.patta_holder_name}</p>
                    <p className="font-mono text-xs text-gray-500">{selectedFeature.claim_id}</p>
                    <div className="grid grid-cols-2 gap-y-1 text-xs">
                      <span className="text-gray-500">Claim Type</span>
                      <span>{selectedFeature.claim_type || "—"}</span>
                      <span className="text-gray-500">Village</span>
                      <span>{selectedFeature.village_name}</span>
                      <span className="text-gray-500">District</span>
                      <span>{selectedFeature.district}</span>
                      <span className="text-gray-500">State</span>
                      <span>{selectedFeature.state}</span>
                      <span className="text-gray-500">Area</span>
                      <span>{selectedFeature.total_area_claimed}</span>
                      <span className="text-gray-500">Land Use (claimed)</span>
                      <span className="font-semibold" style={{ color: getLUColor(selectedFeature.land_use || "") }}>
                        {selectedFeature.land_use || "—"}
                      </span>
                      <span className="text-gray-500">ML Prediction</span>
                      <span className="font-semibold" style={{ color: getLUColor(selectedFeature.ml_land_use || "") }}>
                        {selectedFeature.ml_land_use
                          ? `${selectedFeature.ml_land_use} (${((selectedFeature.ml_confidence as number || 0) * 100).toFixed(0)}%)`
                          : "—"}
                      </span>
                      <span className="text-gray-500">Scheme</span>
                      <span className="font-medium text-green-700">{selectedFeature.eligible_scheme || "—"}</span>
                    </div>
                    <div className="flex justify-between pt-2 border-t">
                      {getStatusBadge(selectedFeature.status)}
                      <button onClick={handleResetMap}
                        className="text-xs bg-gray-100 px-3 py-1 rounded hover:bg-gray-200">
                        Reset
                      </button>
                    </div>
                  </div>
                )}

                {/* ── Satellite AI tab ──────────────────────────────────── */}
                {activeTab === "satellite" && (
                  <div className="space-y-3">
                    <Button size="sm" className="w-full bg-green-700 hover:bg-green-800 text-white"
                      onClick={() => classifySatellite(selectedFeature)}
                      disabled={satelliteLoading}>
                      {satelliteLoading
                        ? <><Loader2 className="h-3 w-3 animate-spin mr-1" /> Analysing via AI…</>
                        : <><Satellite className="h-3 w-3 mr-1" /> Run Satellite AI Classification</>}
                    </Button>

                    {/* Show instant preview from claim data before classification runs */}
                    {!satelliteResult && !satelliteLoading && (selectedFeature.ml_land_use || selectedFeature.land_use) && (
                      <div className="bg-gray-50 border rounded-lg p-3 space-y-2 text-xs">
                        <p className="text-gray-400 font-medium uppercase tracking-wide text-[10px]">Data from FRA Document</p>
                        <div className="flex items-center justify-between">
                          <span className="text-gray-500">Declared Land Use</span>
                          <span className="font-semibold px-2 py-0.5 rounded"
                            style={{
                              background: getLUColor(selectedFeature.land_use || "") + "22",
                              color: getLUColor(selectedFeature.land_use || ""),
                              border: `1px solid ${getLUColor(selectedFeature.land_use || "")}`,
                            }}>
                            {selectedFeature.land_use || "—"}
                          </span>
                        </div>
                        {selectedFeature.ml_land_use && (
                          <div className="flex items-center justify-between">
                            <span className="text-gray-500">ML Insight</span>
                            {selectedFeature.ml_land_use === "Pending Satellite Scan" ? (
                              <Badge variant="outline" className="text-[10px] animate-pulse">Scan Required</Badge>
                            ) : (
                              <span className="font-semibold px-2 py-0.5 rounded"
                                style={{
                                  background: getLUColor(selectedFeature.ml_land_use) + "22",
                                  color: getLUColor(selectedFeature.ml_land_use),
                                  border: `1px solid ${getLUColor(selectedFeature.ml_land_use)}`,
                                }}>
                                {selectedFeature.ml_land_use}
                                {selectedFeature.ml_confidence ? ` (${(Number(selectedFeature.ml_confidence) * 100).toFixed(0)}%)` : ""}
                              </span>
                            )}
                          </div>
                        )}
                        <p className="text-gray-400 text-[10px]">
                          {selectedFeature.ml_land_use === "Pending Satellite Scan"
                            ? "Document scan detected. Click 'Run Satellite AI' to verify land."
                            : 'Click "Run Satellite AI" for real-time verification'}
                        </p>
                      </div>
                    )}

                    {satelliteResult && (() => {
                      const srcLabel: Record<string, string> = {
                        satellite_ai:         "🛰️ Live Satellite (GEE + CNN) — Verified",
                        db_ml_prediction:     "🤖 CNN Model (upload-time) — Verified",
                        fra_document:         "📄 FRA Document declared — Not independently verified",
                        coordinate_heuristic: "📍 Geographic Zone Estimate — Not verified",
                        error:                "❌ Error",
                      };

                      const claimedLu = (selectedFeature.land_use || "").toLowerCase();
                      const detectedLu = (satelliteResult.land_use_class || "").toLowerCase();
                      // Verification flags
                      // FIX: db_ml_prediction IS independent verification - the CNN ran on the
                      // actual uploaded image at upload time. Previously this was excluded,
                      // so the Atlas never showed a real match/mismatch for CNN results.
                      const isLiveSatellite = satelliteResult.source === "satellite_ai";
                      const isDbCNN = satelliteResult.source === "db_ml_prediction";
                      const isHeuristic = satelliteResult.source === "coordinate_heuristic";
                      // Only live satellite and CNN model counts as independent verification.
                      // Geographic heuristic and FRA document are NOT independent.
                      const isIndependentVerification = isLiveSatellite || isDbCNN;
                      
                       // Treat semantically equivalent land use labels as a match
                      // (e.g. "Residential" and "Homestead" are the same FRA category)
                      const EQUIVALENT_GROUPS: string[][] = [
                        ["residential", "homestead"],
                        ["forest", "forest / vegetation", "herbaceousvegetation"],
                        ["agriculture", "annualcrop", "permanentcrop"],
                        ["water body", "river", "sealake", "seaLake"],
                      ];
                      const luEquivalent = (a: string, b: string): boolean => {
                        if (a === b) return true;
                        return EQUIVALENT_GROUPS.some(group => group.includes(a) && group.includes(b));
                      };

                      const isMatch = isIndependentVerification && luEquivalent(detectedLu, claimedLu);
                      const isMismatch = isIndependentVerification && !luEquivalent(detectedLu, claimedLu) && selectedFeature.land_use;
                      
                      const color = getLUColor(satelliteResult.land_use_class);

                      return (
                        <div className="space-y-2 text-xs">
                          {/* Main result card */}
                          <div className="rounded-lg border p-3 space-y-2"
                            style={{ borderColor: color + "66", background: color + "0a" }}>
                            <div className="flex items-center justify-between">
                              <span className="text-gray-500 font-medium">Land Use Class</span>
                              <span className="font-bold text-sm px-2 py-0.5 rounded"
                                style={{ background: color + "22", color, border: `1px solid ${color}` }}>
                                {/* Prefer the document-declared label when AI detects an equivalent class */}
                                {isIndependentVerification && luEquivalent(detectedLu, claimedLu) && selectedFeature.land_use
                                  ? selectedFeature.land_use
                                  : satelliteResult.land_use_class}
                              </span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-gray-500">Confidence</span>
                              <div className="flex items-center gap-2">
                                <div className="w-20 bg-gray-200 rounded-full h-1.5">
                                  <div className="h-1.5 rounded-full"
                                    style={{ width: `${(satelliteResult.confidence * 100).toFixed(0)}%`, background: color }} />
                                </div>
                                <span className="font-mono font-semibold" style={{ color }}>
                                  {satelliteResult.confidence > 0
                                    ? `${(satelliteResult.confidence * 100).toFixed(1)}%`
                                    : "—"}
                                </span>
                              </div>
                            </div>
                            
                            {/* NEW: Spatial Consensus Gauge */}
                            {satelliteResult.consensus_score !== undefined && (
                              <div className="flex items-center justify-between">
                                <span className="text-gray-500">Spatial Harmony</span>
                                <div className="flex items-center gap-2">
                                  <div className="w-20 bg-gray-100 rounded-full h-1.5 border border-gray-200">
                                    <div className="h-full rounded-full transition-all duration-1000"
                                      style={{ 
                                        width: `${(satelliteResult.consensus_score * 100).toFixed(0)}%`, 
                                        background: `linear-gradient(90deg, ${color}cc, ${color})` 
                                      }} />
                                  </div>
                                  <span className="font-mono font-bold text-[10px]" style={{ color }}>
                                    {Math.round(satelliteResult.consensus_score * 100)}%
                                  </span>
                                </div>
                              </div>
                            )}
                            <div className="flex items-center justify-between">
                              <span className="text-gray-500">Source</span>
                              <span className="text-gray-700 text-right">
                                {srcLabel[satelliteResult.source] || satelliteResult.source}
                              </span>
                            </div>
                          </div>

                          {/* Method description */}
                          <div className="bg-gray-50 border rounded p-2 text-gray-500 leading-relaxed text-[11px]">
                            {satelliteResult.method}
                          </div>

                          {/* Satellite thumbnail if available */}
                          {satelliteResult.thumbnail_url && (
                            <div>
                              <p className="text-gray-400 text-[10px] mb-1 uppercase tracking-wide">Sentinel-2 Tile</p>
                              <img src={satelliteResult.thumbnail_url} alt="Satellite tile"
                                className="w-full rounded-lg border shadow-sm" />
                            </div>
                          )}

                          {/* NEW: Verification Unavailable Banner (Only if NO independent verification at all) */}
                          {!isIndependentVerification && (
                            <div className="p-2 bg-amber-50 text-amber-700 rounded-lg font-medium space-y-1 border border-amber-100">
                              <div className="flex items-center gap-2">
                                <AlertCircle className="h-3 w-3" />
                                <span>Verification System Limited</span>
                              </div>
                              <p className="font-normal text-[10px] text-amber-600 leading-tight">
                                GEE Error: {satelliteResult.gee_error || "Connection failure"}. 
                                Please run "earthengine authenticate" in your terminal.
                              </p>
                            </div>
                          )}

                          {isMatch && (
                            <div className="flex items-center gap-2 p-2 bg-green-50 text-green-700 rounded-lg font-medium">
                              <span>✅</span>
                              <span>
                                {isLiveSatellite ? "Live Satellite" : isDbCNN ? "CNN Model" : "Geographic Zone"} confirms: <b style={{ color: getLUColor(selectedFeature.land_use || "") }}>{selectedFeature.land_use}</b>
                                {detectedLu !== claimedLu && (
                                  <span className="font-normal text-green-600 ml-1">
                                    (detected as <b style={{ color }}>{satelliteResult.land_use_class}</b>)
                                  </span>
                                )}
                              </span>
                            </div>
                          )}

                          {isMismatch && (
                            <div className="p-3 bg-red-50 text-red-700 rounded-lg font-bold border border-red-200 animate-in fade-in zoom-in duration-300">
                              <div className="flex items-center gap-2 mb-1">
                                <Target className="h-4 w-4 text-red-600" />
                                <span>Possible False Claim Detected</span>
                              </div>
                              <div className="font-normal text-xs text-red-600 space-y-1">
                                <div className="flex justify-between">
                                  <span>Reported:</span>
                                  <b style={{ color: getLUColor(selectedFeature.land_use || "") }}>{selectedFeature.land_use}</b>
                                </div>
                                <div className="flex justify-between">
                                  <span>{isLiveSatellite ? "Live Satellite" : isDbCNN ? "CNN Model" : "Regional Heuristic"}:</span>
                                  <b style={{ color }}>{satelliteResult.land_use_class}</b>
                                </div>
                                <p className="mt-2 text-[10px] leading-tight opacity-80 pt-1 border-t border-red-100">
                                  The {isLiveSatellite ? "satellite scan" : isDbCNN ? "CNN model" : "geographic zone check"} indicates this land type does not match the claim. Manual investigation recommended.
                                </p>
                              </div>
                            </div>
                          )}
                          {isHeuristic && (
                            <div className="p-2 bg-orange-50 text-orange-700 rounded-lg text-[11px]">
                              📍 Zone estimate only — not real verification. Upload a satellite image or connect GEE for accurate results.
                            </div>
                          )}
                          {satelliteResult.source === "fra_document" && (
                            <div className="p-2 bg-blue-50 text-blue-700 rounded-lg text-[11px]">
                              📄 This shows what the claimant declared. Upload a satellite image of the land for CNN verification.
                            </div>
                          )}
                        </div>
                      );
                    })()}

                    {!satelliteResult && !satelliteLoading && !(selectedFeature.ml_land_use || selectedFeature.land_use) && (
                      <p className="text-xs text-gray-500 text-center py-4">
                        Click "Run Satellite AI Classification" to analyse land use via satellite imagery.
                      </p>
                    )}
                  </div>
                )}

                {/* ── DSS / Interventions tab ───────────────────────────── */}
                {activeTab === "interventions" && (
                  <div className="space-y-2">
                    <Button size="sm" className="w-full bg-green-700 hover:bg-green-800 text-white text-xs"
                      onClick={() => loadInterventions(selectedFeature)}
                      disabled={interventionsLoading}>
                      {interventionsLoading
                        ? <><Loader2 className="h-3 w-3 animate-spin mr-1" />Analysing DSS…</>
                        : <><Target className="h-3 w-3 mr-1" />Load Priority Interventions</>}
                    </Button>

                    {interventions.length > 0 && (
                      <div className="text-[10px] text-gray-400 bg-gray-50 rounded px-2 py-1">
                        📍 {selectedFeature.village_name || selectedFeature.district || selectedFeature.state} · {interventions.length} recommendations
                      </div>
                    )}

                    {interventions.map((iv, idx) => (
                      <div key={idx} className="border rounded-lg p-2.5 text-xs space-y-1.5 hover:shadow-sm transition-shadow">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-1.5">
                            <span className="w-5 h-5 rounded-full bg-green-100 text-green-700 flex items-center justify-center text-[10px] font-bold flex-shrink-0">
                              {iv.priority}
                            </span>
                            <span className="font-semibold text-gray-800 leading-tight">{iv.intervention}</span>
                          </div>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold flex-shrink-0 ${urgencyColor(iv.urgency)}`}>
                            {iv.urgency}
                          </span>
                        </div>
                        <p className="text-gray-500 leading-relaxed pl-6">{iv.reason}</p>
                        <div className="flex justify-between text-gray-400 pl-6 pt-0.5 border-t border-gray-100">
                          <span className="font-medium text-green-700">{iv.scheme}</span>
                          <span>~{iv.beneficiaries_estimated > 0 ? `${iv.beneficiaries_estimated} beneficiaries` : "area-wide"}</span>
                        </div>
                      </div>
                    ))}

                    {!interventions.length && !interventionsLoading && (
                      <div className="text-center py-6 space-y-2">
                        <Target className="h-8 w-8 text-gray-300 mx-auto" />
                        <p className="text-xs text-gray-500">
                          {interventionsMessage
                            ?? 'Click "Load Priority Interventions" for AI-driven DSS recommendations based on land use, demographics & scheme eligibility.'}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Footer stats */}
        <div className="border-t p-3 text-xs text-gray-500 flex justify-between">
          <span>Total: {claims.length} claims</span>
          <span>Visible: {visibleClaims.length}</span>
        </div>
      </div>

      {/* ── Map ──────────────────────────────────────────────────────────────── */}
      <div className="flex-1 relative">
        <MapContainer center={[22.9734, 78.6569]} zoom={6} style={{ height: "100%", width: "100%" }}>

          {/* Base tile layers */}
          <LayersControl position="topright">
            <LayersControl.BaseLayer checked name="OpenStreetMap">
              <TileLayer
                attribution='&copy; <a href="https://osm.org/copyright">OSM</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
            </LayersControl.BaseLayer>
            <LayersControl.BaseLayer name="Satellite (Esri)">
              <TileLayer
                attribution="Esri"
                url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              />
            </LayersControl.BaseLayer>
            <LayersControl.BaseLayer name="Terrain">
              <TileLayer
                attribution="Stamen"
                url="https://stamen-tiles.a.ssl.fastly.net/terrain/{z}/{x}/{y}.png"
              />
            </LayersControl.BaseLayer>
          </LayersControl>

          {/* Fly-to trigger */}
          {flyTarget && <FlyTo lat={flyTarget.lat} lon={flyTarget.lon} />}

          {/* Claim markers + polygons */}
          {visibleClaims.map(claim => {
            if (!claim.coordinates) return null;
            const parts = String(claim.coordinates).split(",");
            const lat = parseFloat(parts[0]?.trim());
            const lng = parseFloat(parts[1]?.trim());
            if (isNaN(lat) || isNaN(lng)) return null;

            const polygon = areaToSquareBounds(lat, lng, claim.total_area_claimed);
            // Ignore "Pending" for polygon coloring as well
            const lu = (claim.ml_land_use && !claim.ml_land_use.includes("Pending"))
              ? claim.ml_land_use
              : (claim.land_use || "");
            const fillColor = getLUColor(lu);

            return (
              <React.Fragment key={claim.id}>
                <Marker
                  position={[lat, lng]}
                  icon={createCustomIcon(claim)}
                  eventHandlers={{
                    click: () => {
                      setSelectedFeature(claim);
                      setActiveTab("info");
                      setInterventions([]);   // clear so DSS tab auto-loads fresh
                      setSatelliteResult(null);
                    }
                  }}
                >
                  <Popup>
                    <div className="w-56 text-sm space-y-1">
                      <p className="font-semibold">{claim.patta_holder_name}</p>
                      <p className="text-xs text-gray-500">{claim.claim_id}</p>
                      <p className="text-xs">{claim.village_name}, {claim.district}</p>
                      <div className="flex items-center gap-2 mt-1">
                        {getStatusBadge(claim.status)}
                        {lu && (
                          <span className="text-xs px-2 py-0.5 rounded"
                            style={{ background: fillColor + "22", color: fillColor, border: `1px solid ${fillColor}` }}>
                            {lu}
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => { setSelectedFeature(claim); setActiveTab("satellite"); classifySatellite(claim); }}
                        className="w-full text-xs bg-green-700 text-white py-1 rounded hover:bg-green-800 mt-1 flex items-center justify-center gap-1">
                        <Satellite size={10} /> Satellite AI Classify
                      </button>
                    </div>
                  </Popup>
                </Marker>
                {polygon.length > 0 && (
                  <Polygon
                    positions={polygon}
                    pathOptions={{ color: fillColor, weight: 2, fillOpacity: 0.25 }}
                    eventHandlers={{ click: () => { setSelectedFeature(claim); setActiveTab("info"); setInterventions([]); setSatelliteResult(null); } }}
                  />
                )}
              </React.Fragment>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
};

export default Atlas;

