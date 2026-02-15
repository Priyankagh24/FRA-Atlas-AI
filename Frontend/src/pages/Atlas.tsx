import React, { useState, useEffect, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polygon,
} from "react-leaflet";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Info } from "lucide-react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// ✅ Fix for Leaflet icons in React
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});





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
  cultivation?: string;
  phone?: string;
  [key: string]: any;
}

const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

// Utility: area to square polygon
const areaToSquareBounds = (lat: number, lng: number, areaStr: string) => {
  try {
    let area = parseFloat(areaStr);
    if (isNaN(area)) return [];

    if ((areaStr || "").toLowerCase().includes("hectare")) {
      area = area * 10000;
    } else if ((areaStr || "").toLowerCase().includes("acre")) {
      area = area * 4046.86;
    } else {
      return [];
    }

    const side = Math.sqrt(area);
    const offsetLat = (side / 111320) / 2;
    const offsetLng =
      (side / (40075000 * Math.cos((lat * Math.PI) / 180) / 360)) / 2;

    return [
      [lat - offsetLat, lng - offsetLng],
      [lat - offsetLat, lng + offsetLng],
      [lat + offsetLat, lng + offsetLng],
      [lat + offsetLat, lng - offsetLng],
    ];
  } catch {
    return [];
  }
};

