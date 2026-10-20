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
