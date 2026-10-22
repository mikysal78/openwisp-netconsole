"use strict";
// Scheda «Netconsole» del device: chiede al server solo le righe nuove
// (parametro pos) mentre la scheda e' aperta e la pagina e' visibile.
// Il testo dei log entra nella pagina solo come textContent.
(function () {
  var MAX_SHOWN = 5000;

  function init(box) {
    var url = box.dataset.url,
      refresh = Math.max(parseInt(box.dataset.refresh, 10) || 5, 2) * 1000,
      log = box.querySelector(".netconsole-log"),
      select = box.querySelector(".netconsole-source"),
      follow = box.querySelector(".netconsole-follow"),
      status = box.querySelector(".netconsole-status"),
      fileList = box.querySelector(".netconsole-file-list"),
      group = document.getElementById("netconsole-group"),
      source = "",
      pos = "",
      timer = null,
      busy = false;

    function visible() {
      return !document.hidden && group && group.classList.contains("current");
    }

    function sizeText(bytes) {
      return bytes >= 1048576
        ? (bytes / 1048576).toFixed(1) + " MB"
        : Math.max(1, Math.round(bytes / 1024)) + " KB";
    }

    function render(data) {
      var atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 20;
      // sorgenti
      var keys = data.sources.map(function (s) { return s.key; });
      if (keys.join("|") !== Array.prototype.map.call(select.options, function (o) { return o.value; }).join("|")) {
        select.textContent = "";
        data.sources.forEach(function (s) {
          var opt = document.createElement("option");
          opt.value = s.key;
          opt.textContent = s.kind === "name" ? s.key : "IP " + s.key;
          select.appendChild(opt);
        });
      }
      select.value = data.source;
      source = data.source;
      pos = data.pos;
      // righe
      if (data.reset) {
        log.textContent = "";
      }
      if (data.lines.length) {
        log.appendChild(document.createTextNode(data.lines.join("\n") + "\n"));
        // limita il testo tenuto in pagina
        var text = log.textContent, lines = text.split("\n");
        if (lines.length > MAX_SHOWN) {
          log.textContent = lines.slice(lines.length - MAX_SHOWN).join("\n");
        }
      }
      if (!source) {
        log.textContent = box.dataset.empty;
      }
      if (atBottom || data.reset) {
        log.scrollTop = log.scrollHeight;
      }
      // file da scaricare
      fileList.textContent = "";
      data.files.forEach(function (f) {
        var a = document.createElement("a");
        a.href = f.url;
        a.textContent = f.name + " (" + sizeText(f.size) + ")";
        fileList.appendChild(a);
      });
      status.textContent = box.dataset.updated + " " + new Date().toLocaleTimeString();
    }

    function load(force) {
      if (busy || (!force && !visible())) {
        return;
      }
      busy = true;
      var q = new URLSearchParams();
      if (source) {
        q.set("source", source);
        q.set("pos", pos);
      }
      fetch(url + "?" + q.toString(), {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      })
        .then(function (r) {
          if (!r.ok) {
            throw new Error(r.status);
          }
          return r.json();
        })
        .then(render)
        .catch(function () {
          status.textContent = box.dataset.error;
        })
        .finally(function () {
          busy = false;
        });
    }

    function schedule() {
      clearInterval(timer);
      timer = follow.checked ? setInterval(load, refresh) : null;
    }

    select.addEventListener("change", function () {
      source = select.value;
      pos = "";
      load(true);
    });
    follow.addEventListener("change", schedule);
    document.addEventListener("visibilitychange", function () {
      if (visible()) {
        load(true);
      }
    });
    // la scheda viene mostrata da tabs.js di openwisp-controller (evento jQuery)
    if (window.django && window.django.jQuery) {
      window.django.jQuery(document).on("tabshown", function (e) {
        if (e.tabId === "#netconsole-group") {
          load(true);
        }
      });
    }
    if (visible()) {
      load(true);
    }
    schedule();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("#netconsole-group .netconsole").forEach(init);
  });
})();
