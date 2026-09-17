/* Galería local — frontend. Habla con el backend por /api/*, sin plantillas. */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const els = {
    crumbs: $("crumbs"),
    folders: $("folders"),
    foldersSection: $("folders-section"),
    foldersTitle: $("folders-title"),
    grid: $("grid"),
    mediaSection: $("media-section"),
    mediaTitle: $("media-title"),
    state: $("state"),
    filter: $("filter"),
    zoom: $("zoom"),
    layout: $("layout"),
    theme: $("theme"),
    viewer: $("viewer"),
    stage: $("stage"),
    viewerName: $("viewer-name"),
    viewerCount: $("viewer-count"),
    viewerPrev: $("viewer-prev"),
    viewerNext: $("viewer-next"),
    viewerClose: $("viewer-close"),
    viewerDownload: $("viewer-download"),
  };

  const tpl = {
    folder: $("tpl-folder"),
    tile: $("tpl-tile"),
  };

  const state = {
    path: "",
    data: null,
    items: [],      // los visibles tras filtrar: lo que recorre el visor
    index: -1,
    config: { thumbnails: true, videoThumbnails: true, root: "" },
  };

  const store = {
    get(key, fallback) {
      try { const v = localStorage.getItem(key); return v === null ? fallback : v; }
      catch (_) { return fallback; }
    },
    set(key, value) { try { localStorage.setItem(key, value); } catch (_) {} },
  };

  const mediaURL = (path, download) =>
    "/media?p=" + encodeURIComponent(path) + (download ? "&dl=1" : "");
  const thumbURL = (path, size) =>
    "/api/thumb?p=" + encodeURIComponent(path) + "&s=" + (size || 360);

  const plural = (n, one, many) => n + " " + (n === 1 ? one : many);

  function humanSize(bytes) {
    const units = ["B", "kB", "MB", "GB"];
    let value = bytes, unit = 0;
    while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
    return (value < 10 && unit > 0 ? value.toFixed(1) : Math.round(value)) + " " + units[unit];
  }

  /* ------------------------------------------------------------ navegación */

  async function load(path, push) {
    setState("Leyendo la carpeta…");
    let data;
    try {
      const res = await fetch("/api/list?p=" + encodeURIComponent(path));
      data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error " + res.status);
    } catch (err) {
      setState("No se pudo leer esta carpeta: " + err.message);
      els.foldersSection.hidden = true;
      els.mediaSection.hidden = true;
      return;
    }

    state.path = data.path;
    state.data = data;
    document.title = (data.path || state.config.root || "Galería") + " — Galería";

    if (push !== false) {
      const url = data.path ? "?p=" + encodeURIComponent(data.path) : "/";
      history.pushState({ path: data.path }, "", url);
    }

    renderCrumbs(data.crumbs);
    render();
    window.scrollTo({ top: 0 });
  }

  function renderCrumbs(crumbs) {
    els.crumbs.textContent = "";
    crumbs.forEach((crumb, i) => {
      if (i > 0) {
        const sep = document.createElement("span");
        sep.className = "sep";
        sep.textContent = "/";
        els.crumbs.appendChild(sep);
      }
      const link = document.createElement("a");
      link.href = crumb.path ? "?p=" + encodeURIComponent(crumb.path) : "/";
      link.textContent = crumb.name;
      if (i === crumbs.length - 1) link.setAttribute("aria-current", "page");
      link.addEventListener("click", (ev) => { ev.preventDefault(); load(crumb.path); });
      els.crumbs.appendChild(link);
    });
  }

  /* ------------------------------------------------------------ pintado */

  function render() {
    const data = state.data;
    if (!data) return;

    const needle = els.filter.value.trim().toLowerCase();
    const folders = data.folders.filter((f) => !needle || f.name.toLowerCase().includes(needle));
    const items = data.items.filter((f) => !needle || f.name.toLowerCase().includes(needle));
    state.items = items;

    renderFolders(folders);
    renderGrid(items);

    if (!folders.length && !items.length) {
      setState(needle
        ? "Nada coincide con «" + els.filter.value.trim() + "» aquí."
        : "Esta carpeta no tiene imágenes, GIFs, vídeos ni subcarpetas.");
    } else {
      setState(null);
    }
  }

  function setState(message) {
    els.state.hidden = !message;
    els.state.textContent = message || "";
  }

  function renderFolders(folders) {
    els.folders.textContent = "";
    els.foldersSection.hidden = folders.length === 0;
    if (!folders.length) return;

    els.foldersTitle.textContent = plural(folders.length, "carpeta", "carpetas");

    const frag = document.createDocumentFragment();
    for (const folder of folders) {
      const node = tpl.folder.content.firstElementChild.cloneNode(true);
      node.href = "?p=" + encodeURIComponent(folder.path);
      node.querySelector(".folder-name").textContent = folder.name;
      node.title = folder.name;

      const parts = [];
      if (folder.media) {
        parts.push(folder.partial ? "más de " + folder.media + " archivos"
                                  : plural(folder.media, "archivo", "archivos"));
      }
      if (folder.subfolders) parts.push(plural(folder.subfolders, "carpeta", "carpetas"));
      node.querySelector(".folder-count").textContent = parts.join(", ") || "vacía";

      const mosaic = node.querySelector(".mosaic");
      mosaic.dataset.count = folder.thumbs.length;
      if (!folder.thumbs.length) {
        const empty = document.createElement("span");
        empty.className = "void";
        empty.textContent = folder.subfolders ? "Sólo subcarpetas" : "Sin vista previa";
        mosaic.appendChild(empty);
      } else {
        for (const thumb of folder.thumbs) {
          const img = document.createElement("img");
          img.loading = "lazy";
          img.decoding = "async";
          img.alt = "";
          img.src = thumbURL(thumb, 300);
          // Si no hay miniatura (p. ej. un vídeo sin ffmpeg) la celda queda vacía,
          // pero se conserva para que el mosaico no se descuadre.
          img.addEventListener("error", () => img.removeAttribute("src"), { once: true });
          mosaic.appendChild(img);
        }
      }

      node.addEventListener("click", (ev) => { ev.preventDefault(); load(folder.path); });
      frag.appendChild(node);
    }
    els.folders.appendChild(frag);
  }

  function renderGrid(items) {
    els.grid.textContent = "";
    els.mediaSection.hidden = items.length === 0;
    if (!items.length) return;

    const counts = items.reduce((acc, item) => (acc[item.kind]++, acc),
      { image: 0, gif: 0, video: 0 });
    const label = [];
    if (counts.image) label.push(plural(counts.image, "imagen", "imágenes"));
    if (counts.gif) label.push(counts.gif + " GIF");
    if (counts.video) label.push(plural(counts.video, "vídeo", "vídeos"));
    els.mediaTitle.textContent = label.join(", ");

    const size = Math.max(240, Math.round(parseInt(els.zoom.value, 10) * 1.6));
    const frag = document.createDocumentFragment();

    items.forEach((item, i) => {
      const node = tpl.tile.content.firstElementChild.cloneNode(true);
      const img = node.querySelector("img");
      const badge = node.querySelector(".badge");

      node.title = item.name + " · " + humanSize(item.size);
      node.setAttribute("aria-label", item.name);
      img.src = thumbURL(item.path, size);
      img.addEventListener("error", () => showFallback(node, img, item), { once: true });

      if (item.kind !== "image") {
        badge.hidden = false;
        badge.textContent = item.kind === "gif" ? "GIF" : "Vídeo";
      }

      if (item.kind === "gif") attachGifHover(node, img, item);
      if (item.kind === "video") attachVideoHover(node, item);

      node.addEventListener("click", () => open(i));
      frag.appendChild(node);
    });

    els.grid.appendChild(frag);
  }

  function showFallback(tile, img, item) {
    img.dataset.failed = "1";
    if (tile.querySelector(".fallback")) return;
    const box = document.createElement("span");
    box.className = "fallback";
    const name = document.createElement("strong");
    name.textContent = item.name;
    const hint = document.createElement("span");
    hint.textContent = item.kind === "video" ? "Vídeo · " + humanSize(item.size)
                                             : "Sin vista previa";
    box.append(name, hint);
    tile.appendChild(box);
  }

  // El GIF se anima al pasar por encima; en reposo se ve su primer fotograma.
  function attachGifHover(tile, img, item) {
    const still = img.src;
    let timer = null;
    tile.addEventListener("pointerenter", () => {
      timer = setTimeout(() => { img.src = mediaURL(item.path); }, 120);
    });
    tile.addEventListener("pointerleave", () => {
      clearTimeout(timer);
      img.src = still;
    });
  }

  // Vista previa del vídeo al pasar por encima, sin sonido.
  function attachVideoHover(tile, item) {
    let timer = null, video = null;
    tile.addEventListener("pointerenter", () => {
      timer = setTimeout(() => {
        if (video) return;
        video = document.createElement("video");
        video.src = mediaURL(item.path);
        video.muted = true;
        video.loop = true;
        video.playsInline = true;
        video.preload = "metadata";
        tile.appendChild(video);
        video.play().catch(() => {});
      }, 320);
    });
    tile.addEventListener("pointerleave", () => {
      clearTimeout(timer);
      if (video) { video.pause(); video.remove(); video = null; }
    });
  }

  /* ------------------------------------------------------------ visor */

  function open(index) {
    if (index < 0 || index >= state.items.length) return;
    state.index = index;
    const item = state.items[index];

    els.stage.textContent = "";
    els.viewerName.textContent = item.name;
    els.viewerCount.textContent = (index + 1) + " de " + state.items.length;
    els.viewerDownload.href = mediaURL(item.path, true);
    els.viewerPrev.disabled = index === 0;
    els.viewerNext.disabled = index === state.items.length - 1;

    if (item.kind === "video") {
      const video = document.createElement("video");
      video.src = mediaURL(item.path);
      video.controls = true;
      video.autoplay = true;
      video.playsInline = true;
      els.stage.appendChild(video);
    } else {
      const img = document.createElement("img");
      img.src = mediaURL(item.path);   // siempre el archivo completo, sin recomprimir
      img.alt = item.name;
      img.addEventListener("click", () => img.classList.toggle("actual"));
      els.stage.appendChild(img);
    }

    els.viewer.hidden = false;
    document.body.style.overflow = "hidden";
    els.viewerClose.focus({ preventScroll: true });
    preload(index + 1);
    preload(index - 1);
  }

  function preload(index) {
    const item = state.items[index];
    if (!item || item.kind === "video") return;
    new Image().src = mediaURL(item.path);
  }

  function close() {
    els.viewer.hidden = true;
    els.stage.textContent = "";  // corta la reproducción del vídeo
    document.body.style.overflow = "";
    state.index = -1;
  }

  const step = (delta) => open(state.index + delta);

  /* ------------------------------------------------------------ controles */

  function applyTile(value) {
    document.documentElement.style.setProperty("--tile", value + "px");
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    els.theme.textContent = theme === "light" ? "Tema oscuro" : "Tema claro";
  }

  function applyLayout(masonry) {
    els.grid.classList.toggle("masonry", masonry);
    els.layout.setAttribute("aria-pressed", String(masonry));
    els.layout.textContent = masonry ? "Cuadrícula" : "Mosaico";
  }

  els.filter.addEventListener("input", render);

  els.zoom.addEventListener("input", () => {
    applyTile(els.zoom.value);
    store.set("galeria.tile", els.zoom.value);
  });
  els.zoom.addEventListener("change", render);  // repide miniaturas a la nueva escala

  els.theme.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    applyTheme(next);
    store.set("galeria.theme", next);
  });

  els.layout.addEventListener("click", () => {
    const next = els.layout.getAttribute("aria-pressed") !== "true";
    applyLayout(next);
    store.set("galeria.masonry", String(next));
  });

  els.viewerClose.addEventListener("click", close);
  els.viewerPrev.addEventListener("click", () => step(-1));
  els.viewerNext.addEventListener("click", () => step(1));
  els.viewer.addEventListener("click", (ev) => {
    if (ev.target === els.viewer || ev.target === els.stage) close();
  });

  document.addEventListener("keydown", (ev) => {
    if (els.viewer.hidden) {
      if (ev.key === "/" && document.activeElement !== els.filter) {
        ev.preventDefault();
        els.filter.focus();
      } else if (ev.key === "Escape" && document.activeElement === els.filter) {
        els.filter.value = "";
        els.filter.blur();
        render();
      } else if (ev.key === "Backspace" && document.activeElement !== els.filter) {
        const crumbs = state.data && state.data.crumbs;
        if (crumbs && crumbs.length > 1) load(crumbs[crumbs.length - 2].path);
      }
      return;
    }
    if (ev.key === "Escape") close();
    else if (ev.key === "ArrowRight" || ev.key === " ") { ev.preventDefault(); step(1); }
    else if (ev.key === "ArrowLeft") step(-1);
    else if (ev.key === "Home") open(0);
    else if (ev.key === "End") open(state.items.length - 1);
  });

  window.addEventListener("popstate", (ev) => {
    close();
    const path = (ev.state && ev.state.path) || pathFromURL();
    load(path, false);
  });

  const pathFromURL = () => new URLSearchParams(location.search).get("p") || "";

  /* ------------------------------------------------------------ arranque */

  (async function start() {
    const saved = store.get("galeria.theme", null);
    applyTheme(saved || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));
    els.zoom.value = store.get("galeria.tile", "220");
    applyTile(els.zoom.value);
    applyLayout(store.get("galeria.masonry", "false") === "true");

    try {
      state.config = await (await fetch("/api/config")).json();
    } catch (_) { /* valores por defecto */ }

    await load(pathFromURL(), false);
    history.replaceState({ path: state.path }, "", location.href);
  })();
})();
