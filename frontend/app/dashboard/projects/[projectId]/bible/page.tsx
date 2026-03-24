import { redirect } from "next/navigation";


export default function LegacyBiblePage({
  params,
}: {
  params: { projectId: string };
}) {
  redirect(`/dashboard/projects/${params.projectId}/story-room`);
}
