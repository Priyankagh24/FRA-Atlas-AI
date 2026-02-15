import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowRight, Map, Upload, MessageCircle, BarChart, Shield, Users } from "lucide-react";
import { Link } from "react-router-dom";
import indiaMap from "@/assets/india-map.jpg";
import dashboardPreview from "@/assets/dashboard-preview.jpg";

const LandingPage = () => {
  const features = [
    {
      icon: Map,
      title: "Interactive FRA Atlas",
      description: "Explore IFR, CR, and CFR claims on an interactive WebGIS map with detailed village boundaries and land-use data.",
    },
    {
      icon: Upload,
      title: "Document Digitization", 
      description: "Upload scanned FRA documents for automated OCR extraction and metadata processing.",
    },
    {
      icon: BarChart,
      title: "Progress Tracking",
      description: "Monitor FRA implementation with real-time KPIs, progress bars, and comprehensive analytics.",
    },
    {
      icon: MessageCircle,
      title: "AI Assistant",
      description: "Get instant help with FRA processes, data queries, and scheme recommendations through our chatbot.",
    },
    {
      icon: Shield,
      title: "Scheme Integration",
      description: "Connect FRA claims with relevant CSS schemes for comprehensive community development.",
    },
    {
      icon: Users,
      title: "Community Empowerment",
      description: "Built specifically for tribal communities with accessible design and multilingual support.",
    },
  ];

  const stats = [
    { label: "Villages Mapped", value: "2,500+" },
    { label: "Claims Verified", value: "15,000+" },
    { label: "CFR Areas", value: "500+" },
    { label: "Active Users", value: "1,200+" },
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative fra-section bg-gradient-to-br from-background to-muted overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <img 
            src={indiaMap} 
            alt="Map of India showing forest rights areas" 
            className="w-full h-full object-cover"
          />
        </div>
        <div className="relative fra-container">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="animate-fade-in">
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
                <span className="fra-gradient-text">FRA Atlas</span>
                <br />
                <span className="text-foreground">Empowering Tribal Communities</span>
              </h1>
              <p className="text-xl text-muted-foreground mb-8 leading-relaxed">
                Comprehensive Forest Rights Act management platform with interactive mapping, 
                document digitization, and AI-powered decision support for tribal communities across India.
              </p>
              <div className="flex flex-col sm:flex-row gap-4">
                <Button asChild size="xl" variant="hero">
                  <Link to="/atlas">
                    Explore Atlas <ArrowRight className="ml-2 h-5 w-5" />
                  </Link>
                </Button>
                <Button asChild size="xl" variant="outline">
                  <Link to="/upload">Upload Documents</Link>
                </Button>
              </div>
            </div>
            
            <div className="relative hover-lift">
              <div className="fra-card-elevated bg-gradient-card">
                <img 
                  src={dashboardPreview} 
                  alt="FRA Atlas Dashboard Preview" 
                  className="w-full h-64 object-cover rounded-lg"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent rounded-lg" />
                <div className="absolute bottom-4 left-4 text-white">
                  <h3 className="font-semibold">Interactive Dashboard</h3>
                  <p className="text-sm opacity-90">Real-time FRA analytics</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 bg-primary text-primary-foreground">
        <div className="fra-container">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((stat, index) => (
              <div key={index} className="text-center animate-fade-in" style={{ animationDelay: `${index * 100}ms` }}>
                <div className="text-3xl md:text-4xl font-bold mb-2">{stat.value}</div>
                <div className="text-primary-foreground/80">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="fra-section">
        <div className="fra-container">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Comprehensive <span className="fra-gradient-text">FRA Management</span>
            </h2>
            <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
              Everything you need to manage Forest Rights Act implementation, 
              from document processing to community empowerment.
            </p>
          </div>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <Card key={index} className="hover-lift animate-fade-in" style={{ animationDelay: `${index * 100}ms` }}>
                <CardHeader>
                  <div className="w-12 h-12 bg-gradient-accent rounded-lg flex items-center justify-center mb-4">
                    <feature.icon className="h-6 w-6 text-accent-foreground" />
                  </div>
                  <CardTitle>{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-base">{feature.description}</CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="fra-section bg-gradient-hero text-primary-foreground">
        <div className="fra-container text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-6">
            Ready to Transform Forest Rights Management?
          </h2>
          <p className="text-xl mb-8 opacity-90 max-w-2xl mx-auto">
            Join thousands of tribal communities already using FRA Atlas to secure their forest rights 
            and access government schemes.
          </p>
          {/* <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button asChild size="xl" variant="secondary">
              <Link to="/dashboard">View Dashboard</Link>
            </Button>
            <Button asChild size="xl" variant="secondary">
              <Link to="/support">Get Support</Link>
            </Button>
          </div> */}
        </div>
      </section>
    </div>
  );
};

export default LandingPage;