const Atlas = () => {
  const [layers, setLayers] = useState({
    ifr: true,
    cfr: true,
    cr: false,
    villages: true,
    landuse: false,
    waterBodies: true,
  });

  const [claims, setClaims] = useState<Claim[]>([]);
  const [filteredClaims, setFilteredClaims] = useState<Claim[]>([]);
  const [selectedFeature, setSelectedFeature] = useState<any>(null);

  // Search states
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [searchResults, setSearchResults] = useState<Claim[]>([]);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);

  const debounceRef = useRef<number | null>(null);


    // 🔍 DEBUG: verify markers & filters
  console.log("Total claims:", claims.length);
  console.log("Filtered claims:", filteredClaims.length);


  useEffect(() => {
  const loadAll = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/atlas/claims`);

      if (!res.ok) throw new Error(`HTTP error ${res.status}`);

      const data = await res.json();
      const results = data.results || [];

      const enriched = results.map((c: Claim) => ({
        ...c,
        status: c.status || "verified",
      }));

      setClaims(enriched);
      setFilteredClaims(enriched);

      console.log("Total claims:", enriched.length);
    } catch (err) {
      console.error("Error fetching FRA data:", err);
      setClaims([]);
      setFilteredClaims([]);
    }
  };

  loadAll();
}, []);


  const toggleLayer = (layerId: string) => {
    setLayers((prev) => ({ ...prev, [layerId]: !prev[layerId] }));
  };

  const createCustomIcon = (status: string) => {
    const safeStatus = (status || "").toLowerCase();
    let color = "#6b7280";
    if (safeStatus === "verified") color = "#16a34a";
    else if (safeStatus === "pending") color = "#eab308";
    else if (safeStatus === "approved") color = "#2563eb";
    else if (safeStatus === "rejected") color = "#dc2626";

    return L.divIcon({
      html: `<div style="background-color: ${color}; width: 18px; height: 18px; border-radius: 50%; border: 2px solid white;"></div>`,
      iconSize: [18, 18],
      className: "custom-marker",
    });
  };

  const getStatusBadge = (status: string) => {
    const safeStatus = (status || "").toLowerCase();
    switch (safeStatus) {
      case "verified":
        return <Badge className="bg-green-600 text-white">Verified</Badge>;
      case "pending":
        return <Badge className="bg-yellow-500 text-white">Pending</Badge>;
      case "approved":
        return <Badge className="bg-blue-600 text-white">Approved</Badge>;
      case "rejected":
        return <Badge className="bg-red-600 text-white">Rejected</Badge>;
      default:
        return <Badge variant="secondary">{status || "Unknown"}</Badge>;
    }
  };

  const buildSearchUrl = (q?: string, status?: string, state?: string) => {
    const base = BACKEND_URL.endsWith("/search")
      ? BACKEND_URL
      : `${BACKEND_URL}/search`;
    const params = new URLSearchParams();
    if (q) params.append("q", q);
    if (status) params.append("status", status);
    if (state) params.append("state", state);
    return `${base}?${params.toString()}`;
  };

  const doSearch = async (q: string, status?: string, state?: string) => {
    if (!q && !status && !state) {
      setSearchResults([]);
      setFilteredClaims(claims);
      setShowDropdown(false);
      return;
    }
    setLoadingSearch(true);
    setShowDropdown(true);
    try {
      const url = buildSearchUrl(q || undefined, status || undefined, state || undefined);
      const res = await fetch(url);
      const data = await res.json();
      const results = Array.isArray(data) ? data : (data.results || []);
      setSearchResults(results);
      if (results.length === 0) setFilteredClaims(claims);
    } catch (err) {
      console.error("Search error:", err);
      setSearchResults([]);
      setFilteredClaims(claims);
    } finally {
      setLoadingSearch(false);
    }
  };

  const handleQueryChange = (value: string) => {
    setQuery(value);
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      doSearch(value.trim(), statusFilter.trim(), stateFilter.trim());
    }, 350);
  };

  const handleViewOnMap = (result: Claim) => {
    setFilteredClaims([result]);
    setSelectedFeature(result);
    setSearchResults([]);
    setShowDropdown(false);
    setQuery("");
  };

  const handleViewAllOnMap = () => {
    if (!searchResults.length) return;
    setFilteredClaims(searchResults);
    setSelectedFeature(null);
    setShowDropdown(false);
    setQuery("");
  };

  const handleResetMap = () => {
    setQuery("");
    setStatusFilter("");
    setStateFilter("");
    setSearchResults([]);
    setFilteredClaims(claims);
    setShowDropdown(false);
  };


  const applyFilters = (
  allClaims: Claim[],
  status?: string,
  state?: string
) => {
  let result = [...allClaims];

  if (status) {
    result = result.filter(
      (c) => (c.status || "").toLowerCase() === status.toLowerCase()
    );
  }

  if (state) {
    result = result.filter(
      (c) => (c.state || "").toLowerCase() === state.toLowerCase()
    );
  }

  setFilteredClaims(result);
};

useEffect(() => {
  if (selectedFeature) {
    console.log("Selected Feature:", selectedFeature);
  }
}, [selectedFeature]);




  return (
    <div className="h-screen flex">
      {/* Sidebar */}
      <div className="w-80 bg-white shadow-xl border-r overflow-y-auto">
        <div className="p-5">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 text-transparent bg-clip-text">
            FRA Atlas
          </h1>
          <p className="text-sm text-gray-500 mb-4">
            Interactive WebGIS for Forest Rights Act
          </p>

          {/* Search Box */}
          <div className="relative mb-4">
            <Input
              value={query}
              onChange={(e) => handleQueryChange(e.target.value)}
              placeholder="Search by name, village, claim ID..."
              className="pl-9 rounded-xl border-gray-300"
              onFocus={() => {
                if (searchResults.length > 0) setShowDropdown(true);
              }}
            />


            

            {/* Filters */}
            <div className="mt-2 flex gap-2">
              <select
                value={statusFilter}
                onChange={(e) => {
                  const value = e.target.value;
                  setStatusFilter(value);
                  applyFilters(claims, value, stateFilter);
                }}

                className="flex-1 px-2 py-1 rounded border text-sm"
              >
                <option value="">All Status</option>
                <option value="verified">Verified</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>

              <select
                value={stateFilter}
                onChange={(e) => {
                  const value = e.target.value;
                  setStateFilter(value);
                  applyFilters(claims, statusFilter, value);
                }}

                className="flex-1 px-2 py-1 rounded border text-sm"
              >
                <option value="">All States</option>
                <option value="Chhattisgarh">Chhattisgarh</option>
                <option value="Madhya Pradesh">Madhya Pradesh</option>
                <option value="Odisha">Odisha</option>
                <option value="Tripura">Tripura</option>
                <option value="Jharkhand">Jharkhand</option>
              </select>
            </div>

            {/* Search Dropdown */}
            {showDropdown && (
              <div className="absolute left-0 right-0 mt-2 bg-white shadow-lg border rounded-md max-h-64 overflow-y-auto z-50">
                {loadingSearch && (
                  <div className="p-3 text-sm text-gray-500">Searching...</div>
                )}

                {!loadingSearch && searchResults.length === 0 && (
                  <div className="p-3 text-sm text-gray-600">
                    No results found. Showing {claims.length} total claims.
                  </div>
                )}

                {!loadingSearch &&
                  searchResults.length > 0 &&
                  searchResults.map((result) => (
                    <div
                      key={result.id}
                      className="p-3 hover:bg-gray-50 border-b flex justify-between items-start"
                    >
                      <div className="pr-2">
                        <h4 className="font-medium text-sm">
                          {result.patta_holder_name}
                        </h4>
                        <p className="text-xs text-gray-500">
                          {result.village_name}, {result.district}
                        </p>
                        <p className="text-xs font-mono text-gray-400 mt-1">
                          {result.claim_id}
                        </p>
                        <div className="mt-2">{getStatusBadge(result.status)}</div>
                      </div>
                      <button
                        onClick={() => handleViewOnMap(result)}
                        className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700"
                      >
                        View
                      </button>
                    </div>
                  ))}

                {searchResults.length > 1 && (
                  <div className="p-2 text-right">
                    <button
                      onClick={handleViewAllOnMap}
                      className="text-xs bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
                    >
                      View all on Map
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Selected Feature */}
          {selectedFeature && (
            <Card className="shadow">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Info className="h-4 w-4" /> Feature Information
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-2">
                <p className="font-medium text-lg">
                  {selectedFeature.patta_holder_name}
                </p>
                <p className="font-mono text-xs text-gray-500">
                  {selectedFeature.claim_id}
                </p>
                <div className="grid grid-cols-2 gap-y-1">
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
                </div>
                <div className="flex justify-between pt-2 border-t">
                  {getStatusBadge(selectedFeature.status)}
                  <button
                    onClick={handleResetMap}
                    className="text-xs bg-gray-200 px-3 py-1 rounded hover:bg-gray-300"
                  >
                    Reset
                  </button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 relative">
        <MapContainer
          center={[22.9734, 78.6569]}
          zoom={6}
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://osm.org/copyright">OSM</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {filteredClaims.map((claim) => {
            if (!claim.coordinates) return null;
            const [lat, lng] = claim.coordinates.split(",").map(Number);
            if (isNaN(lat) || isNaN(lng)) return null;
            const polygon = areaToSquareBounds(lat, lng, claim.total_area_claimed);
            return (
              <React.Fragment key={claim.id}>
                <Marker
                  position={[lat, lng]}
                  icon={createCustomIcon(claim.status)}
                  eventHandlers={{ click: () => setSelectedFeature(claim) }}
                >
                  <Popup>
                    <div className="w-64 text-sm">
                      <h4 className="font-semibold">{claim.patta_holder_name}</h4>
                      <p className="text-xs text-gray-500">{claim.claim_id}</p>
                      {getStatusBadge(claim.status)}
                    </div>
                  </Popup>
                </Marker>
                {polygon.length > 0 && (
                  <Polygon
                    positions={polygon}
                    pathOptions={{
                      color:
                        (claim.status || "").toLowerCase() === "verified"
                          ? "green"
                          : "blue",
                      weight: 2,
                      fillOpacity: 0.2,
                    }}
                    eventHandlers={{ click: () => setSelectedFeature(claim) }}
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
