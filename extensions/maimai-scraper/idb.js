// idb.js — IndexedDB 存储工具
// 用于分页抓取结果存储，替代 chrome.storage.local 的 5MB 限制

var PagerDB = (function () {
  var DB_NAME = "maimai_pager";
  var DB_VERSION = 1;
  var STORE_NAME = "contacts";
  var _db = null; // 缓存连接

  function open() {
    if (_db) return Promise.resolve(_db);
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: "id" });
        }
      };
      req.onsuccess = function (e) {
        _db = e.target.result;
        resolve(_db);
      };
      req.onerror = function (e) { reject(e.target.error); };
    });
  }

  function tx(db, mode) {
    return db.transaction(STORE_NAME, mode).objectStore(STORE_NAME);
  }

  return {
    append: function (contacts) {
      return open().then(function (db) {
        return new Promise(function (resolve, reject) {
          var store = tx(db, "readwrite");
          var count = 0;
          contacts.forEach(function (c) {
            var req = store.put(c);
            req.onsuccess = function () { count++; };
          });
          store.transaction.oncomplete = function () { resolve(count); };
          store.transaction.onerror = function (e) { reject(e.target.error); };
        });
      });
    },

    getAll: function () {
      return open().then(function (db) {
        return new Promise(function (resolve, reject) {
          var req = tx(db, "readonly").getAll();
          req.onsuccess = function () { resolve(req.result); };
          req.onerror = function (e) { reject(e.target.error); };
        });
      });
    },

    getCount: function () {
      return open().then(function (db) {
        return new Promise(function (resolve, reject) {
          var req = tx(db, "readonly").count();
          req.onsuccess = function () { resolve(req.result); };
          req.onerror = function (e) { reject(e.target.error); };
        });
      });
    },

    clear: function () {
      return open().then(function (db) {
        return new Promise(function (resolve, reject) {
          var req = tx(db, "readwrite").clear();
          req.onsuccess = function () { resolve(); };
          req.onerror = function (e) { reject(e.target.error); };
        });
      });
    },
  };
})();