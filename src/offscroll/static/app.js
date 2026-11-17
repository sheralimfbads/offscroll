/* Progressive reading tools. No analytics, remote API calls or copied source data. */
(() => {
  "use strict";
  const key = "offscroll.preferences.v1";
  const ttl = 30 * 24 * 60 * 60 * 1000;
  const now = Date.now();
  const cards = [...document.querySelectorAll(".story[data-key]")];
  let preferences = { items: Object.create(null), theme: null };
  let storageAvailable = true;
  let hadPreferences = false;
  try {
    const saved = JSON.parse(localStorage.getItem(key) || "null");
    if (saved && typeof saved === "object") {
      hadPreferences = true;
      if (saved.theme === "light" || saved.theme === "dark")
        preferences.theme = saved.theme;
      if (saved.items && typeof saved.items === "object") {
        for (const [id, state] of Object.entries(saved.items).slice(-500)) {
          if (
            state &&
            Number.isFinite(state.at) &&
            now - state.at < ttl &&
            state.at <= now
          ) {
            preferences.items[id] = {
              saved: state.saved === true,
              read: state.read === true,
              at: state.at,
            };
          }
        }
      }
    }
  } catch {
    storageAvailable = false;
  }
  const announce = (text) => {
    document.querySelector(".reader-status").textContent = text;
  };
  const storageMessage = document.querySelector(".storage-status");
  function persist() {
    try {
      localStorage.setItem(key, JSON.stringify(preferences));
    } catch {
      storageAvailable = false;
    }
    if (!storageAvailable)
      storageMessage.textContent =
        "Browser storage is unavailable. Choices work for this visit only.";
  }
  let view = "all";
  function update() {
    let saved = 0;
    let read = 0;
    for (const card of cards) {
      const state = preferences.items[card.dataset.key] || {};
      saved += state.saved ? 1 : 0;
      read += state.read ? 1 : 0;
      card.hidden = view === "saved" && !state.saved;
      card.classList.toggle("is-read", !!state.read);
      const saveButton = card.querySelector(".save-button");
      saveButton.setAttribute("aria-pressed", String(!!state.saved));
      saveButton.textContent = state.saved ? "Saved ✓" : "Save";
      const readButton = card.querySelector(".read-button");
      readButton.setAttribute("aria-pressed", String(!!state.read));
      readButton.textContent = state.read ? "Read ✓" : "Mark read";
    }
    document.querySelector("[data-saved-count]").textContent = String(saved);
    document.querySelector("[data-progress]").textContent =
      `${read} of ${cards.length} marked as read`;
    document.querySelector("progress").value = read;
    for (const lane of document.querySelectorAll(".lane")) {
      lane.querySelector(".saved-empty").hidden =
        view !== "saved" || !!lane.querySelector(".story:not([hidden])");
      const empty = lane.querySelector(".empty");
      if (empty) empty.hidden = view === "saved";
    }
    for (const button of document.querySelectorAll("[data-view]")) {
      button.setAttribute("aria-pressed", String(button.dataset.view === view));
    }
  }
  for (const card of cards) {
    for (const [selector, field] of [
      [".save-button", "saved"],
      [".read-button", "read"],
    ]) {
      card.querySelector(selector).addEventListener("click", () => {
        const state = preferences.items[card.dataset.key] || {
          saved: false,
          read: false,
        };
        preferences.items[card.dataset.key] = {
          ...state,
          [field]: !state[field],
          at: Date.now(),
        };
        persist();
        update();
        announce(
          field === "saved"
            ? state.saved
              ? "Selection removed from saved."
              : "Selection saved in this browser."
            : state.read
              ? "Selection marked unread."
              : "Selection marked as read.",
        );
        if (card.hidden) document.querySelector('[data-view="saved"]').focus();
      });
    }
  }
  for (const button of document.querySelectorAll("[data-view]")) {
    button.addEventListener("click", () => {
      view = button.dataset.view;
      update();
      announce(
        view === "saved"
          ? "Showing saved selections from this edition."
          : "Showing all selections.",
      );
    });
  }
  const themeButton = document.querySelector(".theme-button");
  function applyTheme() {
    const dark =
      preferences.theme === "dark" ||
      (!preferences.theme &&
        matchMedia("(prefers-color-scheme: dark)").matches);
    if (preferences.theme)
      document.documentElement.dataset.theme = preferences.theme;
    else delete document.documentElement.dataset.theme;
    themeButton.setAttribute(
      "aria-label",
      `Switch to ${dark ? "light" : "dark"} appearance`,
    );
  }
  themeButton.addEventListener("click", () => {
    preferences.theme = themeButton.getAttribute("aria-label").includes("dark")
      ? "dark"
      : "light";
    applyTheme();
    persist();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener(
    "change",
    applyTheme,
  );
  document.querySelector(".clear-data").addEventListener("click", () => {
    preferences = { items: Object.create(null), theme: null };
    try {
      localStorage.removeItem(key);
    } catch {
      storageAvailable = false;
    }
    view = "all";
    update();
    applyTheme();
    storageMessage.textContent =
      "Your saved selections, read marks and appearance preference have been cleared.";
    announce("Local preferences cleared.");
  });
  for (const frame of document.querySelectorAll("[data-video]")) {
    frame.querySelector(".load-video").addEventListener("click", () => {
      const id = frame.dataset.video;
      if (!/^[A-Za-z0-9_-]{11}$/.test(id)) return;
      if (!["https:", "http:"].includes(location.protocol)) {
        announce(
          "Use the direct YouTube link, or open Offscroll through its web address to use the player.",
        );
        return;
      }
      const iframe = document.createElement("iframe");
      iframe.src = `https://www.youtube-nocookie.com/embed/${id}?playsinline=1`;
      iframe.title = "YouTube video player";
      iframe.allow = "encrypted-media; fullscreen; picture-in-picture";
      iframe.allowFullscreen = true;
      iframe.referrerPolicy = "strict-origin-when-cross-origin";
      frame.replaceChildren(iframe);
      iframe.focus();
      announce("YouTube player loaded. Press play in the player to watch.");
    });
  }
  const edition = document.querySelector("[data-edition-time]");
  if (edition && now - Date.parse(edition.dateTime) > 4 * 86400000)
    document.querySelector(".freshness-notice").hidden = false;
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries)
          if (entry.isIntersecting) {
            for (const link of document.querySelectorAll(".lane-nav a"))
              link.classList.toggle(
                "active",
                link.hash === `#${entry.target.id}`,
              );
          }
      },
      { rootMargin: "-10% 0px -60% 0px" },
    );
    document
      .querySelectorAll(".lane")
      .forEach((lane) => observer.observe(lane));
  }
  applyTheme();
  update();
  // Clean up previously chosen preferences; first-time visits store nothing.
  if (hadPreferences) persist();
  if (!storageAvailable)
    storageMessage.textContent =
      "Browser storage is unavailable. Choices work for this visit only.";
  document.querySelectorAll(".enhanced").forEach((element) => {
    element.hidden = false;
  });
})();
