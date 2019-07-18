#!/usr/bin/env node

'use strict';

const fs = require('fs');
const path = require('path');
const rw = require('rw');
const pdfjsLib = require('pdfjs-dist');
const assert = require('assert').strict;
const util = require('util');


function main() {
  const pdfExtract = new PDFExtract();

  let pdfPath = process.argv[2];
  let indent = 0;

  let options = {
    normalizeWhitespace: false,
    disableCombineTextItems: false,
  };

  pdfExtract.extract(pdfPath, options, function (err, data) {
    if (err) { return console.error(err); }

    let json = JSON.stringify(data, null, indent);
    rw.writeFileSync('/dev/stdout', json);

    //const lines = PDFExtract.utils.pageToLines(data.pages[0], 2);
    //const rows = PDFExtract.utils.extractTextRows(lines);
    //const text = rows.map(row => row.join('')).join('\n');
    //fs.writeFileSync('./example-output.txt', text);
  });
}


class PDFExtract {

  constructor() {
  }

  extract(filename, options, cb) {
    fs.readFile(filename, (err, buffer) => {
      if (err) {
        return cb(err);
      }
      return this.extractBuffer(buffer, options, (err, pdf) => {
        if (err) {
          cb(err);
        } else {
          pdf.filename = filename;
          cb(null, pdf);
        }
      });
    });
  }

  extractBuffer(buffer, options, cb) {
    // Loading file from file system into typed array
    if (options.verbosity === undefined) {
      // get rid of all warnings in nodejs usage
      options.verbosity = -1;
    }
    if (options.cMapUrl === undefined) {
      options.cMapUrl = path.join(__dirname, './cmaps/'); // trailing path delimiter is important
    }
    if (options.cMapPacked === undefined) {
      options.cMapPacked = true;
    }
    if (options.CMapReaderFactory === undefined) {
      options.CMapReaderFactory = NodeCMapReaderFactory;
    }
    options.data = new Uint8Array(buffer);
    const pdf = {
      meta: {},
      pages: []
    };
    // Will be using promises to load document, pages and misc data instead of callback.
    pdfjsLib.getDocument(options).then(doc => {
      const firstPage = (options && options.firstPage) ? options.firstPage : 1;
      const lastPage = Math.min((options && options.lastPage) ? options.lastPage : doc.numPages, doc.numPages);
      pdf.pdfInfo = doc.pdfInfo;
      let lastPromise; // will be used to chain promises
      lastPromise = doc.getMetadata().then(data => {
        pdf.meta = data;
      });
      const loadPage = pageNum => doc.getPage(pageNum).then(page => {
        const viewport = page.getViewport({scale: 1}); // Note: failing to pass an object with scale results in NaN width and height.
        const out_page = {
          pageInfo: {
            num: pageNum,
            scale: viewport.scale,
            rotation: viewport.rotation,
            offsetX: viewport.offsetX,
            offsetY: viewport.offsetY,
            width: viewport.width,
            height: viewport.height
          }
        };

        pdf.pages.push(out_page);
        const normalizeWhitespace = !!(options && options.normalizeWhitespace === true);
        const disableCombineTextItems = !!(options && options.disableCombineTextItems === true);
        return page.getTextContent({normalizeWhitespace, disableCombineTextItems}).then(content => {
          out_page.content = content.items.map(item => {
            const tm = item.transform;
            let x = tm[4];
            let y = out_page.pageInfo.height - tm[5];
            if (viewport.rotation === 90) {
              x = tm[5];
              y = tm[4];
            }
            // see https://github.com/mozilla/pdf.js/issues/8276
            const height = Math.sqrt(tm[2] * tm[2] + tm[3] * tm[3]);
            return {
              x: x,
              y: y,
              str: item.str,
              dir: item.dir,
              width: item.width,
              height: height,
              fontName: item.fontName
            };
          });
        }).then(() => {
          // console.log('done page parsing');
        }, err => {
          cb(err);
        });
      });
      // Loading of the first page will wait on metadata and subsequent loadings
      // will wait on the previous pages.
      for (let i = firstPage; i <= lastPage; i++) {
        lastPromise = lastPromise.then(loadPage.bind(null, i));
      }
      return lastPromise;
    }).then(() => {
      cb(null, pdf);
    }, err => {
      cb(err);
    });
  }
}


