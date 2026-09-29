// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

/*
Resolve every palette variable inside each themed sample and check the declared foreground/background pairs with APCA.
Also check adjacent background surfaces and table shades for OKLCH lightness separation.
Nothing depends on this at runtime; the stylesheet records the tuned values.
*/

'use strict';

/** @typedef {[number, number, number]} RGB */
/** @typedef {{computed:string, rgb:RGB|null}} ResolvedColor */

// APCA (Accessible Perceptual Contrast Algorithm), ported from the constants and formulas of the reference implementation
// at https://github.com/Myndex/apca-w3. Up to date with version 0.1.9 (base algorithm 0.0.98G-4g) as of 2026-09-29.
// The reference license permits the name only for a correct and current implementation; recheck it when the reference changes.
const apcaVersion = '0.1.9 (base algorithm 0.0.98G-4g), current as of 2026-09-29';

const apcaConstants = {
  blkThrs: 0.022, blkClmp: 1.414, deltaYmin: 0.0005, loClip: 0.1,
  normBG: 0.56, normTXT: 0.57, revTXT: 0.62, revBG: 0.65,
  scale: 1.14, offset: 0.027,
};

/** @param {RGB} rgb 8-bit sRGB components. */
function srgbToY([r, g, b]) {
  const lin = (c) => (c / 255) ** 2.4;
  return 0.2126729 * lin(r) + 0.7151522 * lin(g) + 0.0721750 * lin(b);
}

/**
 * APCA lightness contrast Lc between text and background colors.
 * Positive for dark text on a light background, negative for light text on dark.
 * @param {RGB} textRgb
 * @param {RGB} bgRgb
 */
function apcaContrast(textRgb, bgRgb) {
  const c = apcaConstants;
  let txtY = srgbToY(textRgb);
  let bgY = srgbToY(bgRgb);
  if (txtY <= c.blkThrs) txtY += (c.blkThrs - txtY) ** c.blkClmp;
  if (bgY <= c.blkThrs) bgY += (c.blkThrs - bgY) ** c.blkClmp;
  if (Math.abs(bgY - txtY) < c.deltaYmin) return 0;
  if (bgY > txtY) {
    const sapc = (bgY ** c.normBG - txtY ** c.normTXT) * c.scale;
    return sapc < c.loClip ? 0 : (sapc - c.offset) * 100;
  }
  const sapc = (bgY ** c.revBG - txtY ** c.revTXT) * c.scale;
  return sapc > -c.loClip ? 0 : (sapc + c.offset) * 100;
}

/** The sRGB transfer function, from an 8-bit component to linear light. */
function srgbToLinear(c) {
  const v = c / 255;
  return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}

/**
 * OKLab/OKLCH lightness L on the 0-1 scale, from https://bottosson.github.io/posts/oklab/.
 * @param {RGB} rgb 8-bit sRGB components.
 */
function srgbToOklabL(rgb) {
  const r = srgbToLinear(rgb[0]);
  const g = srgbToLinear(rgb[1]);
  const b = srgbToLinear(rgb[2]);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s;
}

const canvas = document.createElement('canvas');
canvas.width = 1;
canvas.height = 1;
const ctx = reqInstance(canvas.getContext('2d', {willReadFrequently: true}), CanvasRenderingContext2D);

/**
 * Parse a computed color string to 8-bit sRGB components, or null if it is not opaque or not parsable.
 * @param {string} computed
 * @returns {RGB|null}
 */
function parseColor(computed) {
  ctx.clearRect(0, 0, 1, 1);
  ctx.fillStyle = 'rgb(0 0 0 / 0)'; // Sentinel: an unparsable value leaves the previous fill style in place.
  ctx.fillStyle = computed;
  ctx.fillRect(0, 0, 1, 1);
  const data = ctx.getImageData(0, 0, 1, 1).data;
  return (data[3] === 255) ? pixelRgb(data) : null;
}

