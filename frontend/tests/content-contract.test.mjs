import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const frontend = new URL("../", import.meta.url);

test("travel and community DTOs remain aliases of generated OpenAPI components", () => {
  const aliases = readFileSync(new URL("lib/api/content.ts", frontend), "utf8");
  for (const component of [
    "Course", "CourseCreateRequest", "CourseCreateResult", "CourseReaction", "CourseViewResult",
    "CommunityPostWrite", "CommunityPost", "CommunityComment", "CommunityVoteState", "CommunityReportResult",
    "PredictionChoiceWrite", "PredictionGame",
  ]) assert.match(aliases, new RegExp(`Schemas\\["${component}"\\]`), component);

  for (const file of ["lib/course-api.ts", "lib/community-api.ts", "lib/predictions-api.ts", "lib/team-community.ts"]) {
    const source = readFileSync(new URL(file, frontend), "utf8");
    assert.match(source, /\.\/api\/content|\.\/api\/content/);
    assert.doesNotMatch(source, /type (ApiCourse|CommunityComment|PredictionGame|TeamCommunityPost) = \{/);
  }
});

test("fictional community examples explicitly have no images", () => {
  assert.match(readFileSync(new URL("lib/free-community-examples.ts", frontend), "utf8"), /isSample: true, images: \[\]/);
});
