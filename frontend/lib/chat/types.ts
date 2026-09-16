export type ChatCoursePhase = "BEFORE" | "GAME" | "AFTER";
export type ChatCoursePlace = {
  phase: ChatCoursePhase; name: string; lat: number; lng: number;
  // STAY·WALK·INDOOR 는 백엔드가 카카오 실시간 조회로 더한 종류 (RAG 에 없는 숙박·산책·실내놀거리)
  category: "FOOD" | "CAFE" | "SPOT" | "STADIUM" | "STAY" | "WALK" | "INDOOR"; placeId?: string; address?: string;
  reason?: string; time?: string; stayMin?: number;
};
/** 챗봇이 짠 코스. 백엔드 done 이벤트의 places·travel·coursePayload 에서 온다 (lib/chat/course.ts). */
export type ChatCourse = {
  places: ChatCoursePlace[];
  stadiumCode?: string;
  travelMode?: "walk" | "car" | "transit";
  travelLabel?: string;
  summary?: string;
  notes: string[];
  title?: string;
  content?: string;
};
// course 는 화면 표시용이다. parseChatRequest 가 서버로 보낼 때 role·content 만 남긴다.
export type ChatMessage = { role: "user" | "assistant"; content: string; course?: ChatCourse };
export type ChatContext = { stadium?: string; intent?: "route" | "baseball" | "stadium" };
export type ChatRequest = { messages: ChatMessage[]; sessionId?: number; context?: ChatContext };
export type ChatStatus = { provider: "demo" | "openai" | "backend" | "guest"; model: string; ready: boolean };
export type ChatReply = ChatStatus & ChatCourseMetadataDto & {
  reply: string;
  sessionId?: number;
  completionStatus?: "completed" | "stopped";
  turnId?: string;
  userMessageId?: number;
  assistantMessageId?: number | null;
  course?: ChatCourse;
};

export const MAX_MESSAGE_LENGTH = 2000;
export const MAX_HISTORY_MESSAGES = 12;
export const MAX_REPLY_LENGTH = 8000;
export const MAX_REQUEST_BYTES = 64000;
import type { ChatCourseMetadataDto } from "./wire";
