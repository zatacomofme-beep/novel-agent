import { redirect } from "next/navigation";


export default function LegacyCollaboratorsPage({
  params,
}: {
  params: { projectId: string };
}) {
  redirect(`/dashboard/projects/${params.projectId}/story-room`);
}
