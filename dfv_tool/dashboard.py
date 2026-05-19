"""
DFV Dashboard Generator - Creates a single HTML file with:
  1. Current week KPI status cards
  2. Action items table (grouped by Owner, filterable)
  3. Historical trend charts (volume diff%, error count)
  4. Week selector to view past weeks' actions
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from history import get_all_data

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


def generate_dashboard():
    """Generate DFV_Dashboard.html with all history data."""
    runs = get_all_data()
    if not runs:
        print("No history data. Run the pipeline first.")
        return

    # Prepare JSON data for embedding
    # runs[0] is the latest (DESC order)
    data_json = json.dumps(runs, ensure_ascii=False, default=str)

    html = _build_html(data_json, runs)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, "DFV_Dashboard.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard: {out_path}")
    return out_path


def _build_html(data_json, runs):
    # Use string.replace instead of f-string to avoid brace escaping issues
    template = _get_template()
    return template.replace('__DATA_JSON__', data_json)


def _get_template():
    return r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DFV Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root { --blue:#0078d4; --dark:#1a1a2e; --bg:#f5f6fa; --card:#fff; --border:#e2e5ea;
         --green:#28a745; --red:#dc3545; --orange:#fd7e14; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI',sans-serif; background:var(--bg); color:#333; }
.topbar { background:var(--dark); color:#fff; padding:18px 32px; display:flex;
           align-items:center; justify-content:space-between; }
.topbar h1 { font-size:1.3em; font-weight:400; letter-spacing:1px; }
.topbar .week-sel { display:flex; align-items:center; gap:10px; }
.topbar .sync-btn { padding:7px 16px; border-radius:5px; border:1px solid #555;
                    background:#2a2a4a; color:#ddd; font-size:0.82em; cursor:pointer;
                    transition:all 0.15s; }
.topbar .sync-btn:hover { background:var(--blue); color:#fff; border-color:var(--blue); }
.topbar .sync-btn.done { background:var(--green); color:#fff; border-color:var(--green); }
.topbar select { padding:6px 12px; border-radius:4px; border:1px solid #555;
                  background:#2a2a4a; color:#fff; font-size:0.9em; cursor:pointer; }
.kpi-row { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; padding:24px 32px 8px; }
.kpi { background:var(--card); border-radius:8px; padding:20px 24px; border-left:4px solid var(--blue); }
.kpi-label { font-size:0.8em; color:#777; text-transform:uppercase; letter-spacing:0.5px; }
.kpi-value { font-size:1.8em; font-weight:600; margin:4px 0; }
.kpi-sub { font-size:0.82em; color:#999; }
.kpi.on-track { border-left-color:var(--green); }
.kpi.off-track { border-left-color:var(--red); }
.main { padding:16px 32px 40px; }
.section-title { font-size:1.15em; font-weight:600; color:var(--dark);
                  margin:24px 0 12px; display:flex; align-items:center; gap:12px; }
.section-title .badge { background:var(--red); color:#fff; padding:2px 10px;
                         border-radius:12px; font-size:0.75em; }
.filters { display:flex; gap:12px; margin-bottom:12px; flex-wrap:wrap; }
.filters button { padding:6px 16px; border:1px solid var(--border); border-radius:20px;
                   background:#fff; cursor:pointer; font-size:0.82em; transition:all 0.15s; }
.filters button:hover { border-color:var(--blue); color:var(--blue); }
.filters button.active { background:var(--blue); color:#fff; border-color:var(--blue); }
.action-table { width:100%; border-collapse:collapse; font-size:0.85em; background:#fff;
                 border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.06); }
.action-table thead th { background:var(--dark); color:#fff; padding:10px 10px;
                          text-align:left; font-weight:500; position:sticky; top:0; }
.action-table tbody td { padding:9px 10px; border-bottom:1px solid #f0f0f0; }
.action-table tbody tr:hover { background:#f0f6ff; }
.action-table .owner-cell { white-space:nowrap; }
.tag { display:inline-block; padding:2px 8px; border-radius:10px; font-size:0.78em; font-weight:600; }
.tag-dp { background:#fff3cd; color:#856404; }
.tag-drp { background:#cce5ff; color:#004085; }
.tag-iol { background:#d4edda; color:#155724; }
.chart-row { display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-top:28px; }
.chart-card { background:#fff; border-radius:8px; padding:20px; }
.chart-card h3 { font-size:0.95em; color:#555; margin-bottom:12px; }
.no-actions { text-align:center; padding:40px; color:#999; font-size:1.1em; }
.copy-btn { padding:8px 18px; background:var(--blue); color:#fff; border:none; border-radius:6px;
            cursor:pointer; font-size:0.85em; margin-left:auto; transition:all 0.15s; }
.copy-btn:hover { background:#005a9e; }
.copy-btn.copied { background:var(--green); }
@media(max-width:900px) {
  .kpi-row { grid-template-columns:repeat(2,1fr); }
  .chart-row { grid-template-columns:1fr; }
}
@media(max-width:600px) {
  .kpi-row { grid-template-columns:1fr; }
  .topbar { flex-direction:column; gap:10px; }
}
</style>
</head>
<body>

<div class="topbar">
  <h1>DFV Dashboard</h1>
  <div class="week-sel">
    <button class="sync-btn" onclick="syncOwners()" title="Copy sync command to clipboard">Sync Owners</button>
    <span style="font-size:0.85em;color:#aaa;">Select Week:</span>
    <select id="weekPicker" onchange="switchWeek(this.value)"></select>
  </div>
</div>

<div class="kpi-row" id="kpiRow"></div>

<div class="main">
  <div class="chart-row">
    <div class="chart-card">
      <h3>Volume Difference % (18 Months) &mdash; Target &lt; 2%</h3>
      <canvas id="chartDiff"></canvas>
    </div>
    <div class="chart-card">
      <h3>Error SKU Count (13 Weeks)</h3>
      <canvas id="chartSKU"></canvas>
    </div>
  </div>

  <div class="section-title">
    Action Items <span class="badge" id="actionCount">0</span>
    <button class="copy-btn" onclick="copyTable()">Copy Table</button>
  </div>
  <div class="filters" id="ownerFilters"></div>
  <div id="actionTableWrap"></div>
</div>

<script>
var DATA = __DATA_JSON__;

var picker = document.getElementById("weekPicker");
for (var i = 0; i < DATA.length; i++) {
  var opt = document.createElement("option");
  opt.value = i;
  opt.textContent = DATA[i].week_label + " (" + DATA[i].run_date.split(" ")[0] + ")";
  picker.appendChild(opt);
}

var currentFilter = "all";

function switchWeek(idx) {
  var run = DATA[idx];
  renderKPI(run);
  renderActions(run.errors || []);
}

function fmt(n) {
  if (n == null) return "?";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return n.toFixed(0);
}

function renderKPI(run) {
  var diff = run.diff_pct != null ? run.diff_pct.toFixed(2) : "?";
  var volCls = run.vol_status === "on-track" ? "on-track" : "off-track";
  var skuCls = run.sku_status === "on-track" ? "on-track" : "off-track";
  document.getElementById("kpiRow").innerHTML =
    '<div class="kpi ' + volCls + '">' +
      '<div class="kpi-label">Volume Diff %</div>' +
      '<div class="kpi-value">' + diff + '%</div>' +
      '<div class="kpi-sub">Target &lt; 2% &mdash; ' + run.vol_status.toUpperCase() + '</div>' +
    '</div>' +
    '<div class="kpi ' + skuCls + '">' +
      '<div class="kpi-label">Error SKUs</div>' +
      '<div class="kpi-value">' + run.total_errors + '</div>' +
      '<div class="kpi-sub">' + run.actionable_errors + ' actionable, ' + run.hktw_errors + ' HKTW</div>' +
    '</div>' +
    '<div class="kpi">' +
      '<div class="kpi-label">Demand Hub</div>' +
      '<div class="kpi-value">' + fmt(run.total_idp) + '</div>' +
      '<div class="kpi-sub">Total IDP Forecast</div>' +
    '</div>' +
    '<div class="kpi">' +
      '<div class="kpi-label">APO-DRP</div>' +
      '<div class="kpi-value">' + fmt(run.total_apo) + '</div>' +
      '<div class="kpi-sub">Impact: ' + fmt(run.impact_volume) + ' MSU</div>' +
    '</div>';
}

function renderActions(errors) {
  var owners = [];
  var seen = {};
  for (var i = 0; i < errors.length; i++) {
    if (!seen[errors[i].owner]) { seen[errors[i].owner] = true; owners.push(errors[i].owner); }
  }
  owners.sort();

  var fhtml = '<button class="' + (currentFilter === "all" ? "active" : "") +
    '" onclick="setFilter(&quot;all&quot;)">All</button>';
  for (var j = 0; j < owners.length; j++) {
    var esc = owners[j].replace(/"/g, "&quot;");
    fhtml += '<button class="' + (currentFilter === owners[j] ? "active" : "") +
      '" onclick="setFilter(&quot;' + esc + '&quot;)">' + owners[j] + '</button>';
  }
  document.getElementById("ownerFilters").innerHTML = fhtml;

  var filtered = currentFilter === "all" ? errors : errors.filter(function(e) { return e.owner === currentFilter; });
  document.getElementById("actionCount").textContent = filtered.length;

  if (filtered.length === 0) {
    document.getElementById("actionTableWrap").innerHTML =
      '<div class="no-actions">No action items for this week</div>';
    return;
  }

  var html = '<table class="action-table" id="actionTable"><thead><tr>' +
    '<th>Product</th><th>Description</th><th>Brand</th><th>Location</th><th>Error</th>' +
    '<th>Forecast</th><th>Reason</th><th>Action</th><th>Owner</th>' +
    '</tr></thead><tbody>';

  for (var k = 0; k < filtered.length; k++) {
    var e = filtered[k];
    var ownerTag = e.owner.indexOf("IOL") >= 0 ? "tag-iol" :
                   e.owner.indexOf("DP") >= 0 ? "tag-dp" : "tag-drp";
    var fcst = Math.round(e.idp_forecast).toLocaleString();
    html += '<tr>' +
      '<td><strong>' + e.apo_product + '</strong></td>' +
      '<td>' + (e.description || "") + '</td>' +
      '<td>' + (e.brand || "") + '</td>' +
      '<td>' + e.apo_location + '</td>' +
      '<td>' + e.error_message + '</td>' +
      '<td style="text-align:right">' + fcst + '</td>' +
      '<td>' + e.reason + '</td>' +
      '<td><strong>' + e.action + '</strong></td>' +
      '<td class="owner-cell"><span class="tag ' + ownerTag + '">' + e.owner + '</span></td>' +
      '</tr>';
  }
  html += '</tbody></table>';
  document.getElementById("actionTableWrap").innerHTML = html;
}

function copyTable() {
  var table = document.getElementById("actionTable");
  if (!table) return;
  // Build HTML table for rich paste (email)
  var hdr = '#1a1a2e';
  var html = '<table style="border-collapse:collapse;font-family:Segoe UI,sans-serif;font-size:12px;">';
  var rows = table.querySelectorAll("tr");
  for (var i = 0; i < rows.length; i++) {
    html += '<tr>';
    var cells = rows[i].querySelectorAll("th, td");
    for (var j = 0; j < cells.length; j++) {
      var tag = cells[j].tagName === 'TH' ? 'th' : 'td';
      var style = tag === 'th'
        ? 'background:' + hdr + ';color:#fff;padding:6px 10px;text-align:left;border:1px solid #ccc;'
        : 'padding:5px 10px;border:1px solid #e0e0e0;' + (j === 5 ? 'text-align:right;' : '');
      html += '<' + tag + ' style="' + style + '">' + cells[j].innerText + '</' + tag + '>';
    }
    html += '</tr>';
  }
  html += '</table>';
  // Also build plain text version
  var tsv = [];
  for (var i2 = 0; i2 < rows.length; i2++) {
    var cells2 = rows[i2].querySelectorAll("th, td");
    var row = [];
    for (var j2 = 0; j2 < cells2.length; j2++) row.push(cells2[j2].innerText.replace(/\t/g, ' '));
    tsv.push(row.join('\t'));
  }
  var plain = tsv.join('\n');
  // Write both HTML and plain text to clipboard
  var blob = new Blob([html], {type: 'text/html'});
  var blobText = new Blob([plain], {type: 'text/plain'});
  var item = new ClipboardItem({'text/html': blob, 'text/plain': blobText});
  navigator.clipboard.write([item]).then(function() {
    var btn = document.querySelector('.copy-btn');
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(function() { btn.textContent = 'Copy Table'; btn.classList.remove('copied'); }, 2000);
  });
}

function syncOwners() {
  var cmd = "cd c:\\0.Local\\17.DFV && python dfv_tool/sync_owners.py";
  navigator.clipboard.writeText(cmd).then(function() {
    var btn = document.querySelector(".sync-btn");
    btn.textContent = "Command Copied!";
    btn.classList.add("done");
    setTimeout(function() { btn.textContent = "Sync Owners"; btn.classList.remove("done"); }, 3000);
  });
}

function setFilter(f) {
  currentFilter = f;
  var idx = document.getElementById("weekPicker").value;
  renderActions(DATA[idx].errors || []);
}

function renderCharts() {
  var sorted = DATA.slice().reverse();
  var labels = sorted.map(function(r) { return r.week_label; });
  var diffs = sorted.map(function(r) { return r.diff_pct; });
  var skus = sorted.map(function(r) { return r.total_errors; });
  var actionable = sorted.map(function(r) { return r.actionable_errors; });

  new Chart(document.getElementById("chartDiff"), {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        { label: "Volume Diff %", data: diffs, borderColor: "#0078d4",
          backgroundColor: "rgba(0,120,212,0.08)", fill: true, tension: 0.3, pointRadius: 4 },
        { label: "Target (2%)", data: labels.map(function() { return 2; }),
          borderColor: "#dc3545", borderDash: [6,4], pointRadius: 0, borderWidth: 2 }
      ]
    },
    options: { responsive: true, plugins: { legend: { position: "bottom" } },
               scales: { y: { beginAtZero: true, title: { display: true, text: "%" } } } }
  });

  new Chart(document.getElementById("chartSKU"), {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        { label: "Total Errors", data: skus, backgroundColor: "rgba(220,53,69,0.15)",
          borderColor: "#dc3545", borderWidth: 1 },
        { label: "Actionable", data: actionable, backgroundColor: "rgba(0,120,212,0.6)",
          borderColor: "#0078d4", borderWidth: 1 }
      ]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: "bottom" },
        datalabels: {
          anchor: "end", align: "top", font: { weight: "bold", size: 11 },
          formatter: function(v) { return v; }
        }
      },
      scales: { y: { beginAtZero: true, title: { display: true, text: "SKU Count" } } }
    },
    plugins: [{
      id: "barLabels",
      afterDatasetsDraw: function(chart) {
        var ctx = chart.ctx;
        chart.data.datasets.forEach(function(ds, di) {
          var meta = chart.getDatasetMeta(di);
          meta.data.forEach(function(bar, idx) {
            var val = ds.data[idx];
            if (val == null) return;
            ctx.save();
            ctx.fillStyle = ds.borderColor || "#333";
            ctx.font = "bold 11px Segoe UI,sans-serif";
            ctx.textAlign = "center";
            ctx.fillText(val, bar.x, bar.y - 6);
            ctx.restore();
          });
        });
      }
    }]
  });
}

switchWeek(0);
if (typeof Chart !== "undefined") {
  renderCharts();
} else {
  var cards = document.querySelectorAll(".chart-card");
  for (var c = 0; c < cards.length; c++) {
    cards[c].innerHTML = '<p style="color:#999;padding:20px">Chart.js CDN not reachable.</p>';
  }
}
</script>
</body>
</html>'''


if __name__ == "__main__":
    generate_dashboard()
