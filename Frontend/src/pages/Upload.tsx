import React, { useState, useCallback, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";

import {
  Upload as UploadIcon,
  FileText,
  X,
  Eye,
  Scan,
  FileCheck,
  Image as ImageIcon,
  AlertTriangle,
  Loader2,
  CheckCircle2,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

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
  claim_type: string;
  date_of_application: string;
  water_bodies: string;
  forest_cover: string;
  homestead: string;
  processed_timestamp?: string;
  confidence?: number;
  eligible_scheme?: string;
  validation_status?: string;
  ml_prediction?: string;
  ml_confidence?: number;
}

interface UploadResult {
  extractedData: ExtractedData;
  docFileName: string;
  photoFileName: string;
  photoPreview: string;
}

type UploadStatus = 'idle' | 'uploading' | 'processing' | 'completed' | 'error';

const normalizeKeys = (rawData?: Record<string, unknown>): ExtractedData => {
  if (!rawData) return {} as ExtractedData;
  const map: Record<string, string> = {
    "Type of Claim": "claim_type",
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
  const result: Record<string, unknown> = {};
  Object.entries(map).forEach(([bk, fk]) => {
    if (bk in rawData) {
      result[fk] = fk === "age" ? Number(rawData[bk] || 0) : (rawData[bk] as string) || "";
    }
  });
  return result as unknown as ExtractedData;
};

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const getClassDescription = (className: string) => {
  const d: Record<string, string> = {
    Forest: "Dense vegetation areas with trees and natural forest cover",
    AnnualCrop: "Agricultural fields with seasonal crops",
    PermanentCrop: "Orchards, vineyards, and perennial crop plantations",
    Pasture: "Grasslands used for livestock grazing",
    HerbaceousVegetation: "Natural grasslands and herbaceous plants",
    Residential: "Urban and residential areas with buildings",
    Industrial: "Industrial zones and manufacturing facilities",
    Highway: "Roads, highways, and transportation infrastructure",
    River: "Rivers, streams, and water bodies",
    SeaLake: "Large water bodies like seas and lakes",
  };
  return d[className] || "Land use type identified by AI analysis";
};

// ── Drop Zone ──────────────────────────────────────────────────────────────

interface DropZoneProps {
  label: string;
  accept: string;
  hint: string;
  icon: React.ReactNode;
  file: File | null;
  preview?: string | null;
  error?: string;
  disabled?: boolean;
  onFile: (file: File) => void;
  onClear: () => void;
}

const DropZone: React.FC<DropZoneProps> = ({
  label, accept, hint, icon, file, preview, error, disabled, onFile, onClear,
}) => {
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation();
    setDragActive(e.type === "dragenter" || e.type === "dragover");
  };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragActive(false);
    const f = e.dataTransfer.files?.[0]; if (f) onFile(f);
  };

  return (
    <div className="space-y-2">
      <p className="text-sm font-semibold text-gray-700">{label}</p>
      {file ? (
        <div className="border rounded-lg p-4 bg-green-50 border-green-200">
          {preview && <img src={preview} alt="Land preview" className="w-full h-36 object-cover rounded mb-3" />}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-green-800 truncate">{file.name}</p>
                <p className="text-xs text-green-600">{formatFileSize(file.size)}</p>
              </div>
            </div>
            {!disabled && (
              <Button size="sm" variant="ghost" onClick={onClear}
                className="shrink-0 text-red-500 hover:text-red-700 hover:bg-red-50">
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      ) : (
        <div
          className={`relative border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
            dragActive ? 'border-primary bg-primary/5'
            : error ? 'border-red-400 bg-red-50'
            : 'border-border hover:border-primary/50'
          }`}
          onDragEnter={handleDrag} onDragLeave={handleDrag}
          onDragOver={handleDrag} onDrop={handleDrop}
          onClick={() => !disabled && inputRef.current?.click()}
        >
          <input ref={inputRef} type="file" accept={accept} className="hidden"
            disabled={disabled}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }} />
          <div className="flex flex-col items-center gap-2">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${error ? 'bg-red-100' : 'bg-primary/10'}`}>
              {icon}
            </div>
            <p className="text-sm text-muted-foreground">{hint}</p>
          </div>
        </div>
      )}
      {error && (
        <p className="text-xs text-red-600 flex items-center gap-1">
          <AlertTriangle className="h-3 w-3" /> {error}
        </p>
      )}
    </div>
  );
};

// ── Main Upload Page ───────────────────────────────────────────────────────

const Upload = () => {
  const { toast } = useToast();
  const previewRef = useRef<HTMLDivElement>(null);

  const [docFile, setDocFile] = useState<File | null>(null);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);

  const [docError, setDocError] = useState('');
  const [photoError, setPhotoError] = useState('');

  const [status, setStatus] = useState<UploadStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [submitError, setSubmitError] = useState('');

  const handleDocFile = (file: File) => {
    const allowed = ['application/pdf', 'image/png', 'image/jpeg'];
    if (!allowed.includes(file.type)) {
      setDocError('Only PDF, PNG, or JPEG files are accepted for the document.');
      return;
    }
    setDocError(''); setDocFile(file);
  };

  const handlePhotoFile = (file: File) => {
    if (!file.type.startsWith('image/')) {
      setPhotoError('Only image files (JPG, PNG, etc.) are accepted for the land photo.');
      return;
    }
    setPhotoError(''); setPhotoFile(file);
    const reader = new FileReader();
    reader.onload = (e) => setPhotoPreview(e.target?.result as string);
    reader.readAsDataURL(file);
  };

  const clearDoc = () => { setDocFile(null); setDocError(''); };
  const clearPhoto = () => { setPhotoFile(null); setPhotoPreview(null); setPhotoError(''); };

  const handleSubmit = useCallback(async () => {
    let valid = true;
    if (!docFile) { setDocError('Please attach the FRA document (PDF or image).'); valid = false; }
    if (!photoFile) { setPhotoError('Please attach a photo of your land.'); valid = false; }
    if (!valid) return;

    setStatus('uploading'); setProgress(20);
    setSubmitError(''); setResult(null);

    try {
      const formData = new FormData();
      formData.append('file', docFile!);
      formData.append('land_photo', photoFile!);

      setProgress(40); setStatus('processing');

      const res = await fetch(`${BACKEND_URL}/upload/with-photo`, {
        method: 'POST',
        body: formData,
      });

      setProgress(80);
      const raw = await res.json();

      if (!res.ok) {
        throw new Error(raw?.detail || 'Upload failed. Please check your files and try again.');
      }

      const extracted = raw?.data ?? raw;
      const normalized: ExtractedData = {
        ...normalizeKeys(extracted),
        claim_id: raw.claim_id,
        eligible_scheme: raw.eligible_scheme,
        validation_status: raw.validation_status,
        processed_timestamp: raw.processed_timestamp,
        ml_prediction: raw.ml_prediction,
        ml_confidence: raw.ml_confidence,
      };

      setResult({
        extractedData: normalized,
        docFileName: docFile!.name,
        photoFileName: photoFile!.name,
        photoPreview: photoPreview || '',
      });

      setStatus('completed'); setProgress(100);
      toast({ title: 'Upload successful', description: 'Your FRA claim has been processed and stored.' });
      setTimeout(() => previewRef.current?.scrollIntoView({ behavior: 'smooth' }), 200);

    } catch (err: unknown) {
      setStatus('error'); setProgress(100);
      const msg = err instanceof Error ? err.message : 'Could not process submission.';
      setSubmitError(msg);
      toast({ title: 'Submission failed', description: msg, variant: 'destructive' });
    }
  }, [docFile, photoFile, photoPreview, toast]);

  const handleReset = () => {
    setDocFile(null); setPhotoFile(null); setPhotoPreview(null);
    setDocError(''); setPhotoError(''); setSubmitError('');
    setStatus('idle'); setProgress(0); setResult(null);
  };

  const isSubmitting = status === 'uploading' || status === 'processing';

  return (
    <div className="fra-container py-8">
      <div className="max-w-4xl mx-auto">

        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Document Upload & Land Classification</h1>
          <p className="text-muted-foreground">
            Submit your FRA claim document along with a photo of your land. The AI will classify
            the land type from the photo and cross-verify it against your document details.
          </p>
        </div>

        {/* ── Form Card ── */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UploadIcon className="h-5 w-5" />
              Submit FRA Claim
            </CardTitle>
            <CardDescription>
              Both fields are required. Upload your claim document AND a photo of the land.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">

            <div className="grid md:grid-cols-2 gap-6">
              <DropZone
                label="1. FRA Claim Document *"
                accept=".pdf,.jpg,.jpeg,.png"
                hint="Drop your PDF or scanned form here, or click to browse"
                icon={<FileText className="h-5 w-5 text-primary" />}
                file={docFile} error={docError}
                disabled={isSubmitting || status === 'completed'}
                onFile={handleDocFile} onClear={clearDoc}
              />
              <DropZone
                label="2. Photo of Your Land *"
                accept="image/*"
                hint="Drop a clear photo of your land, or click to browse"
                icon={<ImageIcon className="h-5 w-5 text-primary" />}
                file={photoFile} preview={photoPreview} error={photoError}
                disabled={isSubmitting || status === 'completed'}
                onFile={handlePhotoFile} onClear={clearPhoto}
              />
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
              <p className="font-semibold mb-1">How it works</p>
              <ul className="list-disc list-inside space-y-1 text-blue-700">
                <li>The document is scanned with OCR to extract claim details (name, state, district, village, claim ID…).</li>
                <li>The land photo is analysed by the AI model to classify land use (Forest, Crop, Pasture…).</li>
                <li>The AI classification is cross-verified against the land use declared in your document.</li>
                <li>Only complete, valid, and non-duplicate records are stored in the database.</li>
              </ul>
            </div>

            {isSubmitting && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {status === 'uploading' ? 'Uploading files…' : 'Processing document and classifying land photo…'}
                </div>
                <Progress value={progress} className="h-2" />
              </div>
            )}

            {submitError && status === 'error' && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{submitError}</AlertDescription>
              </Alert>
            )}

            <div className="flex gap-3">
              {status !== 'completed' && (
                <Button onClick={handleSubmit} disabled={isSubmitting} className="flex-1">
                  {isSubmitting
                    ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Processing…</>
                    : <><Scan className="mr-2 h-4 w-4" /> Submit Claim</>
                  }
                </Button>
              )}
              {(status === 'completed' || status === 'error') && (
                <Button variant="outline" onClick={handleReset} className="flex-1">
                  Submit Another Claim
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* ── Results ── */}
        {result && (
          <div ref={previewRef} className="space-y-6">

            {/* Land Classification Result */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ImageIcon className="h-5 w-5" />
                  Land Classification Result
                </CardTitle>
                <CardDescription>AI analysis of your land photo</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-2 gap-6">
                  {result.photoPreview && (
                    <div className="border rounded-lg overflow-hidden">
                      <img src={result.photoPreview} alt="Uploaded land" className="w-full h-52 object-cover" />
                      <p className="text-xs text-muted-foreground p-2 text-center">{result.photoFileName}</p>
                    </div>
                  )}
                  <div className="space-y-4">
                    <div className="text-center p-4 bg-gray-50 rounded-lg">
                      <p className="text-sm text-muted-foreground mb-1">Predicted Land Use</p>
                      <p className="text-2xl font-bold text-primary">
                        {result.extractedData.ml_prediction || 'N/A'}
                      </p>
                      {result.extractedData.ml_confidence != null && result.extractedData.ml_confidence > 0 && (
                        <p className="text-sm text-muted-foreground mt-1">
                          Confidence: {(result.extractedData.ml_confidence * 100).toFixed(1)}%
                        </p>
                      )}
                    </div>
                    {result.extractedData.ml_prediction && result.extractedData.ml_prediction !== 'Not Applicable' && (
                      <div className="bg-gray-50 p-3 rounded-lg text-sm text-gray-700">
                        {getClassDescription(result.extractedData.ml_prediction)}
                      </div>
                    )}
                    <div className={`p-3 rounded-lg text-sm ${
                      result.extractedData.validation_status === 'Matched'
                        ? 'bg-green-50 text-green-800 border border-green-200'
                        : result.extractedData.validation_status === 'Mismatch'
                        ? 'bg-red-50 text-red-800 border border-red-200'
                        : 'bg-yellow-50 text-yellow-800 border border-yellow-200'
                    }`}>
                      <p className="font-semibold">Validation: {result.extractedData.validation_status || 'Pending'}</p>
                      <p className="mt-1 text-xs">
                        {result.extractedData.validation_status === 'Matched'
                          ? 'The AI classification matches the land use declared in your document.'
                          : result.extractedData.validation_status === 'Mismatch'
                          ? 'A discrepancy was detected. Your claim is flagged for manual review in the Atlas.'
                          : 'Land use could not be auto-verified. Your claim is queued for manual officer review.'}
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Extracted Document Data */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileCheck className="h-5 w-5" />
                  Extracted Document Data
                </CardTitle>
                <CardDescription>OCR and NER extracted information from {result.docFileName}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-xl border bg-white shadow-sm p-6">
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between border-b pb-4 mb-6">
                    <div>
                      <h3 className="text-xl font-semibold">{result.extractedData.patta_holder_name}</h3>
                      <p className="text-sm text-muted-foreground">Claim ID: {result.extractedData.claim_id}</p>
                    </div>
                    <div className="flex flex-wrap gap-3 mt-3 md:mt-0">
                      <Badge className="bg-blue-100 text-blue-700 font-medium px-3 py-1">
                        🏛 {result.extractedData.eligible_scheme || 'No Eligible Scheme'}
                      </Badge>
                      <Badge className={
                        result.extractedData.validation_status === 'Matched'
                          ? 'bg-green-100 text-green-700 font-medium px-3 py-1'
                          : result.extractedData.validation_status === 'Mismatch'
                          ? 'bg-red-100 text-red-700 font-medium px-3 py-1'
                          : 'bg-yellow-100 text-yellow-700 font-medium px-3 py-1'
                      }>
                        🔎 {result.extractedData.validation_status || 'Not Validated'}
                      </Badge>
                    </div>
                  </div>

                  <Button className="mb-6"
                    onClick={() => window.open(`${BACKEND_URL}/upload/certificate/${result.extractedData.claim_id}`, '_blank')}>
                    📄 Download Claim Certificate
                  </Button>

                  <div className="grid md:grid-cols-2 gap-8 text-sm">
                    <div className="space-y-6">
                      <div>
                        <h4 className="text-sm font-semibold text-gray-600 mb-2">Claim Details</h4>
                        <p><strong>Claim Type:</strong> {result.extractedData.claim_type}</p>
                        <p><strong>Application Date:</strong> {result.extractedData.date_of_application}</p>
                        <p><strong>Processed At:</strong> {result.extractedData.processed_timestamp || '—'}</p>
                        <p><strong>Extraction Confidence:</strong> {((result.extractedData.confidence ?? 0.85) * 100).toFixed(0)}%</p>
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-gray-600 mb-2">Personal Information</h4>
                        <p><strong>Age:</strong> {result.extractedData.age}</p>
                        <p><strong>Gender:</strong> {result.extractedData.gender}</p>
                        <p><strong>Father/Husband:</strong> {result.extractedData.father_or_husband_name}</p>
                      </div>
                    </div>
                    <div className="space-y-6">
                      <div>
                        <h4 className="text-sm font-semibold text-gray-600 mb-2">Location Details</h4>
                        <p><strong>Village:</strong> {result.extractedData.village_name}</p>
                        <p><strong>District:</strong> {result.extractedData.district}</p>
                        <p><strong>State:</strong> {result.extractedData.state}</p>
                        <p><strong>Coordinates:</strong> {result.extractedData.coordinates}</p>
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-gray-600 mb-2">Land Information</h4>
                        <p><strong>Total Area:</strong> {result.extractedData.total_area_claimed}</p>
                        <p><strong>Claimed Land Use:</strong> {result.extractedData.land_use}</p>
                        <p><strong>AI Classified As:</strong> {result.extractedData.ml_prediction || '—'}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

          </div>
        )}
      </div>
    </div>
  );
};

export default Upload;
