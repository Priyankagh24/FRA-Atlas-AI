import React, { useState, useCallback, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";


import { 
  Upload as UploadIcon, 
  FileText, 
  Check, 
  X, 
  Eye,
  Scan,
  FileCheck,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

// Use .env backend URL
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

interface ExtractedData {
  patta_holder_name: string;
  father_or_husband_name: string;
  age: number;
  gender: string;
  address: string;
  village_name: string;
  block: string;
  district: string;
  state: string;
  total_area_claimed: string;
  coordinates: string;
  land_use: string;
  claim_id: string;
  claim_type: string;          // ✅ ADD THIS
  date_of_application: string;
  water_bodies: string;
  forest_cover: string;
  homestead: string;
  confidence?: number;
}



interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  status: 'uploading' | 'processing' | 'completed' | 'error';
  progress: number;
  extractedData?: ExtractedData;
  fileObj: File;
}

// 🔹 Utility: normalize backend keys like "Patta-Holder Name" → "patta_holder_name"
const normalizeKeys = (rawData: Record<string, any>): ExtractedData => {
  const map: Record<string, string> = {
    "Type of Claim": "claim_type",
    "Verification Status": "verification_status",
    "Extraction Confidence": "confidence",
    "Processed Timestamp": "processed_timestamp",
    "Patta-Holder Name": "patta_holder_name",
    "Father/Husband Name": "father_or_husband_name",
    "Age": "age",
    "Gender": "gender",
    "Address": "address",
    "Village Name": "village_name",
    "Block": "block",
    "District": "district",
    "State": "state",
    "Total Area Claimed": "total_area_claimed",
    "Coordinates": "coordinates",
    "Land Use": "land_use",
    "Claim ID": "claim_id",
    "Date of Application": "date_of_application",
    "Water bodies": "water_bodies",
    "Forest cover": "forest_cover",
    "Homestead": "homestead",
  };

  const result: any = {};
  Object.entries(map).forEach(([backendKey, frontendKey]) => {
    if (backendKey in rawData) {
      if (frontendKey === "age") {
        result[frontendKey] = Number(rawData[backendKey] || 0);
      } else {
        result[frontendKey] = rawData[backendKey] || "";
      }
    }
  });

  return result as ExtractedData;
};

const Upload = () => {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const { toast } = useToast();
  const previewRef = useRef<HTMLDivElement>(null); // 🔹 For scroll to preview

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  }, []);

  const handleFiles = async (fileList: File[]) => {
    const newFiles: UploadedFile[] = fileList.map((file, index) => ({
      id: `${Date.now()}-${index}`,
      name: file.name,
      size: file.size,
      type: file.type,
      status: 'uploading',
      progress: 0,
      fileObj: file,
    }));

    setFiles(prev => [...prev, ...newFiles]);

    for (const file of newFiles) {
      await uploadFile(file);
    }
  };

   const uploadFile = async (file: UploadedFile) => {
  try {
    setFiles(prev =>
      prev.map(f =>
        f.id === file.id ? { ...f, status: "processing", progress: 50 } : f
      )
    );

    const formData = new FormData();
    formData.append("file", file.fileObj);

    const res = await fetch(`${BACKEND_URL}/upload/`, {
      method: "POST",
      body: formData,
    });

    // ✅ READ RESPONSE ONLY ONCE
    const raw = await res.json();
    console.log("Upload response:", raw);

    if (!res.ok) {
      throw new Error(raw?.detail || "Upload failed");
    }

    const normalized = normalizeKeys(raw.data);

    setFiles(prev =>
      prev.map(f =>
        f.id === file.id
          ? {
              ...f,
              status: "completed",
              progress: 100,
              extractedData: normalized,
            }
          : f
      )
    );

    toast({
      title: "Upload successful",
      description: `${file.name} processed successfully.`,
    });
  } catch (err: any) {
    console.error(err);

    setFiles(prev =>
      prev.map(f =>
        f.id === file.id ? { ...f, status: "error", progress: 100 } : f
      )
    );

    toast({
      title: "Upload failed",
      description: err.message || "Could not process file",
      variant: "destructive",
    });
  }
};


  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'uploading':
        return <UploadIcon className="h-4 w-4 animate-pulse" />;
      case 'processing':
        return <Scan className="h-4 w-4 animate-spin" />;
      case 'completed':
        return <Check className="h-4 w-4 text-green-500" />;
      case 'error':
        return <X className="h-4 w-4 text-red-500" />;
      default:
        return <FileText className="h-4 w-4" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'uploading':
        return <Badge variant="secondary">Uploading</Badge>;
      case 'processing':
        return <Badge className="status-pending">Processing</Badge>;
      case 'completed':
        return <Badge className="status-verified">Completed</Badge>;
      case 'error':
        return <Badge variant="destructive">Error</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  return (
    <div className="fra-container py-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Document Upload & Digitization</h1>
          <p className="text-muted-foreground">
            Upload scanned FRA documents for automated OCR extraction and metadata processing
          </p>
        </div>

        {/* Upload Area */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UploadIcon className="h-5 w-5" />
              Upload FRA Documents
            </CardTitle>
            <CardDescription>
              Drag and drop files or click to select. Supports PDF, JPG, PNG formats.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                dragActive 
                  ? 'border-primary bg-primary/5' 
                  : 'border-border hover:border-primary/50'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                type="file"
                multiple
                accept=".pdf,.jpg,.jpeg,.png"
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={(e) => e.target.files && handleFiles(Array.from(e.target.files))}
              />
              
              <div className="flex flex-col items-center space-y-4">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center">
                  <UploadIcon className="h-8 w-8 text-primary" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold">Drop files here</h3>
                  <p className="text-muted-foreground">or click to browse from your device</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Processing Queue */}
        {files.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileCheck className="h-5 w-5" />
                Processing Queue
              </CardTitle>
              <CardDescription>
                Track the status of your uploaded documents
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {files.map((file) => (
                  <div key={file.id} className="flex items-center space-x-4 p-4 border rounded-lg">
                    <div className="flex items-center space-x-3 flex-1">
                      {getStatusIcon(file.status)}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{file.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {formatFileSize(file.size)} • {file.type}
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-4">
                      {(file.status === 'uploading' || file.status === 'processing') && (
                        <div className="w-24">
                          <Progress value={file.progress} className="h-2" />
                          <p className="text-xs text-muted-foreground mt-1">
                            {file.progress}%
                          </p>
                        </div>
                      )}
                      
                      {getStatusBadge(file.status)}
                      
                      {file.status === 'completed' && (
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => {
                            toast({
                              title: "OCR Data Ready",
                              description: `Showing extracted details for ${file.name}`,
                            });
                            // 🔹 Scroll to preview section
                            previewRef.current?.scrollIntoView({ behavior: "smooth" });
                          }}
                        >
                          <Eye className="h-4 w-4 mr-2" />
                          View
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Extracted Data Preview */}
        {files.some(f => f.status === 'completed' && f.extractedData) && (
          <Card ref={previewRef}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Scan className="h-5 w-5" />
                Extracted Data Preview
              </CardTitle>
              <CardDescription>
                OCR and NER extracted information from your documents
              </CardDescription>
            </CardHeader>
            <CardContent>
              {files.filter(f => f.status === 'completed' && f.extractedData).map((file) => (
                <div key={file.id} className="mb-6 border-b pb-4">
                  <h3 className="font-semibold mb-2">{file.name}</h3>
                  <div className="grid md:grid-cols-2 gap-6">
                    <div className="mt-4 text-sm text-muted-foreground">
                     <p><strong>Claim ID:</strong> {file.extractedData?.claim_id}</p>
                     <p><strong>Claim Type:</strong> {file.extractedData?.claim_type}</p>
                     <p><strong>Status:</strong> {file.extractedData?.verification_status}</p>
                     <p><strong>Coordinates:</strong> {file.extractedData?.coordinates}</p>
                     <p><strong>Extraction Confidence:</strong> {(file.extractedData?.confidence ?? 0.85) * 100}%</p>
                     <p><strong>Processed At:</strong> {file.extractedData?.processed_timestamp}</p>
                    </div>

                    <div className="space-y-2">
                      <p><strong>Applicant:</strong> {file.extractedData?.patta_holder_name}</p>
                      <p><strong>Father/Husband:</strong> {file.extractedData?.father_or_husband_name}</p>
                      <p><strong>Village:</strong> {file.extractedData?.village_name}</p>
                      <p><strong>District:</strong> {file.extractedData?.district}</p>
                      <p><strong>State:</strong> {file.extractedData?.state}</p>
                    </div>
                    <div className="space-y-2">
                      <p><strong>Age:</strong> {file.extractedData?.age}</p>
                      <p><strong>Gender:</strong> {file.extractedData?.gender}</p>
                      <p><strong>Area:</strong> {file.extractedData?.total_area_claimed}</p>
                      <p><strong>Land Use:</strong> {file.extractedData?.land_use}</p>
                      <p><strong>Application Date:</strong> {file.extractedData?.date_of_application}</p>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default Upload;
