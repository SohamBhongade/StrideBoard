// StrideBoard: small helpers for every page. Plain JavaScript, no libraries.
(function () {
  "use strict";

  // Safe localStorage: some browsers block it (private mode), so never crash.
  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function save(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* ignore */ } }

  // ---- Ask "are you sure?" before forms marked with data-confirm
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.getAttribute("data-confirm"))) e.preventDefault();
    });
  });

  // ---- Copy buttons (the phone token)
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = btn.getAttribute("data-copy");
      var done = function () {
        var old = btn.innerHTML;
        btn.textContent = "Copied!";
        setTimeout(function () { btn.innerHTML = old; }, 1600);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done);
      } else {
        // Fallback for plain http on a laptop during testing
        var box = document.createElement("textarea");
        box.value = text; document.body.appendChild(box); box.select();
        try { document.execCommand("copy"); done(); } catch (e) { /* ignore */ }
        box.remove();
      }
    });
  });

  // ---- Show / hide the token
  var tokenToggle = document.querySelector("[data-toggle-token]");
  if (tokenToggle) {
    var code = document.getElementById("token");
    var hidden = code.textContent;
    tokenToggle.addEventListener("click", function () {
      var showing = tokenToggle.textContent === "Hide";
      code.textContent = showing ? hidden : code.getAttribute("data-token");
      tokenToggle.textContent = showing ? "Show" : "Hide";
    });
  }

  // ---- Live steps from the Android app
  // While the app is on screen it reads Health Connect every 30 seconds and calls
  // StrideBoard.liveSteps(n). This updates today's numbers in place, without reloading.
  window.StrideBoard = window.StrideBoard || {};
  window.StrideBoard.liveSteps = function (steps) {
    var card = document.querySelector("[data-live-steps]");
    steps = parseInt(steps, 10);
    if (!card || isNaN(steps) || steps < 0) return;
    var num = card.querySelector("[data-count]");
    var now = parseInt(num.getAttribute("data-count"), 10) || 0;
    if (steps === now) return;
    var goal = parseInt(card.getAttribute("data-goal"), 10) || 1;
    var pct = Math.floor(steps * 100 / goal);
    var shown = Math.min(pct, 100);
    num.setAttribute("data-count", String(steps));
    num.textContent = steps.toLocaleString("en-US");
    card.querySelector("[data-live-chip]").textContent = pct + "% of goal";
    var ring = card.querySelector("[data-live-ring]");
    ring.setAttribute("aria-label", pct + "% of today's goal");
    ring.querySelector(".fill").style.strokeDashoffset = (238.8 * (1 - shown / 100)).toFixed(1);
    card.querySelector("[data-live-label]").innerHTML = pct >= 100
      ? '<svg class="icon" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4.5 12.5l5 5 10-11"/></svg>'
      : pct + "%";
    var on = Math.min(Math.floor(pct / 10), 10);
    card.querySelectorAll(".blocks-10 .block").forEach(function (b, i) { b.classList.toggle("on", i < on); });
    var note = card.querySelector("[data-live-note]");
    if (note) note.innerHTML = pct >= 100
      ? '<p class="small"><strong>Goal reached!</strong> Anything extra still counts towards your weekly tier.</p>'
      : '<p class="small"><strong>' + (goal - steps).toLocaleString("en-US") +
        ' to go.</strong> Moving more is linked to better mood and sleep, and a walk between lessons all adds up.</p>';
  };

  // ---- In-site "time to stand up" reminder
  // The server sets data-due="1" only when the phone's syncs show fewer than 50 steps
  // in the last 30+ minutes. It shows between 7:00 and 21:00, and "Done" hides it
  // for 30 minutes.
  var stand = document.getElementById("stand-nudge");
  if (stand) {
    var hour = new Date().getHours();
    var last = parseInt(load("sb_stand_last") || "0", 10);
    var dismissedRecently = Date.now() - last < 30 * 60 * 1000;
    stand.hidden = !(stand.getAttribute("data-due") === "1" && !dismissedRecently && hour >= 7 && hour < 21);
    stand.querySelector("[data-dismiss-stand]").addEventListener("click", function () {
      save("sb_stand_last", String(Date.now()));
      stand.hidden = true;
    });
  }

  // ---- One-time hint on iPhone Safari: Share -> Add to Home Screen
  var iosHint = document.getElementById("ios-hint");
  if (iosHint) {
    var ua = navigator.userAgent;
    var isIOS = /iPhone|iPad|iPod/.test(ua);
    var isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
    var installed = window.navigator.standalone === true;
    if (isIOS && isSafari && !installed && !load("sb_ios_hint_done")) iosHint.hidden = false;
    iosHint.querySelector("[data-dismiss-ios]").addEventListener("click", function () {
      save("sb_ios_hint_done", "1");
      iosHint.hidden = true;
    });
  }

  // ---- iPhone: "Sync from Apple Health" button on the dashboard.
  // A website cannot read Apple Health, so the button runs the StrideBoard Sync
  // Shortcut. When the person comes back, the page reloads to show the new steps.
  var iosSync = document.querySelector("[data-ios-sync]");
  if (iosSync) {
    var agent = navigator.userAgent;
    var isIPad = navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1; // iPads say "Mac"
    if ((/iPhone|iPod|iPad/.test(agent) || isIPad) && agent.indexOf("StrideBoardAndroid") === -1) {
      iosSync.hidden = false;
      iosSync.querySelector("a").addEventListener("click", function () {
        save("sb_sync_started", String(Date.now()));
      });
      document.addEventListener("visibilitychange", function () {
        if (document.visibilityState !== "visible") return;
        var started = parseInt(load("sb_sync_started") || "0", 10);
        if (started && Date.now() - started < 5 * 60 * 1000) {
          save("sb_sync_started", "0");
          location.reload();
        }
      });
    }
  }

  // ---- Admin: update the suggested distance target when dates change
  var form = document.getElementById("challenge-form");
  if (form) {
    var perDay = parseInt(form.getAttribute("data-per-day"), 10) || 0;
    var start = form.querySelector("#start_date");
    var end = form.querySelector("#end_date");
    var target = form.querySelector("#target_steps");
    var hint = form.querySelector("#target-hint");
    var kind = form.querySelector("#kind");
    var distanceOnly = form.querySelector("[data-distance-only]");
    var update = function () {
      var days = Math.round((new Date(end.value) - new Date(start.value)) / 86400000) + 1;
      if (days > 0 && perDay) {
        var steps = perDay * days;
        target.value = steps;
        hint.textContent = "Suggested: active people × 7,000 × " + days + " days = " +
          steps.toLocaleString("en-US") + " steps (" + (steps * 0.0007).toFixed(1) + " km).";
      }
    };
    start.addEventListener("change", update);
    end.addEventListener("change", update);
    kind.addEventListener("change", function () {
      distanceOnly.hidden = kind.value !== "school_distance";
    });
  }

  // ---- Count up big numbers on the dashboard (a little game feel)
  // Only on the first visit to a page in this tab (see .no-intro in base.html).
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var replay = document.documentElement.classList.contains("no-intro");
  if (!reduce && !replay) {
    document.querySelectorAll("[data-count]").forEach(function (el) {
      var target = parseInt(el.getAttribute("data-count"), 10) || 0;
      // Keep the final width while counting, so "/ 10,000" next to it does not jump.
      el.style.minWidth = el.getBoundingClientRect().width + "px";
      el.textContent = "0";
      var startTime = null;
      var step = function (t) {
        if (!startTime) startTime = t;
        var p = Math.min((t - startTime) / 1200, 1);   // same length as the ring animation
        var eased = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(target * eased).toLocaleString("en-US");
        if (p < 1) requestAnimationFrame(step);
        else el.style.minWidth = "";
      };
      requestAnimationFrame(step);
    });
  }

  // ---- Leaderboard: the period dropdown switches straight away; the search box hides
  // non-matching rows as you type (Enter searches the whole board, not just the top 50).
  document.querySelectorAll("select[data-autosubmit]").forEach(function (sel) {
    sel.addEventListener("change", function () { sel.form.submit(); });
  });
  var boardSearch = document.querySelector("[data-board-search]");
  // Same rule as the server: any part of a name, or a class/department word that starts with it.
  var boardMatch = function (el, needle) {
    if (!needle) return true;
    if (el.getAttribute("data-name").indexOf(needle) !== -1) return true;
    return (el.getAttribute("data-dept") || "").split(" ").some(function (w) { return w.indexOf(needle) === 0; });
  };
  if (boardSearch) {
    boardSearch.addEventListener("input", function () {
      var needle = boardSearch.value.trim().toLowerCase();
      document.querySelectorAll(".rank-row[data-name]").forEach(function (row) {
        row.classList.toggle("no-match", !boardMatch(row, needle));
      });
    });
  }

  // ---- Dashboard water +/- and mood: save without reloading the page.
  // If anything goes wrong, the form is sent the normal way instead.
  function updateWater(res) {
    var count = document.querySelector("[data-water-count]");
    if (!count) return;
    var old = parseInt(count.textContent, 10) || 0;
    count.textContent = res.water;
    var glass = document.querySelector("[data-water-glass]");
    if (glass) {
      glass.style.setProperty("--fill", Math.min(res.water / (res.target || 8), 1).toFixed(3));
      glass.classList.toggle("empty", res.water === 0);
      glass.classList.toggle("full", res.water >= res.target);
      if (res.water > old) {   // a little slosh when a glass is added
        glass.classList.remove("pour"); void glass.offsetWidth; glass.classList.add("pour");
      }
    }
    var chip = document.querySelector("[data-water-chip]");
    if (chip) chip.textContent = res.water >= res.target ? "Done for today" : (res.target - res.water) + " to go";
    var minus = document.querySelector("[data-water-minus]");
    if (minus) minus.disabled = res.water === 0;
    var next = document.querySelector("[data-water-next]");
    if (next) next.textContent = res.water + 1;
    var nudge = document.querySelector("[data-water-nudge]");
    if (nudge) nudge.hidden = res.water >= res.target;
  }

  function updateMood(res) {
    document.querySelectorAll("[data-quick='mood'] .mood-btn").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.value) === String(res.mood) ? "true" : "false");
    });
    var note = document.querySelector("[data-mood-note]");
    if (note) note.textContent = "Saved. Your wrap-up compares mood with your steps.";
  }

  document.querySelectorAll("form[data-quick]").forEach(function (f) {
    var busy = false;
    f.addEventListener("submit", function (e) {
      if (!window.fetch || !window.FormData) return;   // very old browser: normal submit
      e.preventDefault();
      if (busy) return;   // ignore double taps while saving
      busy = true;
      var button = e.submitter || f.querySelector("button");
      var body = new FormData(f);
      if (button && button.name) body.append(button.name, button.value);   // e.g. mood=4
      if (button) button.setAttribute("aria-busy", "true");
      // getAttribute: the hidden input named "action" hides the form's f.action property
      fetch(f.getAttribute("action"), { method: "POST", body: body, credentials: "same-origin",
                        headers: { "X-Requested-With": "fetch" } })
        .then(function (r) { return r.json().then(function (res) { return { ok: r.ok, res: res }; }); })
        .then(function (out) {
          if (!out.ok || !out.res.ok) { window.alert(out.res.error || "Could not save. Please try again."); return; }
          if (f.getAttribute("data-quick") === "water") updateWater(out.res);
          else updateMood(out.res);
        })
        .catch(function () { f.submit(); })   // network or server trouble: fall back to a page load
        .then(function () { busy = false; if (button) button.removeAttribute("aria-busy"); });
    });
  });

  // ---- Settings: show the chosen avatar and colour straight away (saved on "Save avatar")
  var avForm = document.querySelector(".avatar-form");
  var avPreview = document.querySelector("[data-av-preview] .av");
  if (avForm && avPreview) {
    avForm.addEventListener("change", function () {
      var pick = avForm.querySelector("input[name=avatar]:checked");
      var colour = avForm.querySelector("input[name=avatar_color]:checked");
      if (pick) {
        var emoji = document.createElement("span");
        emoji.className = "av-emoji";
        emoji.textContent = pick.getAttribute("data-emoji");
        avPreview.replaceChildren(emoji);
      }
      if (colour) avPreview.className = "av av-" + colour.value;
    });
  }

  // ---- PWA: register the service worker (offline page, faster loads)
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () { /* not critical */ });
    });
  }
})();

