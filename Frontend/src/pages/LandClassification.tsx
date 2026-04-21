import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Upload, Image as ImageIcon, CheckCircle } from "lucide-react";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

interface ClassificationResult {
  filename: string;
  land_use_class: string;
  confidence: number;
}

const LandClassification = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<ClassificationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setResult(null);
      setError(null);
      
      const reader = new FileReader();
      reader.onload = (e) => {
        setPreview(e.target?.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleClassify = async () => {
    if (!selectedFile) return;

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch(`${BACKEND_URL}/model/classify-image`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Classification failed: ${response.statusText}`);
      }

      const data: ClassificationResult = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const getClassDescription = (className: string) => {
    const descriptions: Record<string, string> = {
      Forest: "Dense vegetation areas with trees and natural forest cover",
      AnnualCrop: "Agricultural fields with seasonal crops",
      PermanentCrop: "Orchards, vineyards, and perennial crop plantations",
      Pasture: "Grasslands used for livestock grazing",
      HerbaceousVegetation: "Natural grasslands and herbaceous plants",
      Residential: "Urban and residential areas with buildings",
      Industrial: "Industrial zones and manufacturing facilities",
      Highway: "Roads, highways, and transportation infrastructure",
      River: "Rivers, streams, and water bodies",
      SeaLake: "Large water bodies like seas and lakes"
    };
    return descriptions[className] || "Unknown land use type";
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            AI-Powered Land Use Classification
          </h1>
          <p className="text-lg text-gray-600">
            Upload a land photo to classify its use type using advanced machine learning
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          {/* Upload Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Upload Image
              </CardTitle>
              <CardDescription>
                Select a clear photo of the land area you want to classify
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="file-upload">Choose Image</Label>
                <Input
                  id="file-upload"
                  type="file"
                  accept="image/*"
                  onChange={handleFileSelect}
                  className="mt-1"
                />
              </div>

              {preview && (
                <div className="border rounded-lg p-4">
                  <img
                    src={preview}
                    alt="Preview"
                    className="w-full h-48 object-cover rounded"
                  />
                </div>
              )}

              <Button
                onClick={handleClassify}
                disabled={!selectedFile || loading}
                className="w-full"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <ImageIcon className="mr-2 h-4 w-4" />
                    Classify Land Use
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Results Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5" />
                Classification Results
              </CardTitle>
              <CardDescription>
                AI analysis of the uploaded image
              </CardDescription>
            </CardHeader>
            <CardContent>
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {result ? (
                <div className="space-y-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-primary mb-2">
                      {result.land_use_class}
                    </div>
                    <div className="text-sm text-gray-600 mb-4">
                      Confidence: {(result.confidence * 100).toFixed(1)}%
                    </div>
                  </div>

                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h4 className="font-semibold mb-2">Description:</h4>
                    <p className="text-sm text-gray-700">
                      {getClassDescription(result.land_use_class)}
                    </p>
                  </div>

                  <div className="bg-blue-50 p-4 rounded-lg">
                    <h4 className="font-semibold mb-2">FRA Relevance:</h4>
                    <p className="text-sm text-gray-700">
                      {result.land_use_class === 'Forest' 
                        ? 'This area may be eligible for forest rights claims under FRA.'
                        : result.land_use_class.includes('Crop')
                        ? 'Agricultural land - check eligibility for cultivation rights.'
                        : 'Non-forest land - verify FRA applicability for this area.'
                      }
                    </p>
                  </div>
                </div>
              ) : (
                <div className="text-center text-gray-500 py-8">
                  <ImageIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Upload an image and click "Classify Land Use" to see results</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Info Section */}
        <Card className="mt-8">
          <CardHeader>
            <CardTitle>About Land Classification</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-semibold mb-2">Supported Classes:</h4>
                <ul className="text-sm space-y-1">
                  <li>• Forest - Natural forest areas</li>
                  <li>• Annual Crop - Seasonal agriculture</li>
                  <li>• Permanent Crop - Orchards, vineyards</li>
                  <li>• Pasture - Grazing lands</li>
                  <li>• Herbaceous Vegetation - Grasslands</li>
                  <li>• Residential - Urban areas</li>
                  <li>• Industrial - Manufacturing zones</li>
                  <li>• Highway - Roads and infrastructure</li>
                  <li>• River - Water bodies</li>
                  <li>• SeaLake - Large water areas</li>
                </ul>
              </div>
              <div>
                <h4 className="font-semibold mb-2">How it Works:</h4>
                <ul className="text-sm space-y-1">
                  <li>• AI model trained on satellite imagery</li>
                  <li>• Analyzes visual patterns and textures</li>
                  <li>• Provides confidence scores</li>
                  <li>• Helps with FRA claim preparation</li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default LandClassification;