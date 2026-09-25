import test from "node:test";
import assert from "node:assert/strict";

import {
  markPlantIntroSeen,
  PLANT_INTRO_SEEN_KEY,
  readPlantIntroSeen,
} from "./plantIntro.mjs";

function fakeStore(initial = {}) {
  const data = { ...initial };
  return {
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      data[key] = String(value);
    },
    _data: data,
  };
}

test("fresh store has not seen the intro", () => {
  assert.equal(readPlantIntroSeen(fakeStore()), false);
});

test("marking seen persists and replays never happen", () => {
  const store = fakeStore();
  markPlantIntroSeen(store);
  assert.equal(store._data[PLANT_INTRO_SEEN_KEY], "true");
  assert.equal(readPlantIntroSeen(store), true);
  // Marking again stays seen (idempotent).
  markPlantIntroSeen(store);
  assert.equal(readPlantIntroSeen(store), true);
});

test("unrelated stored values do not count as seen", () => {
  assert.equal(readPlantIntroSeen(fakeStore({ other: "true" })), false);
  assert.equal(readPlantIntroSeen(fakeStore({ [PLANT_INTRO_SEEN_KEY]: "yes" })), false);
});

test("broken storage never throws", () => {
  const broken = {
    getItem: () => {
      throw new Error("denied");
    },
    setItem: () => {
      throw new Error("denied");
    },
  };
  assert.equal(readPlantIntroSeen(broken), false);
  markPlantIntroSeen(broken);
});

test("missing storage never throws", () => {
  assert.equal(readPlantIntroSeen(undefined), false);
  markPlantIntroSeen(undefined);
});
