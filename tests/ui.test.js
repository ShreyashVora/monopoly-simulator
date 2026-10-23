/*
 * Optional headless UI smoke test (jsdom).
 *
 *   npm install
 *   npm run test:ui
 *
 * Verifies: board render, tokens/player cards, roll -> buy modal,
 * buy -> owner marker + manage panel + cash update. Requires Python on PATH.
 */

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { JSDOM } = require("jsdom");

const root = path.resolve(__dirname, "..");
const fixture = JSON.parse(
  execFileSync("python", [path.join("tests", "ui_fixture.py")], {
    cwd: root,
    encoding: "utf8",
  })
);
const html = fs.readFileSync(path.join(root, "ui", "board.html"), "utf8");

const errors = [];
const sequence = [fixture.roll, fixture.buy];
let actionIdx = 0;

const dom = new JSDOM(html, {
  runScripts: "dangerously",
  url: "http://127.0.0.1:8000/",
  beforeParse(window) {
    window.fetch = (url) => {
      const u = String(url);
      if (u.includes("/api/state")) {
        return Promise.resolve({ json: () => Promise.resolve(fixture.initial) });
      }
      if (u.includes("/api/action")) {
        const res = sequence[Math.min(actionIdx, sequence.length - 1)];
        actionIdx += 1;
        return Promise.resolve({ json: () => Promise.resolve(res) });
      }
      return Promise.reject(new Error("unexpected url " + u));
    };
    window.confirm = () => true;
    window.addEventListener("error", (e) => errors.push(e.message));
  },
});

function check(results, name, condition) {
  results.push([name, Boolean(condition)]);
}

function finish(results) {
  let failed = 0;
  for (const [name, pass] of results) {
    console.log((pass ? "ok   " : "FAIL ") + name);
    if (!pass) failed += 1;
  }
  if (errors.length) console.log("JS errors:", errors);
  console.log(failed ? `${failed} FAILURES` : "ALL UI CHECKS PASSED");
  process.exit(failed ? 1 : 0);
}

setTimeout(() => {
  const d = dom.window.document;
  const results = [];
  check(results, "40 board tiles", d.querySelectorAll(".cell[data-idx]").length === 40);
  check(results, "4 tokens", d.querySelectorAll(".token").length === 4);
  check(results, "4 player cards", d.querySelectorAll(".pcard").length === 4);
  check(results, "no owner dots initially", d.querySelectorAll(".owner-dot").length === 0);
  check(results, "roll enabled", !d.getElementById("roll").disabled);
  check(results, "manage shows no properties",
        /No properties/.test(d.getElementById("manageList").textContent));
  check(results, "end turn disabled pre-roll", d.getElementById("endTurn").disabled);

  d.getElementById("roll").click();
  setTimeout(() => {
    check(results, "buy modal visible",
          !d.getElementById("modal").classList.contains("hidden"));
    check(results, "modal prompts purchase",
          /unowned/.test(d.getElementById("modalPrompt").textContent));
    check(results, "two options", d.querySelectorAll("#modalOpts .optbtn").length === 2);
    check(results, "dice rendered", d.getElementById("dice").textContent.length === 2);

    d.querySelectorAll("#modalOpts .optbtn")[0].click();
    setTimeout(() => {
      check(results, "modal hidden after buy",
            d.getElementById("modal").classList.contains("hidden"));
      check(results, "owner dot on Baltic",
            Boolean(d.querySelector('.cell[data-idx="3"] .owner-dot')));
      check(results, "manage lists Baltic",
            /Baltic/.test(d.getElementById("manageList").textContent));
      check(results, "cash updated", /1440/.test(d.getElementById("players").textContent));
      check(results, "end turn enabled", !d.getElementById("endTurn").disabled);
      check(results, "no JS errors", errors.length === 0);
      finish(results);
    }, 300);
  }, 1500);
}, 400);
