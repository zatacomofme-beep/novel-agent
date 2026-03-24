import { redirect } from "next/navigation";


export default function ProjectSettingsPage({
  params,
}: {
  params: { projectId: string };
}) {
  redirect(`/dashboard/projects/${params.projectId}/story-room`);
}
