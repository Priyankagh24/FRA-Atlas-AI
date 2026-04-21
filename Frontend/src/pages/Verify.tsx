import { useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ShieldCheck, ShieldAlert, ShieldX } from "lucide-react";

const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

const Verify = () => {
  const { claim_id } = useParams();
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    fetch(`${BACKEND_URL}/upload/api/verify/${claim_id}`)
      .then(res => res.json())
      .then(data => setResult(data))
      .catch(() => setResult({ status: "NOT_FOUND" }));
  }, [claim_id]);

  const renderStatus = () => {
    if (!result) return null;

    switch (result.status) {
      case "AUTHENTIC":
        return (
          <Badge className="bg-green-100 text-green-700 px-4 py-2 text-sm">
            <ShieldCheck className="w-4 h-4 mr-2" />
            Certificate Authentic
          </Badge>
        );
      case "TAMPERED":
        return (
          <Badge className="bg-red-100 text-red-700 px-4 py-2 text-sm">
            <ShieldAlert className="w-4 h-4 mr-2" />
            Certificate Tampered
          </Badge>
        );
      case "REVOKED":
        return (
          <Badge className="bg-yellow-100 text-yellow-700 px-4 py-2 text-sm">
            <ShieldX className="w-4 h-4 mr-2" />
            Certificate Revoked
          </Badge>
        );
      default:
        return (
          <Badge className="bg-gray-100 text-gray-700 px-4 py-2 text-sm">
            Record Not Found
          </Badge>
        );
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 p-6">
      <Card className="w-full max-w-2xl shadow-lg border">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">
            FRA Digital Certificate Verification
          </CardTitle>
        </CardHeader>

        <CardContent className="space-y-6 text-center">
          {renderStatus()}

          {result?.status === "AUTHENTIC" && (
            <div className="mt-6 text-left space-y-2">
              <p><strong>Applicant:</strong> {result.data.name}</p>
              <p><strong>Claim ID:</strong> {result.data.claim_id}</p>
              <p><strong>State:</strong> {result.data.state}</p>
              <p><strong>District:</strong> {result.data.district}</p>
              <p><strong>Eligible Scheme:</strong> {result.data.scheme}</p>
              <p><strong>Validation:</strong> {result.data.validation}</p>
            </div>
          )}

          {result?.status === "TAMPERED" && (
            <p className="text-red-600 font-medium">
              ⚠ This certificate data does not match original records.
            </p>
          )}

          {result?.status === "REVOKED" && (
            <p className="text-yellow-600 font-medium">
              ⚠ This certificate has been officially revoked.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Verify;