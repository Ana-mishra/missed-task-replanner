import test from "node:test";
import assert from "node:assert/strict";

import { oauthLoginUrl } from "./oauthUrls.mjs";

const RAILWAY_API = "https://missed-task-replanner-production.up.railway.app";

test("local dev points at the API backend with a localhost next", () => {
  const url = oauthLoginUrl(RAILWAY_API, "google", "http://localhost:5173");
  assert.equal(
    url,
    `${RAILWAY_API}/auth/google?next=${encodeURIComponent("http://localhost:5173")}`,
  );
});

test("production points at the API backend with a Vercel next", () => {
  const url = oauthLoginUrl(
    RAILWAY_API,
    "google",
    "https://planora-productivity.vercel.app",
  );
  assert.ok(url.startsWith(`${RAILWAY_API}/auth/google?next=`));
  assert.ok(url.includes(encodeURIComponent("https://planora-productivity.vercel.app")));
});

test("works for the github provider and trims base slashes", () => {
  const url = oauthLoginUrl(`${RAILWAY_API}/`, "github", "http://localhost:5173");
  assert.ok(url.startsWith(`${RAILWAY_API}/auth/github?next=`));
});

test("omits next when no frontend origin is known", () => {
  assert.equal(oauthLoginUrl(RAILWAY_API, "google", undefined), `${RAILWAY_API}/auth/google`);
});
