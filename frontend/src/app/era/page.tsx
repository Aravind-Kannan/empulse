import { EraCommandCenter } from "@/components/era/EraCommandCenter";
import { EraDashboard } from "@/components/era/EraDashboard";

const useCommandCenter =
  process.env.NEXT_PUBLIC_ERA_COMMAND_CENTER !== "false";

export default function EraPage() {
  return (
    <div className="p-4 md:p-8">
      {useCommandCenter ? <EraCommandCenter /> : <EraDashboard />}
    </div>
  );
}
