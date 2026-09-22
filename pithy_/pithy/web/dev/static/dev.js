// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'use strict';

// Opt in before the first paint; initTheme connects the selector when the document is ready.
initTheme();

addEventListener('DOMContentLoaded', () => {
  const currentPath = window.location.pathname;
  const currentLink = [...document.querySelectorAll('body > nav a')]
    .find(link => link instanceof HTMLAnchorElement && link.pathname === currentPath);
  if (currentLink) currentLink.classList.add('current-nav-section-link');
});