/**
 * Composite a possibly translucent computed color over an opaque base, as the browser does for a tint on a surface.
 * @param {string} computed
 * @param {RGB} baseRgb
 * @returns {RGB|null} 8-bit sRGB components, or null if the color is not parsable or is fully transparent.
 */
function compositeColor(computed, baseRgb) {
  ctx.clearRect(0, 0, 1, 1);
  ctx.fillStyle = `rgb(${baseRgb.join(' ')})`;
  ctx.fillRect(0, 0, 1, 1);
  ctx.fillStyle = 'rgb(0 0 0 / 0)';
  const sentinel = ctx.fillStyle; // An unparsable value leaves this serialized sentinel in place.
  ctx.fillStyle = computed;
  if (ctx.fillStyle === sentinel) return null;
  ctx.fillRect(0, 0, 1, 1);
  return pixelRgb(ctx.getImageData(0, 0, 1, 1).data);
}

/**
 * Resolve a CSS variable within `container` to its computed color string and 8-bit sRGB components.
 * The probe inherits the container's mode parameters and color scheme, so light-dark() and the mixes resolve for it.
 * @param {Element} container
 * @param {string} token
 * @returns {ResolvedColor}
 */
function resolveToken(container, token) {
  const probe = document.createElement('span');
  probe.style.color = `var(--${token})`;
  container.append(probe);
  const computed = getComputedStyle(probe).color;
  probe.remove();
  return {computed, rgb: parseColor(computed)};
}

/** @param {RGB} rgb */
function hex(rgb) {
  return '#' + rgb.map((c) => c.toString(16).padStart(2, '0').toUpperCase()).join('');
}

/**
 * Show a warning icon in `el` for a value that this browser could not resolve; `detail` becomes the tooltip.
 * The icon keeps the table columns narrow, where the raw computed string or a word would widen them.
 * @param {Element} el
 * @param {string} detail
 */
function setUnresolved(el, detail) {
  const icon = document.createElement('span');
  icon.className = 'icon color-unresolved';
  icon.textContent = '\u26A0'; // Warning sign. No U+FE0F, so that the Noto Emoji icon font applies.
  icon.title = detail;
  icon.setAttribute('role', 'img');
  icon.setAttribute('aria-label', detail);
  el.replaceChildren(icon);
}

/**
 * Show a resolved color in `el` as hex, or the warning icon if it did not resolve.
 * @param {Element} el
 * @param {ResolvedColor} color
 */
function setColorValue(el, color) {
  if (color.rgb) el.textContent = hex(color.rgb);
  else setUnresolved(el, `Unresolved: ${color.computed}`);
}

for (const el of document.querySelectorAll('.apca-version')) el.textContent = apcaVersion;

/**
 * A memoizing resolver for the tokens of one themed container.
 * @param {Element} container
 * @returns {(token:string|undefined) => ResolvedColor}
 */
function makeResolver(container) {
  /** @type {Map<string, ResolvedColor>} */
  const cache = new Map();
  return (token) => {
    if (!token) throw new Error('Missing color token.');
    let color = cache.get(token);
    if (!color) {
      color = resolveToken(container, token);
      cache.set(token, color);
    }
    return color;
  };
}

// Palette listing: show each variable's resolved value in its themed column.
for (const container of document.querySelectorAll('.color-scheme')) {
  const resolve = makeResolver(container);
  for (const el of container.querySelectorAll('.color-value')) {
    const value = reqInstance(el, HTMLElement);
    const {computed, rgb} = resolve(value.dataset.colorToken);
    value.textContent = rgb ? `${hex(rgb)} ${computed}` : computed;
  }
}

