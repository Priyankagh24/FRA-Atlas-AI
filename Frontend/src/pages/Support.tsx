import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Lightbulb, 
  TrendingUp, 
  Users, 
  Droplets,
  Zap,
  Home,
  ArrowRight,
  MapPin,
  AlertTriangle,
  CheckCircle2
} from "lucide-react";

const Support = () => {
  // Mock recommendation data
  const villageRecommendations = [
    {
      village: "Koraput Village",
      district: "Koraput",
      state: "Odisha",
      population: 1250,
      fraStatus: "65% verified",
      waterIndex: 0.3,
      recommendations: [
        {
          scheme: "Jal Jeevan Mission",
          priority: "High",
          reason: "Low water access index",
          benefit: "Piped water supply",
          eligibility: 95,
          icon: Droplets,
        },
        {
          scheme: "PM Awas Yojana",
          priority: "Medium", 
          reason: "Housing infrastructure gap",
          benefit: "Housing assistance ₹1.2L",
          eligibility: 80,
          icon: Home,
        },
        {
          scheme: "MGNREGA",
          priority: "High",
          reason: "Employment opportunities",
          benefit: "100 days guaranteed work",
          eligibility: 100,
          icon: Users,
        },
      ],
    },
    {
      village: "Bastar Block",
      district: "Bastar",
      state: "Chhattisgarh",
      population: 2100,
      fraStatus: "78% verified",
      waterIndex: 0.7,
      recommendations: [
        {
          scheme: "PM Solar Panel",
          priority: "High",
          reason: "Forest area - ideal for solar",
          benefit: "Free solar installation",
          eligibility: 90,
          icon: Zap,
        },
        {
          scheme: "Forest Conservation",
          priority: "Medium",
          reason: "CFR area development", 
          benefit: "Conservation incentives",
          eligibility: 85,
          icon: TrendingUp,
        },
      ],
    },
  ];

  const schemeCategories = [
    {
      title: "Water & Sanitation",
      count: 12,
      schemes: ["Jal Jeevan Mission", "Swachh Bharat Mission", "PMAY Water Component"],
      color: "bg-tribal",
    },
    {
      title: "Housing & Infrastructure",
      count: 8,
      schemes: ["PM Awas Yojana", "Rural Housing Scheme", "Infrastructure Development"],
      color: "bg-success",
    },
    {
      title: "Employment & Livelihood",
      count: 15,
      schemes: ["MGNREGA", "PM-KISAN", "Rural Livelihood Mission"],
      color: "bg-warning",
    },
    {
      title: "Forest & Environment",
      count: 6,
      schemes: ["Forest Conservation", "Green India Mission", "Biodiversity Conservation"],
      color: "bg-forest",
    },
  ];

  const getPriorityColor = (priority: string) => {
    switch (priority.toLowerCase()) {
      case 'high':
        return 'bg-destructive text-destructive-foreground';
      case 'medium':
        return 'bg-warning text-warning-foreground';
      case 'low':
        return 'bg-success text-success-foreground';
      default:
        return 'bg-muted text-muted-foreground';
    }
  };

  return (
    <div className="fra-container py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Decision Support System</h1>
        <p className="text-muted-foreground">
          AI-powered recommendations for government schemes based on FRA data and village characteristics
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        {schemeCategories.map((category, index) => (
          <Card key={index} className="hover-lift">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className={`w-10 h-10 ${category.color} rounded-lg flex items-center justify-center`}>
                  <Lightbulb className="h-5 w-5 text-white" />
                </div>
                <Badge variant="secondary">{category.count}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <h3 className="font-semibold mb-2">{category.title}</h3>
              <div className="space-y-1">
                {category.schemes.slice(0, 2).map((scheme, i) => (
                  <p key={i} className="text-xs text-muted-foreground">• {scheme}</p>
                ))}
                {category.schemes.length > 2 && (
                  <p className="text-xs text-muted-foreground">
                    +{category.schemes.length - 2} more
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Village Recommendations */}
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold">Village-wise Recommendations</h2>
          <Button variant="outline">
            <MapPin className="h-4 w-4 mr-2" />
            View on Map
          </Button>
        </div>

        {villageRecommendations.map((village, index) => (
          <Card key={index} className="overflow-hidden">
            <CardHeader className="bg-gradient-card">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <MapPin className="h-5 w-5" />
                    {village.village}
                  </CardTitle>
                  <CardDescription>
                    {village.district}, {village.state} • Population: {village.population.toLocaleString()}
                  </CardDescription>
                </div>
                <div className="text-right">
                  <Badge className="status-verified mb-2">{village.fraStatus}</Badge>
                  <p className="text-sm text-muted-foreground">
                    Water Index: {village.waterIndex.toFixed(1)}/1.0
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6">
              <div className="grid gap-4">
                <h4 className="font-semibold text-lg flex items-center gap-2">
                  <Lightbulb className="h-5 w-5 text-warning" />
                  Recommended Schemes
                </h4>
                
                <div className="grid gap-4">
                  {village.recommendations.map((rec, recIndex) => (
                    <div key={recIndex} className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors">
                      <div className="flex items-start space-x-4">
                        <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                          <rec.icon className="h-5 w-5 text-primary" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h5 className="font-medium">{rec.scheme}</h5>
                            <Badge className={getPriorityColor(rec.priority)}>
                              {rec.priority} Priority
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground mb-2">{rec.reason}</p>
                          <p className="text-sm font-medium text-success">{rec.benefit}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="flex items-center gap-2 mb-2">
                          <CheckCircle2 className="h-4 w-4 text-success" />
                          <span className="text-sm font-medium">{rec.eligibility}% match</span>
                        </div>
                        <Button size="sm" variant="outline">
                          View Details
                          <ArrowRight className="h-3 w-3 ml-1" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-between pt-4 border-t">
                  <div className="flex items-center text-sm text-muted-foreground">
                    <AlertTriangle className="h-4 w-4 mr-2" />
                    Recommendations updated based on latest FRA data
                  </div>
                  <Button variant="hero" size="sm">
                    Generate Report
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* AI Insights */}
      <Card className="mt-8 bg-gradient-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            AI Insights & Patterns
          </CardTitle>
          <CardDescription>
            Machine learning insights from FRA and scheme data
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium mb-3">Key Findings</h4>
              <ul className="space-y-2 text-sm">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" />
                  Villages with 70%+ FRA verification show higher scheme adoption
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" />
                  Water access schemes have 85% success rate in tribal areas
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" />
                  Combined FRA+MGNREGA shows improved livelihood outcomes
                </li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium mb-3">Trending Opportunities</h4>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm">Solar energy schemes</span>
                  <Badge variant="outline">+15%</Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm">Digital literacy programs</span>
                  <Badge variant="outline">+22%</Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm">Organic farming initiatives</span>
                  <Badge variant="outline">+18%</Badge>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Support;