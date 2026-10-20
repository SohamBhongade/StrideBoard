// Weekly Wrap-Up chart: steps as rounded bars, mood as a pink line (Chart.js).
(function () {
  var data = window.STRIDE_CHART;
  var canvas = document.getElementById("moodChart");
  if (!data || !canvas || !window.Chart) return;

  // Colours come from the page, so the chart matches light and dark mode.
  var css = getComputedStyle(document.documentElement);
  var v = function (name, fallback) { return (css.getPropertyValue(name) || "").trim() || fallback; };
  Chart.defaults.font.family = '"Outfit", system-ui, sans-serif';
  Chart.defaults.color = v("--muted", "#565B66");

  // The best day gets the brighter periwinkle colour.
  var best = Math.max.apply(null, data.steps);
  var colours = data.steps.map(function (s) { return s === best && s > 0 ? "#A9B4F7" : "#BCCFD8"; });

  new Chart(canvas, {
    data: {
      labels: data.labels,
      datasets: [
        {
          type: "bar", label: "Steps", data: data.steps, yAxisID: "y",
          backgroundColor: colours, borderRadius: 14, borderSkipped: false,
          maxBarThickness: 64, order: 2
        },
        {
          type: "line", label: "Mood", data: data.moods, yAxisID: "y1",
          borderColor: "#E58AAB", backgroundColor: "#E58AAB", borderWidth: 3,
          pointRadius: 6, pointHoverRadius: 8, pointBackgroundColor: v("--white", "#fff"),
          pointBorderWidth: 3, tension: 0.35, spanGaps: true, order: 1,
          clip: false // so a mood of 5 isn't cut off at the top edge
        }
      ]
    },
    options: {
      maintainAspectRatio: false,
      layout: { padding: { top: 12 } },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#17181C", padding: 12, cornerRadius: 12,
          callbacks: {
            label: function (c) {
              if (c.dataset.label === "Mood") return " Mood: " + (c.raw == null ? "not logged" : c.raw + " of 5");
              return " Steps: " + Number(c.raw).toLocaleString("en-US");
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false }, border: { display: false } },
        y: {
          beginAtZero: true, border: { display: false },
          grid: { color: v("--chart-grid", "#EEF0F2") },
          ticks: { callback: function (v) { return v >= 1000 ? v / 1000 + "k" : v; } }
        },
        y1: {
          position: "right", min: 1, max: 5, border: { display: false },
          grid: { display: false }, ticks: { stepSize: 1 }
        }
      }
    }
  });
})();
