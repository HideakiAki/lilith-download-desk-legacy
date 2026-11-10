(() => {
  if (window.__lilithVideoToolbarInstalled) return;
  window.__lilithVideoToolbarInstalled = true;

  let active = null;
  const bar = document.createElement('div');
  bar.id = 'lilith-video-toolbar';
  bar.innerHTML = `
    <button class="lilith-toggle" type="button" title="Send video to Lilith Download Desk">✦ Download with Lilith ♡</button>
    <div class="lilith-menu">
      <button class="lilith-download" type="button">⬇ Download this video</button>
      <button class="lilith-inspect" type="button">▣ Choose quality in Lilith…</button>
      <div class="lilith-result">Ready ♡</div>
    </div>`;
  document.documentElement.appendChild(bar);
  const menu = bar.querySelector('.lilith-menu');
  const result = bar.querySelector('.lilith-result');
  bar.querySelector('.lilith-toggle').addEventListener('click', (ev) => {
    if (!ev.isTrusted) return;
    ev.preventDefault(); ev.stopPropagation();
    menu.classList.toggle('visible');
  });

  function send(action) {
    result.textContent = 'Sending to Lilith…';
    chrome.runtime.sendMessage({
      type:'lilith-send', action, url: location.href,
      title: document.title || '', mode: 'Video page'
    }, reply => {
      if (chrome.runtime.lastError) {
        result.textContent = 'Open the extension popup to connect Lilith first.';
      } else {
        result.textContent = reply?.ok
          ? (action === 'inspect' ? 'Lilith is showing available qualities ♡' : 'Added to downloads ♡')
          : (reply?.error || 'Unable to contact Lilith.');
      }
    });
  }
  bar.querySelector('.lilith-download').addEventListener('click', ev => { if (!ev.isTrusted) return; ev.stopPropagation(); send('add'); });
  bar.querySelector('.lilith-inspect').addEventListener('click', ev => { if (!ev.isTrusted) return; ev.stopPropagation(); send('inspect'); });
  document.addEventListener('click', ev => { if (!bar.contains(ev.target)) menu.classList.remove('visible'); }, true);

  function visibleVideo() {
    let chosen = null;
    let largest = 0;
    for (const video of document.querySelectorAll('video')) {
      const box = video.getBoundingClientRect();
      const width = Math.min(box.right, window.innerWidth) - Math.max(box.left, 0);
      const height = Math.min(box.bottom, window.innerHeight) - Math.max(box.top, 0);
      const area = Math.max(width, 0) * Math.max(height, 0);
      if (area < 45000 || box.width < 230 || box.height < 145) continue;
      if (getComputedStyle(video).visibility === 'hidden') continue;
      if (area > largest) { largest = area; chosen = {video, box}; }
    }
    return chosen;
  }

  function position() {
    if (!document.documentElement.contains(bar)) document.documentElement.appendChild(bar);
    const candidate = visibleVideo();
    if (!candidate) { bar.style.display = 'none'; menu.classList.remove('visible'); active = null; return; }
    if (candidate.video !== active) {
      menu.classList.remove('visible'); result.textContent = 'Ready ♡';
      active = candidate.video;
    }
    const box = candidate.box;
    const width = Math.min(240, Math.max(145, box.width - 28));
    bar.style.display = 'block';
    bar.style.right = `${Math.max(8, window.innerWidth - box.right + 12)}px`;
    bar.style.left = 'auto';
    bar.style.top = `${Math.max(8, box.top + 10)}px`;
    bar.style.maxWidth = `${width}px`;
  }
  window.addEventListener('resize', position, {passive: true});
  window.addEventListener('scroll', position, {passive: true});
  document.addEventListener('fullscreenchange', position);
  setInterval(position, 1200);
  position();
})();
