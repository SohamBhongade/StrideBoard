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

  // ---- Dashboard water +/- and mood: save without reloading the page.
  // If anything goes wrong, the form is sent the normal way instead.
  function updateWater(res) {
    var count = document.querySelector("[data-water-count]");
    if (!count) return;
    var old = parseInt(count.textContent, 10) || 0;
    count.textContent = res.water;
    document.querySelectorAll("[data-water-blocks] .block").forEach(function (b, i) {
      var on = i < res.water;
      b.classList.toggle("on", on);
      b.classList.toggle("just-on", on && i >= old);   // only new glasses animate
    });
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
      if (left <= 0) { done.disabled = false; if (label) label.textContent = "Done"; }
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
    var n = box.querySelector("[data-walk-done]");
    if (n) n.textContent = walked.toLocaleString("en-US");
    var bar = box.querySelector("[data-walk-bar]");
    if (bar) bar.style.setProperty("--w", Math.floor(walked * 100 / goal) + "%");
    if (walked >= goal && !reloading) { reloading = true; setTimeout(function () { location.reload(); }, 1200); }
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
      if (start === null) start = t + 250;            // wait for the number to pop in
      var p = Math.max(0, Math.min(1, (t - start) / 900));
      out.textContent = String(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  var close = function () {
    win.classList.add("closing");
    setTimeout(function () { win.remove(); }, still ? 0 : 300);
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