// ---- Mini challenges: a running clock, the Done button unlocking, and live walk progress
(function () {
  var box = document.querySelector("[data-mini-live]");
  if (!box) return;
  var started = Date.now() - (parseInt(box.getAttribute("data-elapsed"), 10) || 0) * 1000;
  var wait = parseInt(box.getAttribute("data-wait"), 10) || 0;
  var unlockAt = Date.now() + wait * 1000;
  var plank = parseInt(box.getAttribute("data-plank"), 10) || 0;
  var clocks = box.querySelectorAll("[data-mini-clock]");
  var done = box.querySelector("[data-mini-done]");
  var label = box.querySelector("[data-done-label]");
  function mmss(s) {
    s = Math.max(0, Math.floor(s));
    var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = ("0" + s % 60).slice(-2);
    return h ? h + ":" + ("0" + m).slice(-2) + ":" + sec : m + ":" + sec;
  }
  function tick() {
    var secs = (Date.now() - started) / 1000;
    var shown = plank ? (secs >= plank ? "Time!" : mmss(plank - secs)) : mmss(secs);
    clocks.forEach(function (c) { c.textContent = shown; });
    if (done && done.disabled) {
      var left = Math.ceil((unlockAt - Date.now()) / 1000);
      if (left <= 0) {
        done.disabled = false; if (label) label.textContent = "Done";
        if (wait) done.classList.add("unlocked");    // a soft glow so they notice it's ready
      }
      else if (label) label.textContent = "Done in " + left + "s";
    }
  }
  tick();
  setInterval(tick, 1000);

  // Walks: the Android app calls StrideBoard.liveSteps(today's total) every 30 seconds.
  var base = box.getAttribute("data-walk-base");
  if (base === null) return;
  base = parseInt(base, 10) || 0;
  var goal = parseInt(box.getAttribute("data-walk-amount"), 10) || 1;
  var reloading = false;
  var previous = window.StrideBoard && window.StrideBoard.liveSteps;
  window.StrideBoard = window.StrideBoard || {};
  window.StrideBoard.liveSteps = function (steps) {
    if (previous) previous(steps);
    steps = parseInt(steps, 10);
    if (isNaN(steps)) return;
    var walked = Math.max(0, Math.min(goal, steps - base));
    box.querySelectorAll("[data-walk-done]").forEach(function (n) { n.textContent = walked.toLocaleString("en-US"); });
    var course = window.StrideBoardWalk;
    if (course) course.update(walked, goal);
    if (walked >= goal && !reloading) {
      reloading = true;   // walk to the flag first, then the page shows the finish line and celebration
      if (course) course.atFlag(function () { location.reload(); });
      else setTimeout(function () { location.reload(); }, 1200);
    }
  };
})();

