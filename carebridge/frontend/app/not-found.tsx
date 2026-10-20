import Link from "next/link";
import { AlertCircle, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-xl shadow-xs border border-slate-200 p-6 space-y-4 text-center">
        <div className="h-12 w-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto">
          <AlertCircle className="h-6 w-6" />
        </div>
        <div className="space-y-1">
          <h1 className="text-xl font-bold text-slate-900">404 - Resource Not Found</h1>
          <p className="text-xs text-slate-500">
            RFC 7807: The requested endpoint or portal route has been retired or does not exist.
          </p>
        </div>
        <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-left text-xs font-mono text-slate-700 space-y-1">
          <div><span className="text-slate-400">type:</span> &quot;https://carebridge.health/errors/not-found&quot;</div>
          <div><span className="text-slate-400">title:</span> &quot;Route Retired / Not Found&quot;</div>
          <div><span className="text-slate-400">status:</span> 404</div>
        </div>
        <div className="pt-2">
          <Link href="/">
            <Button size="sm" className="bg-blue-700 hover:bg-blue-800 text-white flex items-center gap-2 mx-auto">
              <ArrowLeft className="h-4 w-4" />
              <span>Return to CareBridge</span>
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
