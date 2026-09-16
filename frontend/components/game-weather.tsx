"use client";

import { useEffect, useState } from "react";
import type { KboGame } from "@/lib/kbo/types";
import { fetchStadiumWeather, weatherStadiumCode, type StadiumWeather } from "@/lib/weather-api";

export function GameWeather({ game }: { game: KboGame }) {
  const stadium = weatherStadiumCode(game.stadium);
  const query = `${stadium ?? ""}:${game.date}:${game.time}`;
  const [result, setResult] = useState<{ query: string; weather: StadiumWeather | null } | null>(null);
  useEffect(() => {
    if (!stadium) return;
    const controller = new AbortController();
    fetchStadiumWeather(stadium, game.date, game.time, fetch, controller.signal)
      .then(weather => { if (!controller.signal.aborted) setResult({ query, weather }); });
    return () => controller.abort();
  }, [game.date, game.time, query, stadium]);
  const weather = result?.query === query ? result.weather : null;
  const resolved = !stadium || result?.query === query;
  return <span className="game-weather" title={weather ? `기상청 최신 단기예보 · ${weather.issuedAt} 발표 · ${weather.forecastAt} 경기 시각 예보${stadium === "GOCHEOK" ? " (구장 외부 날씨)" : ""}` : "해당 경기 시간의 단기예보를 확인하지 못했어요."}><span>{weather?.label ?? (resolved ? "날씨 정보 없음" : "날씨 확인 중")}</span><span>{weather ? `${weather.temperature}°C` : "—"}</span></span>;
}