// ---- Sign-up: sensible age default when switching Student / Teacher
// (which dropdown shows is done in CSS, so it works without JavaScript too)
(function () {
  var age = document.getElementById("age_band");
  if (!age || !document.querySelector(".signup-form")) return;
  var touched = false;
  age.addEventListener("change", function () { touched = true; });
  document.querySelectorAll("input[name=role]").forEach(function (r) {
    r.addEventListener("change", function () {
      if (!touched) age.value = r.value === "teacher" ? "adult_18_39" : "teen_13_17";
    });
  });
})();

// ---- Settings > Appearance: save as soon as a choice is tapped
document.querySelectorAll("form[data-autosubmit]").forEach(function (form) {
  form.addEventListener("change", function () { form.submit(); });
});

// ---- Admin > People: filter the list as you type (the tabs and Enter also work without this)
(function () {
  var box = document.querySelector("[data-people-search]");
  var rows = document.querySelector("[data-people-rows]");
  if (!box || !rows) return;
  var count = document.querySelector("[data-people-count]");
  var none = document.querySelector("[data-people-none]");
  var all = Array.prototype.slice.call(rows.querySelectorAll("tr"));
  box.form.addEventListener("submit", function (e) { e.preventDefault(); });
  box.addEventListener("input", function () {
    var words = box.value.toLowerCase().split(/\s+/).filter(Boolean);
    var n = 0;
    all.forEach(function (tr) {
      var text = tr.getAttribute("data-search");
      var ok = words.every(function (w) { return text.indexOf(w) !== -1; });
      tr.hidden = !ok;
      if (ok) n++;
    });
    if (count) count.textContent = n;
    if (none) none.hidden = n !== 0;
  });
})();

