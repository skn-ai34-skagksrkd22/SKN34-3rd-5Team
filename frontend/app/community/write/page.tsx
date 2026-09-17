import { CommunityPostEditor } from "@/components/community-post-editor";

export const metadata = { title: "게시글 작성" };

export default async function Page({ searchParams }: { searchParams: Promise<{ board?: string | string[]; team?: string | string[]; edit?: string | string[] }> }) {
  const query = await searchParams;
  const board = query.board === "teams" ? "teams" : "free";
  return <CommunityPostEditor board={board} teamCode={typeof query.team === "string" ? query.team : ""} editId={typeof query.edit === "string" ? query.edit : ""} />;
}
