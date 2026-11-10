const statusEl = document.getElementById('status');
const pair = document.getElementById('pair');

chrome.storage.local.get('pairingKey', ({pairingKey}) => {
  if (pairingKey) { pair.value = pairingKey; statusEl.textContent = 'Paired. Open a video and click the floating Lilith button ♡'; }
});

document.getElementById('save').addEventListener('click', async () => {
  const value = pair.value.trim();
  if (!value) { statusEl.textContent = 'Paste the pairing key first.'; return; }
  await chrome.storage.local.set({ pairingKey: value });
  statusEl.textContent = 'Pairing key saved locally in this browser.';
});

async function send(action) {
  statusEl.textContent = 'Connecting to Lilith…';
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url || !/^https?:\/\//i.test(tab.url)) {
    statusEl.textContent = 'Open a regular website tab first.';
    return;
  }
  try {
    const reply = await chrome.runtime.sendMessage({
      type: 'lilith-send', action, url: tab.url, title: tab.title || '',
      mode: document.getElementById('mode').value
    });
    statusEl.textContent = reply?.ok ? (action === 'inspect' ? 'Quality picker opened in Lilith ♡' : 'Sent to Lilith ♡')
                                    : (reply?.error || 'Unable to connect.');
  } catch (error) { statusEl.textContent = 'Unable to contact extension service worker.'; }
}

document.getElementById('send').addEventListener('click', () => send('add'));
document.getElementById('inspect').addEventListener('click', () => send('inspect'));

const autoBox = document.getElementById('autoCapture');
chrome.storage.local.get({autoCaptureDownloads:false,lastCaptureStatus:''}, ({autoCaptureDownloads,lastCaptureStatus}) => {
  autoBox.checked = Boolean(autoCaptureDownloads);
  document.getElementById('captureStatus').textContent = lastCaptureStatus || 'Chrome auto-capture is initially disabled.';
});
autoBox.addEventListener('change', async () => {
  await chrome.storage.local.set({autoCaptureDownloads:autoBox.checked});
  statusEl.textContent = autoBox.checked
    ? 'Auto-capture enabled. Chrome will pause and offer new downloads to Lilith.'
    : 'Auto-capture disabled. Chrome downloads normally.';
});
