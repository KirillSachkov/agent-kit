/* agent-clarity page: table of contents, sequence steps with notes, zoom for diagrams and screenshots. No network. */
(function () {
  "use strict";
  const toc = [...document.querySelectorAll(".toc a")];
  const secs = toc.map((a) => document.getElementById(a.getAttribute("href").slice(1)));
  toc.forEach((a, i) => (a.onclick = (e) => { e.preventDefault(); secs[i]?.scrollIntoView({ behavior: "smooth" }); }));
  const spy = () => {
    let cur = 0;
    secs.forEach((s, i) => { if (s && s.getBoundingClientRect().top < 140) cur = i; });
    toc.forEach((a, i) => a.classList.toggle("on", i === cur));
  };
  addEventListener("scroll", spy, { passive: true });
  spy();

  // Zoom: a diagram or a screenshot opens full screen; wheel or buttons zoom, drag moves, Esc closes.
  function zoom(node, caption) {
    const box = document.createElement("div");
    box.className = "zoom";
    box.innerHTML = '<div class="zbar"><button data-z="-">−</button><button data-z="+">+</button><button data-z="fit">Вписать</button><span></span><span style="flex:1"></span><button data-z="x">Закрыть · Esc</button></div><div class="zstage"><div class="zin"></div></div>';
    box.querySelector(".zbar span").textContent = caption || "";
    const stage = box.querySelector(".zstage"), inner = box.querySelector(".zin");
    const copy = node.cloneNode(true);
    copy.removeAttribute("style");
    if (node.tagName !== "IMG") inner.classList.add("mm");  // keep the theme colours of the diagram
    inner.append(copy);
    document.querySelector(".pg").append(box);
    const w = node.getBoundingClientRect().width;
    const natural = node.tagName === "IMG" ? { w: node.naturalWidth, h: node.naturalHeight } : (() => { const vb = node.viewBox?.baseVal; return vb && vb.width ? { w: vb.width, h: vb.height } : { w: w, h: node.getBoundingClientRect().height }; })();
    copy.setAttribute("width", natural.w);
    copy.setAttribute("height", natural.h);
    let k = 1, x = 0, y = 0, drag = null;
    const apply = () => (inner.style.transform = `translate(${x}px,${y}px) scale(${k})`);
    const fit = () => { const W = stage.clientWidth, H = stage.clientHeight; k = Math.min(W / natural.w, H / natural.h) * 0.94; x = (W - natural.w * k) / 2; y = (H - natural.h * k) / 2; apply(); };
    const at = (f, cx, cy) => { const nk = Math.min(8, Math.max(0.2, k * f)); x = cx - (cx - x) * nk / k; y = cy - (cy - y) * nk / k; k = nk; apply(); };
    stage.addEventListener("wheel", (e) => { e.preventDefault(); const r = stage.getBoundingClientRect(); at(Math.exp(-e.deltaY * 0.0015 * (e.ctrlKey ? 6 : 1)), e.clientX - r.left, e.clientY - r.top); }, { passive: false });
    stage.addEventListener("pointerdown", (e) => { drag = { sx: e.clientX, sy: e.clientY, x, y }; stage.classList.add("drag"); });
    const move = (e) => { if (drag) { x = drag.x + e.clientX - drag.sx; y = drag.y + e.clientY - drag.sy; apply(); } };
    const up = () => { drag = null; stage.classList.remove("drag"); };
    addEventListener("pointermove", move);
    addEventListener("pointerup", up);
    const close = () => { box.remove(); removeEventListener("pointermove", move); removeEventListener("pointerup", up); removeEventListener("keydown", key); };
    const key = (e) => { if (e.key === "Escape") close(); };
    addEventListener("keydown", key);
    box.querySelector(".zbar").onclick = (e) => {
      const z = e.target.closest("button")?.dataset.z;
      if (z === "x") close(); else if (z === "fit") fit(); else if (z) at(z === "+" ? 1.3 : 1 / 1.3, stage.clientWidth / 2, stage.clientHeight / 2);
    };
    fit();
  }
  document.querySelectorAll(".mm svg").forEach((svg) => svg.addEventListener("click", () => {
    const sec = svg.closest(".sec");
    zoom(svg, svg.closest("figure").previousElementSibling?.matches("h3") ? svg.closest("figure").previousElementSibling.textContent : sec?.querySelector("h2")?.textContent);
  }));
  document.querySelectorAll(".shot img").forEach((img) => img.addEventListener("click", () => zoom(img, img.alt)));

  // Sequence diagrams: step through messages; an ordered list right after the diagram gives each step its note.
  document.querySelectorAll(".mm.seq").forEach((fig) => {
    const svg = fig.querySelector("svg");
    if (!svg) return;
    const lines = [...svg.querySelectorAll(".messageLine0, .messageLine1")];
    const texts = [...svg.querySelectorAll(".messageText")];
    const n = Math.min(lines.length, texts.length);
    if (n < 2) return;
    const list = fig.nextElementSibling && fig.nextElementSibling.tagName === "OL" ? fig.nextElementSibling : null;
    const notes = list ? [...list.children].map((li) => li.innerHTML) : [];
    if (list) list.classList.add("notes");
    let cur = -1;
    const bar = document.createElement("div");
    bar.className = "steps";
    bar.innerHTML = '<button data-d="-1" title="Назад">←</button><button data-d="1" title="Дальше">→</button><button data-d="0" title="Показать всё">все</button><span class="n"></span><div class="say"></div>';
    fig.after(bar);
    const say = bar.querySelector(".say");
    const show = (i) => {
      cur = i;
      for (let k = 0; k < n; k++) {
        const on = i < 0 || k === i, past = i >= 0 && k < i;
        [lines[k], texts[k]].forEach((el) => { el.classList.toggle("dim", !on && !past); el.classList.toggle("hot", i >= 0 && k === i); });
      }
      bar.querySelector(".n").textContent = i < 0 ? `${n} шагов` : `шаг ${i + 1} из ${n}`;
      if (i < 0) say.innerHTML = notes.length ? "Нажми →, чтобы пройти механизм по шагам." : "";
      else say.innerHTML = `<b>${texts[i].textContent}</b>${notes[i] || ""}`;
      say.style.display = say.innerHTML ? "" : "none";
    };
    bar.onclick = (e) => {
      const d = e.target.closest("button")?.dataset.d;
      if (d === undefined) return;
      if (d === "0") return show(-1);
      show(Math.max(0, Math.min(n - 1, cur + Number(d))));
    };
    show(-1);
  });
})();
