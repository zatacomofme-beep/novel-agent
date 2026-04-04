import { redirect } from "next/navigation";


export default function LegacyWorldBuildingPage({
  params,
}: {
  params: { projectId: string };
}) {
  redirect(`/dashboard/projects/${params.projectId}/story-room?stage=knowledge`);
}
