import { Skeleton } from "@/components/ui/skeleton";

export default function DocumentLoading() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-10 w-64" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Skeleton className="h-[600px] w-full rounded-xl" />
        <Skeleton className="h-[600px] w-full rounded-xl" />
      </div>
    </div>
  );
}
