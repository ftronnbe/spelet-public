// Deep Regrats: the website's motion. Everything degrades to a plain, complete page without JavaScript
// or with prefers-reduced-motion. No trackers, no cookies, no requests to anyone else.
(() => {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fine = matchMedia("(pointer: fine)").matches;

  // ---- Store buttons (links from assets/js/links.js)
  const links = window.DEEP_REGRATS_LINKS || {};
  for (const [id, url] of [["badge-testflight", links.testFlight], ["badge-appstore", links.appStore]]) {
    const a = document.getElementById(id);
    if (!a || !url) continue;
    a.href = url;
    a.removeAttribute("aria-disabled");
    a.rel = "noopener";
    a.querySelectorAll("[data-when-off]").forEach((e) => (e.hidden = true));
    a.querySelectorAll("[data-when-on]").forEach((e) => (e.hidden = false));
  }

  // ---- Nav: solid once scrolled, menu button on small screens
  const nav = document.getElementById("nav");
  if (nav) {
    const onScroll = () => nav.classList.toggle("scrolled", scrollY > 30);
    addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    const btn = nav.querySelector(".menu-btn");
    btn?.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      btn.setAttribute("aria-expanded", open);
    });
    nav.querySelectorAll(".links a").forEach((a) => a.addEventListener("click", () => {
      nav.classList.remove("open");
      btn?.setAttribute("aria-expanded", "false");
    }));
    addEventListener("keydown", (e) => {
      if (e.key === "Escape" && nav.classList.contains("open")) { nav.classList.remove("open"); btn?.setAttribute("aria-expanded", "false"); btn?.focus(); }
    });
  }

  // ---- Scroll reveals
  const reveal = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); reveal.unobserve(e.target); }
  }, { rootMargin: "0px 0px -8% 0px" });
  document.querySelectorAll("[data-reveal]").forEach((el) => reveal.observe(el));

  // ---- Sprites only animate while on screen
  const spriteObs = new IntersectionObserver((entries) => {
    for (const e of entries) e.target.classList.toggle("paused", !e.isIntersecting);
  });
  document.querySelectorAll(".sprite").forEach((s) => spriteObs.observe(s));

  // ---- Tilt on hover (mouse only)
  if (fine && !reduced) {
    document.querySelectorAll("[data-tilt]").forEach((card) => {
      card.addEventListener("pointermove", (e) => {
        const r = card.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        card.style.setProperty("--ry", `${(x - 0.5) * 8}deg`);
        card.style.setProperty("--rx", `${(0.5 - y) * 8}deg`);
        card.style.setProperty("--mx", `${x * 100}%`);
        card.style.setProperty("--my", `${y * 100}%`);
      });
      card.addEventListener("pointerleave", () => { card.style.setProperty("--rx", "0deg"); card.style.setProperty("--ry", "0deg"); });
    });
  }

  // ---- Monster of the moment: one resident on duty at a time, a new random one every 12 seconds
  (function () {
    const dataEl = document.getElementById("monster-data");
    const spot = document.getElementById("spot");
    if (!dataEl || !spot) return;
    const list = JSON.parse(dataEl.textContent);
    const sprite = document.getElementById("spot-sprite");
    const nameEl = document.getElementById("spot-name"), descEl = document.getElementById("spot-desc"), whereEl = document.getElementById("spot-where");
    const countEl = document.getElementById("spot-count"), bar = document.getElementById("spot-bar");
    const SHOW_MS = 12000;
    let order = [], pos = -1, timer = 0, started = 0, left = SHOW_MS, held = false, visible = false;
    const shuffle = () => {              // a fresh shuffle each lap, and the same monster never shows twice in a row
      const last = order[order.length - 1];
      order = list.map((_, i) => i).sort(() => Math.random() - 0.5);
      if (order[0] === last) order.push(order.shift());
    };
    const show = (i) => {
      const m = list[i];
      const apply = () => {
        const k = 1.05;                                          // about native pixel size: the sprites are small, so showing them small keeps them crisp
        sprite.style.cssText = `--n:${m.n};--dur:${m.dur}s;aspect-ratio:${m.w} / ${m.h};height:${Math.round(m.h * k)}px;background-image:url(${m.img})`;
        nameEl.textContent = m.name; descEl.textContent = m.desc;
        whereEl.textContent = `${m.region}, ${m.floors.toLowerCase()}`;
        countEl.textContent = "";                                  // no counting the residents
        spot.classList.remove("swap");
      };
      if (reduced) return apply();
      spot.classList.add("swap"); setTimeout(apply, 260);
    };
    const go = (step) => {
      if (!order.length) shuffle();
      pos += step;
      if (pos >= order.length) { shuffle(); pos = 0; }
      if (pos < 0) pos = order.length - 1;
      show(order[pos]); left = SHOW_MS; started = performance.now(); tick();
    };
    const tick = () => {
      clearTimeout(timer); cancelAnimationFrame(spot._raf);
      const frame = () => {
        const elapsed = performance.now() - started, f = Math.min(1, elapsed / left);
        bar.style.transform = `scaleX(${f})`;
        if (f >= 1) { go(1); return; }
        spot._raf = requestAnimationFrame(frame);
      };
      if (!reduced && visible && !held) { started = performance.now(); spot._raf = requestAnimationFrame(frame); }
    };
    const pause = (v) => {
      if (v === held) return;
      if (v) { left = Math.max(1000, left - (performance.now() - started)); cancelAnimationFrame(spot._raf); }
      held = v; if (!v) { started = performance.now(); tick(); }
    };
    document.getElementById("spot-next").addEventListener("click", () => go(1));
    document.getElementById("spot-prev").addEventListener("click", () => go(-1));
    spot.addEventListener("pointerenter", () => { if (fine) pause(true); });
    spot.addEventListener("pointerleave", () => pause(false));
    spot.addEventListener("focusin", () => pause(true));
    spot.addEventListener("focusout", () => pause(false));
    new IntersectionObserver(([e]) => { visible = e.isIntersecting; spot.classList.toggle("paused", !visible); if (visible) { started = performance.now(); tick(); } else cancelAnimationFrame(spot._raf); }).observe(spot);
    go(1);
  })();

  // ---- Hero: parallax and embers
  const hero = document.querySelector(".hero");
  const scene = hero?.querySelector(".scene");
  let heroVisible = true;
  if (hero) new IntersectionObserver(([e]) => (heroVisible = e.isIntersecting)).observe(hero);

  if (scene && !reduced) {
    let tx = 0, ty = 0, cx = 0, cy = 0, raf = 0;
    const tick = () => {
      cx += (tx - cx) * 0.08; cy += (ty - cy) * 0.08;
      scene.style.setProperty("--px", cx.toFixed(3));
      scene.style.setProperty("--py", cy.toFixed(3));
      scene.style.setProperty("--sy", Math.min(scrollY, innerHeight).toFixed(0));
      raf = Math.abs(tx - cx) + Math.abs(ty - cy) > 0.002 ? requestAnimationFrame(tick) : 0;
    };
    const kick = () => { if (!raf) raf = requestAnimationFrame(tick); };
    addEventListener("pointermove", (e) => {
      if (!heroVisible || e.pointerType !== "mouse") return;
      tx = (e.clientX / innerWidth - 0.5) * 2; ty = (e.clientY / innerHeight - 0.5) * 2; kick();
    }, { passive: true });
    addEventListener("scroll", () => { if (heroVisible) kick(); }, { passive: true });
    // Tilt on phones that report it without asking (Android). iOS needs a permission prompt; we do not ask.
    addEventListener("deviceorientation", (e) => {
      if (e.gamma == null || !heroVisible) return;
      tx = Math.max(-1, Math.min(1, e.gamma / 25)); ty = Math.max(-1, Math.min(1, (e.beta - 45) / 25)); kick();
    }, { passive: true });
  }

  const canvas = document.getElementById("embers");
  if (canvas && hero && !reduced) {
    const ctx = canvas.getContext("2d");
    const VBW = 1600, VBH = 1000;
    const sources = [{ x: 800, y: 760, w: 120, n: 0.55 }, { x: 330, y: 720, w: 26, n: 0.22 }, { x: 1270, y: 720, w: 26, n: 0.22 }];
    let W = 0, H = 0, dpr = 1, s = 1, ox = 0, oy = 0, parts = [], last = performance.now();
    const resize = () => {
      dpr = Math.min(devicePixelRatio || 1, 2);
      W = hero.clientWidth; H = hero.clientHeight;
      canvas.width = W * dpr; canvas.height = H * dpr;
      // map the arch layer's viewBox (preserveAspectRatio slice) to canvas pixels
      const hb = hero.getBoundingClientRect(), lb = (hero.querySelector(".layer.arch") || hero).getBoundingClientRect();
      s = Math.max(lb.width / VBW, lb.height / VBH);
      ox = lb.left - hb.left + (lb.width - VBW * s) / 2; oy = lb.top - hb.top + (lb.height - VBH * s) / 2;
    };
    resize();
    addEventListener("resize", resize);
    const max = () => Math.round(Math.min(140, (W * H) / 9000));
    const spawn = () => {
      const r = Math.random(); let acc = 0, src = sources[0];
      for (const so of sources) { acc += so.n; if (r < acc) { src = so; break; } }
      return {
        x: ox + (src.x + (Math.random() - 0.5) * src.w) * s, y: oy + src.y * s,
        vx: (Math.random() - 0.5) * 14, vy: -(22 + Math.random() * 48) * Math.max(0.6, s),
        life: 0, ttl: 3 + Math.random() * 4, size: 0.8 + Math.random() * 2.2, wob: Math.random() * 6.28,
        hue: 18 + Math.random() * 26,
      };
    };
    const frame = (now) => {
      const dt = Math.min(0.05, (now - last) / 1000); last = now;
      if (heroVisible && !document.hidden) {
        while (parts.length < max() && Math.random() < 0.5) parts.push(spawn());
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, W, H);
        ctx.globalCompositeOperation = "lighter";
        for (let i = parts.length - 1; i >= 0; i--) {
          const p = parts[i];
          p.life += dt; p.wob += dt * 2;
          p.x += (p.vx + Math.sin(p.wob) * 10) * dt; p.y += p.vy * dt;
          if (p.life > p.ttl || p.y < -10) { parts.splice(i, 1); continue; }
          const t = p.life / p.ttl, a = Math.sin(Math.PI * Math.min(1, t)) * 0.9;
          const r = p.size * (1 - t * 0.5);
          const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 4);
          g.addColorStop(0, `hsla(${p.hue + 20}, 100%, 75%, ${a})`);
          g.addColorStop(0.3, `hsla(${p.hue}, 100%, 55%, ${a * 0.5})`);
          g.addColorStop(1, `hsla(${p.hue}, 100%, 50%, 0)`);
          ctx.fillStyle = g;
          ctx.beginPath(); ctx.arc(p.x, p.y, r * 4, 0, 6.283); ctx.fill();
        }
      }
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }

  // ---- Kevin: remarks and hats
  const QUOTES = [
    "Took you long enough.", "I waited. For three floors.", "Benefits: none. Hats sold separately.",
    "I am coming with you. Not up for discussion.", "Drink the red one. It is not a metaphor.",
    "A rare. Try to look like you earned it.", "Sell it. Buy a spine.", "That one is large. I will be over here. Far.",
    "A boss. How unexpectedly expected.", "I believe in you. From a distance.", "Welcome back. The stairs missed you.",
    "Level up. The bar was low and you cleared it.", "You picked up a stick. Of course you did.",
    "Hoarding. A brave life choice.", "Bloodshed. Very on-brand.", "Standing still. The peak of your career.",
    "Do not touch the ears.", "Purr. This is a reflex, not a feeling.", "Pats are rationed. Rationing is love.",
    "A hat. I will wear it ironically.", "Another floor. Still no windows.", "I hid. Tactically.", "Is it over? Good. I helped.",
  ];
  const bubble = document.getElementById("kevin-quote");
  const cat = document.getElementById("kevin-cat");
  const hatItems = [...document.querySelectorAll("#hat-list li")];
  QUOTES.sort(() => Math.random() - 0.5);               // a fresh order on every visit; they loop by themselves
  let q = 0, hat = 0, autoTimer = 0;
  const react = () => {                                  // a small nod each time he says something
    if (!cat || reduced) return;
    cat.classList.remove("react"); void cat.offsetWidth; cat.classList.add("react");
  };
  const say = (i) => {
    if (!bubble) return;
    q = (i + QUOTES.length) % QUOTES.length;
    const set = () => { bubble.innerHTML = `${QUOTES[q]}<cite>Kevin</cite>`; bubble.classList.remove("swap"); react(); };
    if (reduced) return set();
    bubble.classList.add("swap"); setTimeout(set, 300);
  };
  const wear = (h) => {
    if (!cat) return;
    const imgs = cat.querySelectorAll("img");
    hat = (h + imgs.length) % imgs.length;
    if (!reduced) { cat.classList.remove("pop"); void cat.offsetWidth; cat.classList.add("pop"); }
    imgs.forEach((im, i) => im.classList.toggle("on", i === hat));
    hatItems.forEach((li) => li.classList.toggle("on", Number(li.dataset.hat) === hat));
  };
  document.getElementById("kevin-hat")?.addEventListener("click", () => { wear(hat + 1); restart(); });
  hatItems.forEach((li) => {
    li.tabIndex = 0; li.setAttribute("role", "button");
    li.setAttribute("aria-label", `Put the ${li.querySelector("b").textContent} on Kevin`);
    const go = () => { wear(Number(li.dataset.hat)); restart(); };
    li.addEventListener("click", go);
    li.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
  });
  // Rotate on their own while the section is in view (not with reduced motion; the buttons still work).
  let kevinVisible = false;
  const kevinSec = document.getElementById("kevin");
  if (kevinSec) new IntersectionObserver(([e]) => { kevinVisible = e.isIntersecting; }).observe(kevinSec);
  function restart() {
    clearInterval(autoTimer);
    if (reduced) return;
    autoTimer = setInterval(() => { if (kevinVisible && !document.hidden) { say(q + 1); if (q % 3 === 0) wear(hat + 1); } }, 6500);
  }
  if (bubble) bubble.setAttribute("aria-live", "off");   // automatic changes are not announced; button presses are
  restart();

  // ---- Screenshot carousel buttons
  const shots = document.getElementById("shots");
  document.querySelectorAll(".carousel-nav [data-dir]").forEach((b) => b.addEventListener("click", () => {
    const item = shots.querySelector("li");
    shots.scrollBy({ left: Number(b.dataset.dir) * (item.getBoundingClientRect().width + 22), behavior: reduced ? "auto" : "smooth" });
  }));
})();
