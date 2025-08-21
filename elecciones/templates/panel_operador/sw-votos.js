/* sw-votos.js (scope raíz '/') */
const DB = 'votos-offline';
const STORE = 'queue';

function openDB(){
  return new Promise((res, rej)=>{
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
}
async function qAll(){ const db=await openDB(); return new Promise(ok=>{ const tx=db.transaction(STORE,'readonly'); const g=tx.objectStore(STORE).getAll(); g.onsuccess=()=>ok(g.result||[]); }); }
async function qPut(rec){ const db=await openDB(); return new Promise(ok=>{ const tx=db.transaction(STORE,'readwrite'); tx.objectStore(STORE).put(rec); tx.oncomplete=ok; }); }
async function qDel(id){ const db=await openDB(); return new Promise(ok=>{ const tx=db.transaction(STORE,'readwrite'); tx.objectStore(STORE).delete(id); tx.oncomplete=ok; }); }

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

async function trySend(item){
  const res = await fetch('/operador/guardar-votos/', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...(item.csrf ? { 'X-CSRFToken': item.csrf } : {})
    },
    body: JSON.stringify(item.payload)
  });
  const data = await res.json().catch(()=>({}));
  return { ok: res.ok && data.status==='ok', status: res.status, data };
}

async function drain(){
  const items = await qAll();
  for (const it of items.filter(x => x.status==='pending')) {
    try {
      const r = await trySend(it);
      if (r.ok) {
        await qDel(it.id);
      } else if (r.status === 409) {
        // pedir confirmación al cliente
        const clis = await self.clients.matchAll({ includeUncontrolled: true, type: 'window' });
        clis.forEach(c => c.postMessage({ type:'NEEDS_CONFIRM', id: it.id, message: r.data?.message || 'La mesa ya fue escrutada. ¿Sobrescribir?' }));
        await qPut({ ...it, status:'needs_confirm' });
      } else if (r.status === 403) {
        await qPut({ ...it, status:'blocked_auth' });
      } else {
        await qPut({ ...it, status:'error_last_try', lastStatus: r.status });
      }
    } catch (e) {
      // sigue pending, se reintentará luego
    }
  }
}

self.addEventListener('sync', e => { if (e.tag==='send-votos') e.waitUntil(drain()); });
self.addEventListener('message', e => {
  if (e.data?.type === 'DRAIN_NOW') e.waitUntil(drain());
});