const utils = {
  xStats: page => {
    const x = {};
    page.content.forEach(item => {
      const xx = item.x.toFixed(0);
      x[xx] = (x[xx] || 0) + 1;
    });
    return Object.keys(x).map(key => ({x: key, val: x[key]})).filter(o => o.val > 1).sort((a, b) => a.x - b.x);
  },
  lineStartWithStrings: (line, strings) => {
    if (line.length < strings.length) return false;
    for (let i = 0; i < strings.length; i++) {
      if (line[i].str.indexOf(strings[i]) !== 0) return false;
    }
    return true;
  },
  extractTextRows: lines => lines.map(line => line.map(cell => {
    if (!cell) return null;
    return cell.str;
  })),
  extractColumnRows: (lines, columns, maxdiff) => {
    lines = utils.extractColumnLines(lines, columns, maxdiff);
    return utils.extractTextRows(lines);
  },
  extractColumnLines: (lines, columns, maxdiff) => {

    const getCol = x => {
      let col = 0;
      for (let i = columns.length; i >= 0; i--) {
        if (x < columns[i]) col = i;
      }
      return col;
    };

    return lines.map(line => {
      const row = [];
      line.forEach((cell, j) => {
        const x = cell.x;
        const col = getCol(x);
        if (row[col]) {
          const before = (line[j - 1]);
          const diff = cell.x - (before.x + before.width);
          if (diff < maxdiff) {
            cell.str = row[col].str + cell.str;
            row[col].merged = true;
            row[col].str = '';
          } else {
            console.log('---------------');
            console.log('warning, double content for cell', JSON.stringify(cell));
            console.log('col', col);
            console.log('diff', diff, 'line-length', line.length);
            console.log(line.filter(c => !c.merged).map(c => {
              c.col = getCol(c.x);
              return c;
            }));
            cell.str = row[col].str + '\n' + cell.str;
          }
        }
        while (row.length <= col) {
          row.push(null);
        }
        row[col] = cell;
      });
      return row;
    });
  },
  extractLines: (lines, start_strings, end_strings) => {
    let includeLine = -1;
    return lines.filter(line => {
      if (line.length === 0) return false;
      if (includeLine === -1) {
        if (utils.lineStartWithStrings(line, start_strings)) {
          includeLine = 0;
        }
      } else if (includeLine > -1) {
        if (utils.lineStartWithStrings(line, end_strings)) {
          includeLine = -1;
        } else {
          includeLine++;
        }
      }
      return includeLine > 0;
    });
  },
  pageToLines: (page, maxDiff) => {
    const collector = {};
    page.content.forEach(text => {
      collector[text.y] = collector[text.y] || [];
      collector[text.y].push(text);
    });
    const list = Object.keys(collector).map(key => ({y: key, items: collector[key]})).sort((a, b) => a.y - b.y);
    if (maxDiff > 0) {
      for (let i = list.length - 1; i > 0; i--) {
        const r1 = list[i - 1];
        const r2 = list[i];
        const diff = r2.y - r1.y;
        if (diff < maxDiff) {
          r1.items = r1.items.concat(r2.items);
          r2.items = [];
        }
      }
    }
    list.forEach(item => {
      item.items = item.items.sort((a, b) => a.x - b.x);
    });
    return list.filter(item => item.items.length > 0).map(item => item.items)
  }
};


const _createClass = function () {
  function defineProperties(target, props) {
    for (var i = 0; i < props.length; i++) {
      var descriptor = props[i];
      descriptor.enumerable = descriptor.enumerable || false;
      descriptor.configurable = true;
      if ("value" in descriptor) descriptor.writable = true;
      Object.defineProperty(target, descriptor.key, descriptor);
    }
  }

  return function (Constructor, protoProps, staticProps) {
    if (protoProps) defineProperties(Constructor.prototype, protoProps);
    if (staticProps) defineProperties(Constructor, staticProps);
    return Constructor;
  };
}();

function _classCallCheck(instance, Constructor) {
  if (!(instance instanceof Constructor)) {
    throw new TypeError("Cannot call a class as a function");
  }
}

var NodeCMapReaderFactory = function () {
  function NodeCMapReaderFactory(_ref) {
    var _ref$baseUrl = _ref.baseUrl,
      baseUrl = _ref$baseUrl === undefined ? null : _ref$baseUrl,
      _ref$isCompressed = _ref.isCompressed,
      isCompressed = _ref$isCompressed === undefined ? false : _ref$isCompressed;
    _classCallCheck(this, NodeCMapReaderFactory);
    this.baseUrl = baseUrl;
    this.isCompressed = isCompressed;
  }

  _createClass(NodeCMapReaderFactory, [{
    key: 'fetch',
    value: function fetch(_ref2) {
      var _this = this;
      var name = _ref2.name;
      if (!this.baseUrl) {
        return Promise.reject(new Error('The CMap "baseUrl" parameter must be specified, ensure that ' + 'the "cMapUrl" and "cMapPacked" API parameters are provided.'));
      }
      if (!name) {
        return Promise.reject(new Error('CMap name must be specified.'));
      }
      return new Promise(function (resolve, reject) {
        var url = _this.baseUrl + name + (_this.isCompressed ? '.bcmap' : '');
        fs.readFile(url, function (error, data) {
          if (error || !data) {
            reject(new Error('Unable to load ' + (_this.isCompressed ? 'binary ' : '') + 'CMap at: ' + url));
            return;
          }
          resolve({
            cMapData: new Uint8Array(data),
            compressionType: _this.isCompressed ? pdfjsLib.CMapCompressionType.BINARY : pdfjsLib.CMapCompressionType.NONE
          });
        });
      });
    }
  }]);

  return NodeCMapReaderFactory;
}();


const repr = util.inspect;

function str(obj) {
  return (typeof obj === 'string') ? obj : repr(obj);
}


function errL(...items) {
  let reprs = items.map(str);
  console.error('%s', reprs.join(''));
}


main();
