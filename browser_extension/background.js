const ENDPOINT = 'http://127.0.0.1:51234';

async function sendToLilith(data, pathOverride=null) {
  const {pairingKey} = await chrome.storage.local.get('pairingKey');
  if (!pairingKey) return {ok: false, error: 'Pair the extension first: paste Lilith’s pairing key in the popup.'};
  const path = pathOverride || (data.action === 'inspect' ? '/inspect' : '/add');
  try {
    const response = await fetch(ENDPOINT + path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Lilith-Token': pairingKey},
      body: JSON.stringify({
        url: data.url, title: data.title || '', mode: data.mode || 'Video page',
        filename: data.filename || '', referer: data.referer || ''
      }),
      signal: AbortSignal.timeout(11000)
    });
    let payload = {};
    try {payload = await response.json();} catch (_e) {}
    if (!response.ok) return {ok:false, error: payload.error || `Lilith returned HTTP ${response.status}.`};
    return {ok: true};
  } catch (_e) {
    return {ok: false, error: 'Lilith could not be reached. Keep it running in the Windows tray.'};
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== 'lilith-send') return;
  sendToLilith(message).then(sendResponse).catch(() => sendResponse({ok:false,error:'Lilith is unavailable.'}));
  return true;
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id:'lilith-link', title:'Download link with Lilith (direct file)', contexts:['link'],
    documentUrlPatterns:['http://*/*','https://*/*']
  });
  chrome.contextMenus.create({
    id:'lilith-page', title:'Download video page with Lilith', contexts:['page','video'],
    documentUrlPatterns:['http://*/*','https://*/*']
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const url = info.linkUrl || info.pageUrl || tab?.url;
  if (!url || !/^https?:\/\//i.test(url)) return;
  const direct = info.menuItemId === 'lilith-link';
  const reply = await sendToLilith({url, title:direct ? '' : (tab?.title || ''),
                                    mode:direct ? 'Direct file' : 'Video page', action:'add',
                                    referer:direct ? (info.pageUrl || tab?.url || '') : ''});
  if (!reply.ok) await chrome.storage.local.set({lastCaptureStatus:`Manual send failed: ${reply.error}`});
});

// Opt-in takeover for actual Chrome downloads.
// Pause Chrome first. Only if Lilith's server confirms unauthenticated file access
// and queues the URL do we cancel the Chrome transfer. If not, Chrome resumes.
const handling = new Set();
chrome.downloads.onCreated.addListener(async item => {
  if (!item || handling.has(item.id) || item.state !== 'in_progress') return;
  if (item.byExtensionId === chrome.runtime.id) return;
  const {autoCaptureDownloads=false} = await chrome.storage.local.get('autoCaptureDownloads');
  if (!autoCaptureDownloads) return;
  const url = item.finalUrl || item.url;
  if (!url || !/^https?:\/\//i.test(url)) return; // blob:, data:, file:, etc stay with Chrome
  handling.add(item.id);
  let paused = false;
  try {
    // Chrome may finish a very small file before we have time to pause.
    await chrome.downloads.pause(item.id);
    paused = true;
    const reply = await sendToLilith({
      url, title:'', mode:'Direct file', action:'handoff', filename:item.filename || '',
      referer:item.referrer || ''
    }, '/handoff');
    if (!reply.ok) {
      await chrome.storage.local.set({lastCaptureStatus:`Chrome kept the download: ${reply.error}`});
      return;
    }
    // The local downloader has acknowledged and queued the file.
    await chrome.downloads.cancel(item.id);
    paused = false;
    await chrome.storage.local.set({lastCaptureStatus:'Lilith took over a Chrome download ♡'});
  } catch (err) {
    await chrome.storage.local.set({lastCaptureStatus:`Chrome kept the download: ${String(err).slice(0,130)}`});
  } finally {
    if (paused) {
      try {await chrome.downloads.resume(item.id);} catch (_e) {}
    }
    handling.delete(item.id);
  }
});
