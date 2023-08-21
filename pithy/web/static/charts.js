"use strict";

console.log('charts.js');

function chartsLinkScrollX(visGrid) {
  let activeDiv = null;
  const visScroll = visGrid.querySelector('.vis-scroll');
  const ticksXScroll = visGrid.querySelector('.ticks-x-scroll');
  console.assert(visScroll);
  console.assert(ticksXScroll);
  function link(div, other) {
    div.addEventListener('mouseenter', (e) => {
      activeDiv = e.target;
    });
    div.addEventListener("scroll", (e) => {
      if (e.target !== activeDiv) return;
      other.scrollLeft = e.target.scrollLeft;
    });
  }

  link(visScroll, ticksXScroll);
  link(ticksXScroll, visScroll);
}
