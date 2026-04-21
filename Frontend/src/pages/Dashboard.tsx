import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";

import {
  BarChart3,
  TrendingUp,
  Users,
  FileText,
  MapPin,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Filter,
  Download
} from "lucide-react";

const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

// ✅ Single source of truth — matches backend SUPPORTED_STATES
const SUPPORTED_STATES = ["Madhya Pradesh", "Odisha", "Telangana", "Tripura"];

const Dashboard = () => {
  const [documents, setDocuments]       = useState([]);
  const [selectedState, setSelectedState] = useState("");
  const [kpiData, setKpiData]           = useState([]);
  const [claimsByState, setClaimsByState] = useState([]);
  const [recentActivity, setRecentActivity] = useState([]);

  const navigate = useNavigate();

  // ─── Remove empty + duplicate records ───────────────────────────────────────
  const uniqueDocsMap = new Map();
  documents.forEach((doc: any) => {
    const existing = uniqueDocsMap.get(doc.claim_id);
    if (!existing) {
      uniqueDocsMap.set(doc.claim_id, doc);
    } else if (new Date(doc.created_at) > new Date(existing.created_at)) {
      uniqueDocsMap.set(doc.claim_id, doc);
    }
  });

  // ✅ Keep only documents from supported states (guards against old DB rows)
  const uniqueDocs = Array.from(uniqueDocsMap.values()).filter((doc: any) =>
    SUPPORTED_STATES.map(s => s.toLowerCase()).includes(
      (doc.state || "").toLowerCase().trim()
    )
  );

  // ✅ Apply per-state dropdown filter on top
  const filteredDocs = uniqueDocs.filter((doc: any) =>
    selectedState
      ? doc.state?.toLowerCase().trim() === selectedState.toLowerCase().trim()
      : true
  );

  useEffect(() => {
    // Dashboard summary — backend already scopes to supported states
    fetch(`${BACKEND_URL}/dashboard/summary`)
      .then(res => res.json())
      .then(data => {
        setKpiData(data.kpis || []);
        // Extra safety: filter frontend-side too in case DB has stale rows
        const filtered = (data.statewise || []).filter((item: any) =>
          SUPPORTED_STATES.map(s => s.toLowerCase()).includes(
            (item.state_name || "").toLowerCase().trim()
          )
        );
        setClaimsByState(filtered);
        setRecentActivity(data.recent || []);
      })
      .catch(err => console.error("Summary error:", err));

    // All uploaded documents
    fetch(`${BACKEND_URL}/upload/all`)
      .then(res => res.json())
      .then(data => setDocuments(data.results || []))
      .catch(err => console.error("Upload fetch error:", err));
  }, []);

  // ─── Helpers ────────────────────────────────────────────────────────────────
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return <Badge className="status-verified">Completed</Badge>;
      case "pending":
        return <Badge className="status-pending">Pending</Badge>;
      case "processing":
        return <Badge className="status-pending">Processing</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const exportToCSV = () => {
    const headers = ["Name", "State", "Land Use", "Eligible Scheme", "Validation"];
    const rows = filteredDocs.map((doc: any) => [
      doc.patta_holder_name,
      doc.state,
      doc.land_use,
      doc.eligible_scheme,
      doc.validation_status,
    ]);
    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers, ...rows].map(e => e.join(",")).join("\n");
    const link = document.createElement("a");
    link.setAttribute("href", encodeURI(csvContent));
    link.setAttribute("download", "fra_export.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // ─── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="fra-container py-8">

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">FRA Dashboard</h1>
          <p className="text-muted-foreground">
            Forest Rights Act implementation — {SUPPORTED_STATES.join(", ")}
          </p>
        </div>
        <div className="flex gap-2 mt-4 lg:mt-0">
          {/* ✅ Dropdown only lists the 4 supported states */}
          <select
            value={selectedState}
            onChange={(e) => setSelectedState(e.target.value)}
            className="border px-3 py-1 rounded text-sm"
          >
            <option value="">All States</option>
            {SUPPORTED_STATES.map(state => (
              <option key={state} value={state}>{state}</option>
            ))}
          </select>
          <Button variant="outline" size="sm" onClick={exportToCSV}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {kpiData.map((kpi: any, index: number) => (
          <Card key={index}>
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground">
                {kpi.title}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {Number(kpi.value).toLocaleString()}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-8">

        {/* Claims by State — only 4 supported states */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                FRA Claims by State
              </CardTitle>
              <CardDescription>
                Verification progress — {SUPPORTED_STATES.join(" · ")}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {claimsByState.map((item: any, index: number) => (
                  <div key={index} className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium">{item.state_name}</span>
                      <span className="text-muted-foreground">
                        {item.titles_total}/{item.claims_total} verified
                      </span>
                    </div>
                    <Progress value={item.progress} className="h-2" />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>{item.progress}% completed</span>
                      <span>{item.claims_total - item.titles_total} pending</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent Activity */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                Recent Activity
              </CardTitle>
              <CardDescription>Latest FRA claim updates</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {recentActivity
                  .filter((activity: any) =>
                    activity.action &&
                    activity.action.trim() !== "" &&
                    activity.action.trim() !== '":' &&
                    activity.scheme !== "No Eligible Scheme"
                  )
                  .map((activity: any) => (
                    <div
                      key={activity.id}
                      className="flex items-start space-x-3 p-3 rounded-lg bg-muted/50"
                    >
                      <div className="w-2 h-2 bg-primary rounded-full mt-2" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium">{activity.action}</p>
                        <p className="text-xs text-muted-foreground">
                          {activity.village}, {activity.state}
                        </p>
                        <div className="flex items-center justify-between mt-2">
                          <span className="text-xs text-muted-foreground">
                            {activity.time}
                          </span>
                          {getStatusBadge(activity.status)}
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Uploaded Documents Table */}
      <Card className="mt-8">
        <CardHeader>
          <CardTitle>Uploaded Documents</CardTitle>
          <CardDescription>Scheme qualification and validation status</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b">
                <tr className="text-left">
                  <th className="py-2">Name</th>
                  <th>State</th>
                  <th>Land Use</th>
                  <th>Scheme</th>
                  <th>Validation</th>
                </tr>
              </thead>
              <tbody>
                {filteredDocs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-muted-foreground">
                      No documents found
                      {selectedState ? ` for ${selectedState}` : ""}.
                    </td>
                  </tr>
                ) : (
                  filteredDocs.map((doc: any) => (
                    <tr key={doc.id} className="border-b hover:bg-muted/50 h-10">
                      <td className="py-1">{doc.patta_holder_name}</td>
                      <td>{doc.state}</td>
                      <td>{doc.land_use}</td>
                      <td>
                        <Badge className="bg-blue-100 text-blue-700">
                          {doc.eligible_scheme}
                        </Badge>
                      </td>
                      <td>
                        <Badge
                          className={
                            doc.validation_status === "Matched"
                              ? "bg-green-100 text-green-700"
                              : "bg-yellow-100 text-yellow-700"
                          }
                        >
                          {doc.validation_status}
                        </Badge>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="mt-8">
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Common tasks and operations</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Button variant="outline" className="justify-start h-auto p-4">
                <div className="flex items-center space-x-3">
                  <MapPin className="h-8 w-8 text-primary" />
                  <div className="text-left">
                    <div className="font-medium" onClick={() => navigate('/atlas')}>
                      View Atlas
                    </div>
                    <div className="text-sm text-muted-foreground">Interactive map</div>
                  </div>
                </div>
              </Button>
              <Button variant="outline" className="justify-start h-auto p-4">
                <div className="flex items-center space-x-3">
                  <FileText className="h-8 w-8 text-accent" />
                  <div className="text-left">
                    <div className="font-medium" onClick={() => navigate('/upload')}>
                      Upload Documents
                    </div>
                    <div className="text-sm text-muted-foreground">Process claims</div>
                  </div>
                </div>
              </Button>
              <Button variant="outline" className="justify-start h-auto p-4">
                <div className="flex items-center space-x-3">
                  <Users className="h-8 w-8 text-warning" />
                  <div className="text-left">
                    <div className="font-medium">Scheme Matching</div>
                    <div className="text-sm text-muted-foreground">Find benefits</div>
                  </div>
                </div>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

    </div>
  );
};

export default Dashboard;