// ---- Buttons that ask "are you sure?" (e.g. Delete forever)
document.querySelectorAll("button[data-confirm]").forEach(function (btn) {
  btn.addEventListener("click", function (e) {
    if (!window.confirm(btn.getAttribute("data-confirm"))) e.preventDefault();
  });
});

// ---- Admin > People: tick people, then "Delete forever" appears with the count
(function () {
  var bar = document.querySelector("[data-delete-bar]");
  if (!bar) return;
  var count = bar.querySelector("[data-pick-count]");
  var picks = document.querySelectorAll("[data-pick]");
  function update() {
    var n = 0;
    picks.forEach(function (p) { if (p.checked) n++; });
    count.textContent = n;
    bar.hidden = n === 0;
  }
  picks.forEach(function (p) { p.addEventListener("change", update); });
  update();
})();

// ---- Mini challenge complete: count the EXP up, then let them close the celebration
(function () {
  var win = document.querySelector("[data-win]");
  if (!win) return;
  var target = parseInt(win.getAttribute("data-exp"), 10) || 0;
  var out = win.querySelector("[data-win-count]");
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (out && !still && target > 0) {
    var start = null;
    out.textContent = "0";
    var step = function (t) {
      if (start === null) start = t + 250 + (parseInt(win.getAttribute("data-delay"), 10) || 0);  // after the finish line
      var p = Math.max(0, Math.min(1, (t - start) / 900));
      out.textContent = String(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) requestAnimationFrame(step);
      else if (out.parentNode) out.parentNode.classList.add("landed");   // a little bump on the final number
    };
    requestAnimationFrame(step);
  }
  var close = function () {
    if (still) { win.remove(); return; }
    win.classList.add("closing");
    setTimeout(function () {          // then fold the gap away so the list slides up smoothly
      win.style.height = win.offsetHeight + "px";
      win.classList.add("folding");
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { win.style.height = "0px"; win.style.marginBottom = "0px"; });
      });
      setTimeout(function () { win.remove(); }, 360);
    }, 260);
  };
  var btn = win.querySelector("[data-win-close]");
  if (btn) btn.addEventListener("click", close);
})();

