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


const Dashboard = () => {
  // hooks
  const navigate = useNavigate();

const [kpiData, setKpiData] = useState([]);
const [claimsByState, setClaimsByState] = useState([]);
const [recentActivity, setRecentActivity] = useState([]);

useEffect(() => {
  fetch("http://127.0.0.1:8000/dashboard/summary")
    .then((res) => res.json())
    .then((data) => {
      setKpiData(data.kpis || []);
      setClaimsByState(data.statewise || []);
      setRecentActivity(data.recent || []);
    })
    .catch((err) => {
      console.error("Dashboard API error:", err);
    });
}, []);


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
  
  return (

    <div className="fra-container py-8">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">FRA Dashboard</h1>
          <p className="text-muted-foreground">
            Comprehensive overview of Forest Rights Act implementation across India
          </p>
        </div>
        <div className="flex gap-2 mt-4 lg:mt-0">
          <Button variant="outline" size="sm">
            <Filter className="h-4 w-4 mr-2" />
            Filters
          </Button>
          <Button variant="outline" size="sm">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
     <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
  {kpiData.map((kpi, index) => (
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
        {/* Claims by State */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                FRA Claims by State
              </CardTitle>
              <CardDescription>
                Verification progress across major states
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
       {claimsByState.map((item, index) => (
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
              <CardDescription>
                Latest FRA claim updates
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {recentActivity.map((activity) => (
                  <div key={activity.id} className="flex items-start space-x-3 p-3 rounded-lg bg-muted/50">
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

      {/* Quick Actions */}
      <div className="mt-8">
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>
              Common tasks and operations
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Button variant="outline" className="justify-start h-auto p-4">
                <div className="flex items-center space-x-3">
                  <MapPin className="h-8 w-8 text-primary" />
                  <div className="text-left">
                    <div className="font-medium" onClick={()=> navigate('/atlas')}>View Atlas</div>
                    <div className="text-sm text-muted-foreground">Interactive map</div>
                  </div>
                </div>
              </Button>
              <Button variant="outline" className="justify-start h-auto p-4">
                <div className="flex items-center space-x-3">
                  <FileText className="h-8 w-8 text-accent" />
                  <div className="text-left">
                    <div className="font-medium" onClick={()=> navigate('/upload')}>Upload Documents</div>
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