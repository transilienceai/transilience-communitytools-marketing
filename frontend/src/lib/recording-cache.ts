const DB_NAME = "screen_recordings";
const STORE_NAME = "recordings";
const MAX_ENTRIES = 5;

export interface CachedRecording {
  id: string;
  name: string;
  blob: Blob;
  timestamp: number;
  duration: number;
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function saveRecording(file: File, duration: number): Promise<void> {
  const db = await openDB();
  const id = `rec_${Date.now()}`;
  const blob = new Blob([await file.arrayBuffer()], { type: file.type });

  const entry: CachedRecording = {
    id,
    name: file.name,
    blob,
    timestamp: Date.now(),
    duration,
  };

  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).put(entry);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });

  // Prune old entries beyond MAX_ENTRIES
  const all = await getRecordings();
  if (all.length > MAX_ENTRIES) {
    const toDelete = all.slice(MAX_ENTRIES);
    const tx = db.transaction(STORE_NAME, "readwrite");
    for (const rec of toDelete) {
      tx.objectStore(STORE_NAME).delete(rec.id);
    }
  }
}

export async function getRecordings(): Promise<CachedRecording[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const req = tx.objectStore(STORE_NAME).getAll();
    req.onsuccess = () => {
      const results = (req.result as CachedRecording[]).sort(
        (a, b) => b.timestamp - a.timestamp
      );
      resolve(results);
    };
    req.onerror = () => reject(req.error);
  });
}

export async function deleteRecording(id: string): Promise<void> {
  const db = await openDB();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