// ---- Workout scenes: the athlete is SVG animation, so pause it when the phone asks for less motion
if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  // The workout figure keeps moving: it shows HOW to do the exercise. Only the celebration
  // (pure decoration) is stilled; removing its movement leaves every part in its clean first pose.
  document.querySelectorAll(".game-cheer animate, .game-cheer animateTransform").forEach(function (a) {
    a.parentNode.removeChild(a);
  });
}

// ---- Walk challenges: the athlete waits at the last checkpoint reached and walks to the next
// one only when the steps get there (every fifth of the walk). Remembers where it was shown, so
// after an iPhone sync the walker walks on from where you last saw it.
(function () {
  var game = document.querySelector(".game-walk[data-reached]");
  var box = document.querySelector("[data-mini-live]");
  if (!game || !box) return;
  var xs = game.getAttribute("data-course").split(",").map(Number);
  var walker = game.querySelector(".walker");
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var key = "sb_walk_" + (box.getAttribute("data-run") || "");
  var get = function () { try { return parseInt(localStorage.getItem(key), 10); } catch (e) { return NaN; } };
  var put = function (k) { try { localStorage.setItem(key, String(k)); } catch (e) { /* fine */ } };
  var at = get(), target = parseInt(game.getAttribute("data-reached"), 10) || 0, busy = false, done = null;
  if (isNaN(at) || at > target) at = 0;

  function mark(hop) {
    game.querySelectorAll(".g-cp").forEach(function (cp) {
      var on = parseInt(cp.getAttribute("data-cp"), 10) <= at;
      if (hop && on && !cp.classList.contains("passed")) cp.classList.add("just-passed");
      cp.classList.toggle("passed", on);
    });
  }
  function place(k, ms) {
    // eases in and out of each checkpoint instead of starting and stopping dead
    walker.style.transition = ms ? "transform " + ms + "ms cubic-bezier(.4, 0, .4, 1)" : "none";
    walker.style.transform = "translateX(" + xs[k] + "px)";
  }
  function step() {
    if (at >= target) {
      busy = false; walker.classList.remove("walking"); put(at); mark();
      if (done && at >= 5) { var cb = done; done = null; setTimeout(cb, 500); }
      return;
    }
    busy = true; at += 1;
    if (still) { place(at, 0); step(); return; }
    walker.classList.add("walking");
    place(at, 1900);
    setTimeout(function () { mark(true); step(); }, 1950);
  }
  place(at, 0); mark();
  requestAnimationFrame(function () { setTimeout(step, 600); });

  window.StrideBoardWalk = {
    update: function (walked, goal) {
      var k = Math.min(5, Math.floor(walked * 5 / goal));
      if (k > target) { target = k; if (!busy) step(); }
    },
    atFlag: function (cb) { done = cb; target = 5; if (!busy) step(); }
  };
})();

