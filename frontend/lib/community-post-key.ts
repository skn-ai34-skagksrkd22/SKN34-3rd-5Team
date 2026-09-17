let submissionCount = 0;

export function createCommunitySubmissionKey() {
  // Used only for duplicate-request detection; account authentication stays JWT-based.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${++submissionCount}`;
}
