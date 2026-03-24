import { redirect } from "next/navigation";


export default function LegacyBootstrapPage({
  params,
}: {
  params: { projectId: string };
}) {
  redirect(`/dashboard/projects/${params.projectId}/story-room`);
}
