import { redirect } from "next/navigation";


export default function LegacyGenerationLocationsPage({
  params,
}: {
  params: { projectId: string };
}) {
  redirect(`/dashboard/projects/${params.projectId}/story-room`);
}