// Phone tab bar: scrolling down shrinks it into a round menu button (more of the page shows);
// tapping the button, or scrolling back to the top, opens the full bar again.
(function () {
  var nav = document.querySelector(".bottom-nav");
  if (!nav) return;
  var btn = nav.querySelector(".nav-toggle"), last = window.scrollY;
  function mini(on) {
    if (nav.classList.contains("nav-mini") === on) return;
    nav.classList.toggle("nav-mini", on);
    nav.classList.toggle("nav-open", !on);
    btn.setAttribute("aria-expanded", String(!on));
  }
  window.addEventListener("scroll", function () {
    var y = window.scrollY, d = y - last;
    if (y < 40) { mini(false); last = y; }
    else if (d > 12) { mini(true); last = y; }
    else if (d < -12) last = y;
  }, { passive: true });
  btn.addEventListener("click", function () { mini(false); });
})();

// Android app "Update" notice on Home: newer apps download and install the update themselves
// (Android then asks "Update StrideBoard?"). Older apps just follow the download link.
(function () {
  var btn = document.querySelector("[data-app-update-button]");
  if (!btn || !(window.StrideBoardApp && window.StrideBoardApp.installUpdate)) return;
  btn.addEventListener("click", function (e) {
    e.preventDefault();
    btn.textContent = "Downloading…";
    window.StrideBoardApp.installUpdate();
    setTimeout(function () { btn.textContent = "Update"; }, 15000);
  });
})();

// Offline Home: the service worker shows the last saved Home when there's no internet.
// Say so, grey out anything that needs the internet, and refresh once it's back.
(function () {
  var saved = document.documentElement.getAttribute("data-offline-copy");
  if (!saved) return;
  var when = new Date(+saved);
  var label = when.toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" });
  var note = document.createElement("div");
  note.className = "offline-note";
  note.setAttribute("role", "status");
  note.textContent = "You're offline \u00b7 this is your Home from " + label + ". It updates when you're back online.";
  var main = document.querySelector(".main");
  if (main) main.insertBefore(note, main.firstChild);
  document.querySelectorAll("form button, form input, [data-app-update-button]").forEach(function (el) {
    el.disabled = true;
    el.setAttribute("title", "Needs the internet");
  });
  window.addEventListener("online", function () { location.reload(); });
})();

// Under-18s: a break after BREAK_AFTER minutes of using the app (UAE Child Digital Safety Law).
// Time only counts while a page is open and visible; 5 minutes away counts as a break already.
// Kept in sessionStorage, so it carries across pages but not to someone else's browser.
(function () {
  var body = document.body, veil = document.querySelector("[data-break]");
  var after = parseInt(body.getAttribute("data-break-after"), 10) || 0;
  if (!after || !veil) return;
  var wait = parseInt(body.getAttribute("data-break-seconds"), 10) || 60;
  var btn = veil.querySelector("[data-break-done]"), count = veil.querySelector("[data-break-count]");
  var load = function (k) { try { return parseInt(sessionStorage.getItem(k), 10) || 0; } catch (e) { return 0; } };
  var save = function (k, v) { try { sessionStorage.setItem(k, String(v)); } catch (e) { /* fine */ } };
  var used = load("sb_used"), last = load("sb_last"), breakEnds = load("sb_break_until");
  if (last && Date.now() - last > 5 * 60 * 1000) used = 0;        // they were away: that was a break
  function show() {
    if (!breakEnds) { breakEnds = Date.now() + wait * 1000; save("sb_break_until", breakEnds); }
    veil.hidden = false;
    btn.disabled = true;
    var timer = setInterval(function () {
      var left = Math.ceil((breakEnds - Date.now()) / 1000);
      if (left > 0) { count.textContent = left; return; }
      clearInterval(timer);
      btn.disabled = false;
      btn.textContent = "Keep going";
      btn.focus();
    }, 250);
  }
  btn.addEventListener("click", function () {
    veil.hidden = true; used = 0; breakEnds = 0;
    save("sb_used", 0); save("sb_break_until", 0);
  });
  if (breakEnds) show();
  setInterval(function () {
    if (document.hidden || !veil.hidden) return;
    used += 15; last = Date.now();
    save("sb_used", used); save("sb_last", last);
    if (used >= after * 60) show();
  }, 15000);
})();

// A parent's daily time limit: tell the server each minute the app is open, and show the
// "Time's up" page as soon as the minutes run out.
(function () {
  if (!document.body.getAttribute("data-screen-limit")) return;
  setInterval(function () {
    if (document.hidden || !window.fetch) return;
    fetch("/ping", { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d && d.over) location.reload(); })
      .catch(function () { /* offline: fine */ });
  }, 60000);
})();