// Foreground/background pairs: each must meet its APCA target.
for (const container of document.querySelectorAll('.color-pairs')) {
  const resolve = makeResolver(container);
  let failures = 0;
  let checked = 0;
  for (const el of container.querySelectorAll('.color-contrast tr[data-fg]')) {
    const row = reqInstance(el, HTMLTableRowElement);
    const fg = resolve(row.dataset.fg);
    const bg = resolve(row.dataset.bg);
    setColorValue(findSel('.color-fg-value', row), fg);
    setColorValue(findSel('.color-bg-value', row), bg);
    const lcEl = findSel('.color-lc', row);
    if (!fg.rgb || !bg.rgb) {
      setUnresolved(lcEl, 'Unresolved: this browser could not convert one of the colors to sRGB.');
      row.classList.add('fail');
      failures += 1;
      continue;
    }
    const lc = apcaContrast(fg.rgb, bg.rgb);
    lcEl.textContent = lc.toFixed(1);
    if (!row.dataset.target) continue;
    const target = Number(row.dataset.target);
    checked += 1;
    const ok = Math.abs(lc) >= target;
    row.classList.add(ok ? 'pass' : 'fail');
    if (!ok) failures += 1;
  }
  const summary = findSel('.color-summary', container);
  summary.textContent = failures
    ? `${failures} of ${checked} checked pairs miss their target.`
    : `All ${checked} checked pairs meet their targets.`;
  summary.classList.toggle('fail', failures > 0);
}

// Adjacent tone steps: each pair must clear the OKLCH delta L threshold set on the table.
for (const container of document.querySelectorAll('.color-steps')) {
  const resolve = makeResolver(container);
  const canvasRgb = resolve('bg').rgb;
  // A translucent tint does not resolve to an opaque color on its own; composite it over the canvas.
  const resolveOnCanvas = (token) => {
    const {computed, rgb} = resolve(token);
    return {computed, rgb: rgb || (canvasRgb && compositeColor(computed, canvasRgb))};
  };
  const table = reqInstance(findSel('.color-surface-steps', container), HTMLTableElement);
  const minDeltaL = Number(table.dataset.minDeltaL);
  let failures = 0;
  let checked = 0;
  for (const el of table.querySelectorAll('tr[data-lower]')) {
    const row = reqInstance(el, HTMLTableRowElement);
    const lower = resolveOnCanvas(row.dataset.lower);
    const upper = resolveOnCanvas(row.dataset.upper);
    setColorValue(findSel('.color-lower-value', row), lower);
    setColorValue(findSel('.color-upper-value', row), upper);
    const deltaEl = findSel('.color-delta-l', row);
    checked += 1;
    if (!lower.rgb || !upper.rgb) {
      setUnresolved(deltaEl, 'Unresolved: this browser could not convert one of the colors to sRGB.');
      row.classList.add('fail');
      failures += 1;
      continue;
    }
    const lowerL = srgbToOklabL(lower.rgb);
    const upperL = srgbToOklabL(upper.rgb);
    findSel('.color-lower-l', row).textContent = lowerL.toFixed(3);
    findSel('.color-upper-l', row).textContent = upperL.toFixed(3);
    // Judge the value at its displayed precision, so that the verdict agrees with the shown number.
    const deltaText = Math.abs(upperL - lowerL).toFixed(3);
    deltaEl.textContent = deltaText;
    const ok = Number(deltaText) >= minDeltaL;
    deltaEl.classList.add(ok ? 'pass' : 'fail');
    row.classList.add(ok ? 'pass' : 'fail');
    if (!ok) failures += 1;
  }
  const summary = findSel('.color-summary', container);
  summary.textContent = failures
    ? `${failures} of ${checked} adjacent pairs fall below the threshold.`
    : `All ${checked} adjacent pairs clear the threshold.`;
  summary.classList.toggle('fail', failures > 0);
}


/**
 * Read the RGB channels of one canvas pixel.
 * @param {Uint8ClampedArray} data
 * @returns {RGB}
 */
function pixelRgb(data) {
  const [r, g, b] = data;
  if (r === undefined || g === undefined || b === undefined) throw new Error('Missing canvas pixel channels.');
  return [r, g, b];
}
