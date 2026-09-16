/**
 * RESQ Operations Console - UX Shell Controller
 *
 * Lightweight presentation-only view switcher and layout manager.
 * Manages tab switching between the four primary operational views:
 *   - Operations (#operations)
 *   - Governance (#governance)
 *   - Backlog (#backlog)
 *   - Safety (#safety)
 *
 * Adheres strictly to non-mutation:
 * Does NOT alter data fetching, API contracts, or existing business logic in app.js.
 */

(function () {
  "use strict";

  const VIEW_MAP = {
    "#operations": "view-operations",
    "#governance": "view-governance",
    "#backlog": "view-backlog",
    "#safety": "view-safety",
  };

  const DEFAULT_HASH = "#operations";

  function switchView(targetHash) {
    const viewId = VIEW_MAP[targetHash] || VIEW_MAP[DEFAULT_HASH];
    const cleanHash = Object.keys(VIEW_MAP).find((k) => VIEW_MAP[k] === viewId) || DEFAULT_HASH;

    // 1. Update Navigation items
    const navItems = document.querySelectorAll(".nav-item");
    navItems.forEach((item) => {
      const target = item.getAttribute("data-target");
      if (target === viewId) {
        item.classList.add("active");
        item.setAttribute("aria-selected", "true");
      } else {
        item.classList.remove("active");
        item.setAttribute("aria-selected", "false");
      }
    });

    // 2. Update View containers
    const views = document.querySelectorAll(".console-view");
    views.forEach((view) => {
      if (view.id === viewId) {
        view.classList.add("active");
        view.removeAttribute("hidden");
      } else {
        view.classList.remove("active");
        view.setAttribute("hidden", "true");
      }
    });

    // 3. Reset scroll position on workspace
    const workspace = document.querySelector(".app-workspace");
    if (workspace) {
      workspace.scrollTop = 0;
    }

    // 4. Update history / hash cleanly without triggering extra jumps
    if (window.location.hash !== cleanHash) {
      history.replaceState(null, "", cleanHash);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    // Attach click listeners to sidebar navigation items
    const navItems = document.querySelectorAll(".nav-item");
    navItems.forEach((item) => {
      item.addEventListener("click", (e) => {
        e.preventDefault();
        const target = item.getAttribute("data-target");
        const hash = Object.keys(VIEW_MAP).find((k) => VIEW_MAP[k] === target);
        if (hash) {
          switchView(hash);
        }
      });
    });

    // Listen for browser back/forward navigation
    window.addEventListener("hashchange", () => {
      const currentHash = window.location.hash.toLowerCase();
      if (VIEW_MAP[currentHash]) {
        switchView(currentHash);
      }
    });

    // Initialize initial view from current URL hash
    const initialHash = window.location.hash.toLowerCase();
    switchView(VIEW_MAP[initialHash] ? initialHash : DEFAULT_HASH);
  });
})();
