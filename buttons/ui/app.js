// The buttons page: draws one key per configured button, shows each one's
// state, and sends presses to the server next to it.

const POLL_MS = 3000;

const ICONS = {
  light: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.6 10.8c.6.5 1 1.2 1 2V16h5.2v-.2c0-.8.4-1.500 1-2A6 6 0 0 0 12 3z"/>',
  plug: '<path d="M9 3v5M15 3v5"/><path d="M6.500 8h11v3a5.500 5.500 0 0 1-11 0z"/><path d="M12 16.500V21"/>',
  fan: '<circle cx="12" cy="12" r="1.600"/><path d="M12 10.400C11 6 12.500 3 15.500 3.600c2 .4 1.800 4.600-3.500 6.800zM13.400 12.800c3.300 3.100 3.200 6.400.3 7.400-1.900.7-3.900-3-1.700-7.400zM10.600 12.800c-4.300 1.300-7.200-.400-6.200-3.300.7-1.900 4.900-1.700 6.200 3.300z"/>',
  lock: '<rect x="5.500" y="10.500" width="13" height="10" rx="2.500"/><path d="M8.500 10.500V7.500a3.500 3.500 0 0 1 7 0v3"/>',
  tv: '<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M8.500 21h7"/>',
  scene: '<path d="M12 3l1.900 5.100L19 10l-5.100 1.900L12 17l-1.900-5.100L5 10l5.100-1.900z"/><path d="M18.500 16.500l.7 1.800 1.800.7-1.800.7-.7 1.800-.7-1.800-1.800-.7 1.800-.7z"/>',
  heat: '<path d="M12 21a5.500 5.500 0 0 1-5.500-5.500c0-2.500 1.500-3.800 2.500-5.500.5 1.500 1.500 2 1.500 2C10.500 8.500 12 5.500 14 3c.3 3 3.500 5.500 3.500 9.500A5.500 5.500 0 0 1 12 21z"/>',
  door: '<path d="M6.500 21V4.500A1.500 1.500 0 0 1 8 3h8a1.500 1.500 0 0 1 1.500 1.500V21M4 21h16"/><path d="M14 12.500v.01"/>',
  power: '<path d="M12 3.500v8"/><path d="M7 6.800a7 7 0 1 0 10 0"/>',
  dot: '<circle cx="12" cy="12" r="4.500"/>',
};
const TONES = { light: "butter", plug: "mint", fan: "sky", lock: "lilac", tv: "pink",
                scene: "pink", heat: "peach", door: "mint", power: "peach", dot: "lilac" };
const COLORS = ["peach", "mint", "butter", "pink", "sky", "lilac"];

// Home Assistant states that mean the thing is active.
const ON = new Set(["on", "open", "unlocked", "playing", "home", "heat", "cool", "cleaning"]);
const WORDS = { on: "On", off: "Off", open: "Open", closed: "Closed", locked: "Locked",
                unlocked: "Unlocked", unavailable: "Unavailable", unknown: "Unknown" };

const keys = document.getElementById("keys");
const notice = document.getElementById("notice");
const els = new Map();

function stateWords(b) {
  if (b.state === null || b.state === undefined) return b.missing ? "Not found in Home Assistant" : "";
  // A scene's or button's state is the time it last ran, which says nothing useful.
  if (/^\d{4}-\d\d-\d\dT/.test(b.state)) return "";
  return WORDS[b.state] || b.state.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

function draw(b) {
  let el = els.get(b.id);
  if (!el) {
    el = document.createElement("button");
    el.className = "key";
    el.type = "button";
    const icon = ICONS[b.icon] ? b.icon : "dot";
    const tone = COLORS.includes(b.color) ? b.color : TONES[icon];
    el.style.setProperty("--tone", `var(--${tone})`);
    el.innerHTML =
      `<span class="cap"><svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[icon]}</svg>` +
      `<span class="legend"><span class="label"></span><span class="state"></span></span></span>`;
    el.querySelector(".label").textContent = b.label;
    el.addEventListener("click", () => press(b.id));
    els.set(b.id, el);
    keys.append(el);
  }
  el.classList.toggle("on", ON.has(b.state));
  el.classList.toggle("missing", Boolean(b.missing));
  el.setAttribute("aria-pressed", String(ON.has(b.state)));
  el.querySelector(".state").textContent = stateWords(b);
}

function layout(count) {
  // 640 px wide holds three keys across comfortably; few keys get bigger ones.
  const cols = count <= 2 ? 1 : count <= 6 ? 2 : 3;
  keys.style.setProperty("--cols", cols);
}

function say(text) {
  notice.hidden = !text;
  notice.textContent = text || "";
  document.body.classList.toggle("offline", Boolean(text));
}

async function refresh() {
  let data;
  try {
    const res = await fetch("/buttons", { cache: "no-store" });
    data = await res.json();
  } catch {
    say("The buttons server on this Pi is not answering. Check that xeneon-buttons is running.");
    return;
  }
  const ids = new Set(data.buttons.map((b) => b.id));
  for (const [id, el] of els) if (!ids.has(id)) { el.remove(); els.delete(id); }
  layout(data.buttons.length);
  for (const b of data.buttons) {
    // With Home Assistant unreachable every state is unknown; that is not
    // the same as an entity Home Assistant does not have.
    draw({ ...b, missing: !data.error && b.state === null && b.has_entity });
  }
  say(data.error);
}

async function press(id) {
  const el = els.get(id);
  el.classList.add("sending");
  el.classList.remove("failed");
  try {
    const res = await fetch(`/press/${encodeURIComponent(id)}`, {
      method: "POST", headers: { "X-Buttons-Page": "1" } });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    draw({ ...data.button, missing: false });
    say("");
  } catch (e) {
    el.classList.add("failed");
    say(e.message || "The press did not reach Home Assistant.");
  } finally {
    el.classList.remove("sending");
  }
}

refresh();
setInterval(refresh, POLL_MS);
