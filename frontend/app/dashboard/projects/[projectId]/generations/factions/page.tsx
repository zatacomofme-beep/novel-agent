import { redirect } from "next/navigation";


export default function LegacyGenerationFactionsPage({
  params,
}: {
  params: { projectId: string };
}) {
  redirect(`/dashboard/projects/${params.projectId}/story-room`);
}
