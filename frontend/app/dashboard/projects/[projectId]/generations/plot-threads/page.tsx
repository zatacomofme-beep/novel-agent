import { redirect } from "next/navigation";


export default function LegacyGenerationPlotThreadsPage({
  params,
}: {
  params: { projectId: string };
}) {
  redirect(`/dashboard/projects/${params.projectId}/story-room`);
}
