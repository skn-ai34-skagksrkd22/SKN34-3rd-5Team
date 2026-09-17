import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../lib/stop-history.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { createStopHistory, observeStops, undoStops, redoStops, STOP_HISTORY_LIMIT } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
const stop = (name) => ({ name, lat: 37.5, lng: 127, category: "먹거리", visitId: name });

// The writer hands back exactly the array we pass up, like `setStops(next)`.
function apply(history, step) { return observeStops(step.history, step.stops); }

test("user edits are recorded and can be undone and redone in order", () => {
  const a = [], b = [stop("a")], c = [stop("a"), stop("b")];
  let history = observeStops(observeStops(createStopHistory(a), b), c);
  assert.equal(history.past.length, 2);

  history = apply(history, undoStops(history));
  assert.equal(history.current, b);
  history = apply(history, undoStops(history));
  assert.equal(history.current, a);
  assert.equal(undoStops(history), null);

  history = apply(history, redoStops(history));
  assert.equal(history.current, b);
  history = apply(history, redoStops(history));
  assert.equal(history.current, c);
  assert.equal(redoStops(history), null);
});

test("a new edit after undo drops the redo branch", () => {
  const b = [stop("a")], c = [stop("a"), stop("b")], d = [stop("x")];
  let history = observeStops(observeStops(createStopHistory([]), b), c);
  history = apply(history, undoStops(history));
  history = observeStops(history, d);
  assert.deepEqual(history.future, []);
  assert.equal(apply(history, undoStops(history)).current, b);
});

test("identical content is not a step and history is capped", () => {
  let history = observeStops(createStopHistory([]), [stop("a")]);
  history = observeStops(history, [stop("a")]);
  assert.equal(history.past.length, 1);
  for (let i = 0; i < STOP_HISTORY_LIMIT + 10; i += 1) history = observeStops(history, [stop(String(i))]);
  assert.equal(history.past.length, STOP_HISTORY_LIMIT);
});
