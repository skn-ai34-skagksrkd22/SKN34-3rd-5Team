// Shared vocabulary for community fixtures and a future post editor/API adapter.
export const communityPostCategories = [
  "잡담", "질문", "응원", "경기토론", "전력토론", "소식·정보",
  "이적·신인", "직관후기", "좌석·예매", "직관준비", "굿즈", "사진·영상",
] as const;
export type CommunityPostCategory = typeof communityPostCategories[number];

// Keep the writer choices aligned with backend/community/models.py.
const freePostCategories = ["질문", "잡담"] as const;
const teamPostCategories = ["질문", "잡담", "경기토론", "굿즈", "사진·영상", "응원", "전력토론", "좌석·예매", "직관준비", "직관후기"] as const;

export function writablePostCategories(board: "free" | "teams"): readonly CommunityPostCategory[] {
  return board === "free" ? freePostCategories : teamPostCategories;
}

export const communityCategoryGroups = {
  일반: { color: "#52647b", categories: ["잡담", "질문"] },
  응원: { color: "#d52a32", categories: ["응원"] },
  야구: { color: "#1455eb", categories: ["경기토론", "전력토론", "소식·정보", "이적·신인"] },
  직관: { color: "#00853e", categories: ["직관후기", "좌석·예매", "직관준비"] },
  취미: { color: "#d52b87", categories: ["굿즈", "사진·영상"] },
} as const;

export function getCommunityCategoryGroup(category: CommunityPostCategory) {
  return Object.entries(communityCategoryGroups).find(([, group]) =>
    (group.categories as readonly string[]).includes(category))!;
}
