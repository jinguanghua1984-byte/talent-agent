// idb.js — IndexedDB 存储工具
// 用于分页联系人和批量详情结果存储，替代 chrome.storage.local 的 5MB 限制

function createIndexedDbClient(dbName, version, stores) {
  var _db = null;

  function open() {
    if (_db) return Promise.resolve(_db);
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(dbName, version);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        stores.forEach(function (storeDef) {
          if (!db.objectStoreNames.contains(storeDef.name)) {
            db.createObjectStore(storeDef.name, { keyPath: storeDef.keyPath });
          }
        });
      };
      req.onsuccess = function (e) {
        _db = e.target.result;
        resolve(_db);
      };
      req.onerror = function (e) { reject(e.target.error); };
    });
  }

  function store(db, name, mode) {
    return db.transaction(name, mode).objectStore(name);
  }

  function putMany(storeName, records) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var objectStore = store(db, storeName, "readwrite");
        var count = 0;
        (records || []).forEach(function (record) {
          if (!record) return;
          var req = objectStore.put(record);
          req.onsuccess = function () { count++; };
        });
        objectStore.transaction.oncomplete = function () { resolve(count); };
        objectStore.transaction.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function getOne(storeName, key) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var req = store(db, storeName, "readonly").get(key);
        req.onsuccess = function () { resolve(req.result || null); };
        req.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function getAll(storeName) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var req = store(db, storeName, "readonly").getAll();
        req.onsuccess = function () { resolve(req.result || []); };
        req.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function count(storeName) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var req = store(db, storeName, "readonly").count();
        req.onsuccess = function () { resolve(req.result || 0); };
        req.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function clearStore(storeName) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var req = store(db, storeName, "readwrite").clear();
        req.onsuccess = function () { resolve(); };
        req.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function clearAll() {
    return Promise.all(stores.map(function (storeDef) {
      return clearStore(storeDef.name);
    })).then(function () {});
  }

  return {
    putMany: putMany,
    getOne: getOne,
    getAll: getAll,
    count: count,
    clearStore: clearStore,
    clearAll: clearAll,
  };
}

var PagerDB = (function () {
  var CONTACTS_STORE = "contacts";
  var client = createIndexedDbClient("maimai_pager", 1, [
    { name: CONTACTS_STORE, keyPath: "id" },
  ]);

  return {
    append: function (contacts) {
      return client.putMany(CONTACTS_STORE, contacts || []);
    },

    getAll: function () {
      return client.getAll(CONTACTS_STORE);
    },

    getCount: function () {
      return client.count(CONTACTS_STORE);
    },

    clear: function () {
      return client.clearAll();
    },
  };
})();

var DetailDB = (function () {
  var JOBS_STORE = "jobs";
  var DETAILS_STORE = "details";
  var client = createIndexedDbClient("maimai_detail", 1, [
    { name: JOBS_STORE, keyPath: "id" },
    { name: DETAILS_STORE, keyPath: "id" },
  ]);

  return {
    putJob: function (job) {
      return client.putMany(JOBS_STORE, job ? [job] : []);
    },

    putJobs: function (jobs) {
      return client.putMany(JOBS_STORE, jobs || []);
    },

    getJob: function (id) {
      return client.getOne(JOBS_STORE, id);
    },

    getAllJobs: function () {
      return client.getAll(JOBS_STORE);
    },

    putDetail: function (detail) {
      return client.putMany(DETAILS_STORE, detail ? [detail] : []);
    },

    getAllDetails: function () {
      return client.getAll(DETAILS_STORE);
    },

    getCounts: function () {
      return Promise.all([
        client.count(JOBS_STORE),
        client.count(DETAILS_STORE),
      ]).then(function (counts) {
        return { jobs: counts[0], details: counts[1] };
      });
    },

    clear: function () {
      return client.clearAll();
    },

    clearJobs: function () {
      return client.clearStore(JOBS_STORE);
    },

    clearDetails: function () {
      return client.clearStore(DETAILS_STORE);
    },
  };
})();
